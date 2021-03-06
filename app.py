# -*- coding: utf-8 -*-
"""Backend of MIPTach (Flask + SQLite)"""
from configparser import ConfigParser, ExtendedInterpolation
from datetime import datetime
import logging
from logging.handlers import TimedRotatingFileHandler
import sqlite3
import threading

# import bleach
from flask import Flask, abort, g, redirect, render_template, request
# from flask.ext.babel import Babel
from markdown import markdown
from markupsafe import Markup

CONFIG = ConfigParser()
CONFIG.read("config.ini", encoding="utf-8")
SITE_NAME = CONFIG["Common"]["SiteName"]
ANNOUNCE = Markup(CONFIG["Common"]["Announcement"]
                  ) if "Announcement" in CONFIG["Common"] else None

BOARD_DICT = {}
DEFAULT_LANG = CONFIG["LanguageFiles"].pop("Default", "en")
LANG_CONFIG = ConfigParser(interpolation=ExtendedInterpolation())
LANG_CONFIG.read_dict(CONFIG)
LANG_CONFIG.read(CONFIG["LanguageFiles"][DEFAULT_LANG], encoding="utf-8")
for board in LANG_CONFIG["Boards"]:
    BOARD_DICT[board] = LANG_CONFIG["Boards"][board]
# LANG_CONFIG = {}
# for lang in CONFIG["LanguageFiles"]:
#     cur_config = ConfigParser(interpolation=ExtendedInterpolation())
#     LANG_CONFIG[lang] = cur_config
#     cur_config.read_dict(CONFIG)
#     cur_config.read(CONFIG["LanguageFiles"][DEFAULT_LANG], encoding="utf-8")
#     for board in cur_config["Boards"]:
#         BOARD_DICT[board] = cur_config["Boards"][board]

SERVER = Flask(SITE_NAME, static_folder=CONFIG["Common"]["StaticFolder"],
               template_folder=CONFIG["Common"]["TemplateFolder"])
SERVER.jinja_env.trim_blocks = True
SERVER.jinja_env.lstrip_blocks = True
# BABEL = Babel(server)

DB_LOCK = threading.Lock()


def get_db():
    """Get Connection object."""
    if "db_connection" not in g:
        g.db_connection = sqlite3.connect(CONFIG["Common"]["DatabaseFile"])
    return g.db_connection


# pylint: disable=unused-argument
@SERVER.teardown_appcontext
def teardown_db(exception):
    """Close database connection."""
    db_connection = g.pop("db_connection", None)
    if db_connection is not None:
        db_connection.close()


@SERVER.route("/")
def home():
    """Generate and return homepage."""
    return render_template("index.html",
                           site_name=SITE_NAME,
                           announce=ANNOUNCE,
                           board_list=BOARD_DICT.items())


@SERVER.route("/about")
def about():
    """Generate and return "About" page."""
    return render_template("about.html",
                           site_name=SITE_NAME,
                           announce=ANNOUNCE)


@SERVER.route("/<board_name>/", methods=["GET", "POST"])
def board_handler(board_name):
    """Handler for board page (postback + PRG)."""
    if request.method == "GET":
        return get_board(board_name)
    else:
        return create_thread(board_name)


@SERVER.route("/<board_name>/<int:thread_id>", methods=["GET", "POST"])
def thread_handler(board_name, thread_id):
    """Handler for thread page (postback + PRG)."""
    if request.method == "GET":
        return get_thread(board_name, thread_id)
    else:
        return create_post(board_name, thread_id)


# @SERVER.route("/<board_name>/")
def get_board(board_name):
    """Generate and return page of board."""
    if board_name not in BOARD_DICT:
        abort(404)
    cursor = get_db().cursor()
    result = cursor.execute("""
SELECT thread_id, title, creation_time
FROM thread_info
WHERE NOT archived AND board_name = :board_name
ORDER BY bumping_time DESC
LIMIT 20 OFFSET :offset;""",
                            {"board_name": board_name, "offset": 0}).fetchall()
    converted_result = []
    for item in result:
        converted_result.append((item[0], item[1],
                                 str(datetime.strptime(
                                     item[2], "%Y-%m-%d %H:%M:%S.%f")
                                     .replace(microsecond=0)),))
    return render_template("board.html",
                           site_name=SITE_NAME,
                           announce=ANNOUNCE,
                           board_info=(
                               board_name, BOARD_DICT[board_name],),
                           threads=converted_result)


# @SERVER.route("/<board_name>/<int:thread_id>")
def get_thread(board_name, thread_id):
    """Generate and return page of thread."""
    if board_name not in BOARD_DICT:
        abort(404)
    cursor = get_db().cursor()
    title = cursor.execute("""
SELECT title
FROM thread_info
WHERE board_name = :board_name
AND thread_id = :thread_id;""", {"board_name": board_name,
                                 "thread_id": thread_id}).fetchone()
    if title is None:
        abort(404)
    title = title[0]
    result = cursor.execute("""
SELECT post_basic.post_id, content, creation_time
FROM post_basic INNER JOIN thread_posts
ON post_basic.board_name = thread_posts.board_name
AND post_basic.post_id = thread_posts.post_id
WHERE post_basic.board_name = :board_name
AND thread_id = :thread_id
ORDER BY creation_time ASC;""", {"board_name": board_name,
                                 "thread_id": thread_id}).fetchall()
    converted_result = []
    for item in result:
        converted_result.append(
            (item[0], Markup(markdown(item[1], output_format="html5")),
             datetime.strftime(
                 datetime.strptime(item[2],
                                   "%Y-%m-%d %H:%M:%S.%f"),
                 "%Y-%m-%d %H:%M:%S"),))
    return render_template("thread.html",
                           site_name=SITE_NAME,
                           announce=ANNOUNCE,
                           board_info=(
                               board_name, BOARD_DICT[board_name],),
                           thread_title=title,
                           thread_id=thread_id,
                           posts=converted_result)


# @SERVER.route("/<board_name>/create_thread", methods=["POST"])
def create_thread(board_name):
    """Create new thread in board."""
    if board_name not in BOARD_DICT:
        abort(404)
    if request.form["thread_title"] is None:
        abort(403, Markup("Value <code>thread_title</code> is required."))
    string_length = len(request.form["thread_title"])
    if string_length < 3 or string_length > 10000:
        abort(403, Markup("Length of value <code>thread_title</code>" +
                          " must lie in range from 3 to 10000."))
    if request.form["initial_text"] is None:
        abort(403, Markup("Value <code>initial_text</code> is required."))
    string_length = len(request.form["initial_text"])
    if string_length < 3 or string_length > 10000:
        abort(403, Markup("Length of value <code>initial_text</code>" +
                          " must lie in range from 3 to 10000."))

    with DB_LOCK:
        conn = get_db()
        cursor = conn.cursor()

        time = datetime.utcnow()
        post_id = cursor.execute("""
SELECT post_counter
FROM counters
WHERE board_name = :board_name;""", {"board_name": board_name}).fetchone()
        if post_id is None:
            post_id = 0
        else:
            post_id = post_id[0]

        cursor.execute("""
INSERT INTO thread_info
VALUES (:board_name, :thread_id,
:creation_time, :bumping_time,
:title, 0)""", {"board_name": board_name,
                "thread_id": post_id,
                "creation_time": time,
                "bumping_time": time,
                "title": request.form["thread_title"]})
        cursor.execute("""
INSERT INTO thread_posts
VALUES (:board_name, :thread_id, :post_id)""",
                       {"board_name": board_name,
                        "thread_id": post_id,
                        "post_id": post_id})
        cursor.execute("""
INSERT INTO post_basic
VALUES (:board_name, :post_id,
:creation_time, :content)""",
                       {"board_name": board_name,
                        "post_id": post_id,
                        "creation_time": time,
                        "content": request.form["initial_text"]})

        if post_id == 0:
            cursor.execute("""
INSERT INTO counters
VALUES (:board_name, 1);""", {"board_name": board_name})
        else:
            cursor.execute("""
UPDATE counters
SET post_counter = :post_counter
WHERE board_name = :board_name;""", {"board_name": board_name,
                                     "post_counter": post_id + 1})
        conn.commit()
    return redirect("/{}/".format(board_name), 303)


# @SERVER.route("/<board_name>/<int:thread_id>/create_post", methods=["POST"])
def create_post(board_name, thread_id):
    """Create new post in thread."""
    if board_name not in BOARD_DICT:
        abort(404)
    if request.form["content"] is None:
        abort(403, Markup("Value <code>content</code> is required."))
    string_length = len(request.form["content"])
    if string_length < 3 or string_length > 10000:
        abort(403, Markup("Length of value <code>content</code>" +
                          " must lie in range from 3 to 10000."))

    with DB_LOCK:
        conn = get_db()
        cursor = conn.cursor()

        time = datetime.utcnow()
        post_id = cursor.execute("""
SELECT post_counter
FROM counters
WHERE board_name = :board_name;""", {"board_name": board_name}).fetchone()
        if post_id is None:
            post_id = 0
        else:
            post_id = post_id[0]

        test = cursor.execute("""
SELECT thread_id FROM thread_info
WHERE board_name = :board_name
AND thread_id = :thread_id;""", {"board_name": board_name,
                                 "thread_id": thread_id}).fetchone()
        if test is None:
            abort(404)

        cursor.execute("""
UPDATE thread_info
SET bumping_time = :bumping_time
WHERE board_name = :board_name
AND thread_id = :thread_id;""", {"board_name": board_name,
                                 "thread_id": thread_id,
                                 "bumping_time": time})
        cursor.execute("""
INSERT INTO thread_posts
VALUES (:board_name, :thread_id, :post_id)""",
                       {"board_name": board_name,
                        "thread_id": thread_id,
                        "post_id": post_id})
        cursor.execute("""
INSERT INTO post_basic
VALUES (:board_name, :post_id,
:creation_time, :content)""",
                       {"board_name": board_name,
                        "post_id": post_id,
                        "creation_time": time,
                        "content": request.form["content"]})

        if post_id == 0:
            cursor.execute("""
INSERT INTO counters
VALUES (:board_name, 1);""", {"board_name": board_name})
        else:
            cursor.execute("""
UPDATE counters
SET post_counter = :post_counter
WHERE board_name = :board_name;""", {"board_name": board_name,
                                     "post_counter": post_id + 1})
        conn.commit()
    return redirect("/{}/{}".format(board_name, thread_id), 303)


HANDLER = TimedRotatingFileHandler("logs/log.log", encoding="utf-8", utc=True)
HANDLER.setLevel(logging.INFO)
logging.root.handlers = [HANDLER]
