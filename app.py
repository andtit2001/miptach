# -*- coding: utf-8 -*-
"""Backend of MIPTach (Flask + SQLite)"""
from collections import deque
from configparser import ConfigParser, ExtendedInterpolation
from datetime import datetime
from enum import Enum
import logging
from logging.handlers import TimedRotatingFileHandler
import os.path
import shutil
import sqlite3
import threading

from flask import (Flask, abort, g, redirect, render_template, request,
                   send_file, url_for)
# from flask.ext.babel import Babel
from markupsafe import Markup

from captcha import generate_captcha
from setup import setup_database
from text_filter import markdown_to_html


config = ConfigParser()  # pylint: disable=invalid-name
config.read("config.ini", encoding="utf-8")
SITE_NAME = config["Common"]["SiteName"]
ANNOUNCE = Markup(config["Common"]["Announcement"]
                  ) if "Announcement" in config["Common"] else None
CAPTCHA_DIR = config["Common"]["CaptchaFolder"]

if not os.path.exists(config["Common"]["DatabaseFile"]):
    setup_database(config["Common"]["DatabaseFile"])
if os.path.exists(CAPTCHA_DIR):
    shutil.rmtree(CAPTCHA_DIR)
os.mkdir(CAPTCHA_DIR)

DEFAULT_LANG = config["LanguageFiles"].pop("Default", "en")
lang_config = ConfigParser(  # pylint: disable=invalid-name
    interpolation=ExtendedInterpolation())
lang_config.read_dict(config)
lang_config.read(config["LanguageFiles"][DEFAULT_LANG], encoding="utf-8")
BOARD_DICT = dict(lang_config["Boards"])

app = Flask(SITE_NAME,  # pylint: disable=invalid-name
            static_folder=config["Common"]["StaticFolder"],
            template_folder=config["Common"]["TemplateFolder"])
app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True

DB_LOCK = threading.Lock()

CAPTCHA_LOCK = threading.Lock()
captcha_queue = deque()  # pylint: disable=invalid-name
captcha_values = dict()  # pylint: disable=invalid-name
MAX_CAPTCHA_QUEUE_SIZE = config.getint("Common", "MaxCaptchaQueueSize")
CaptchaResult = Enum(  # pylint: disable=invalid-name
    "CAPTCHA_RESULT", "NOT_FOUND WRONG CORRECT")


def get_db():
    """Get Connection object."""
    if "db_connection" not in g:
        g.db_connection = sqlite3.connect(config["Common"]["DatabaseFile"])
    return g.db_connection


# pylint: disable=unused-argument
@app.teardown_appcontext
def teardown_db(exception):
    """Close database connection."""
    db_connection = g.pop("db_connection", None)
    if db_connection is not None:
        db_connection.close()


@app.route("/")
def home():
    """Generate and return homepage."""
    return render_template("index.html",
                           site_name=SITE_NAME,
                           announce=ANNOUNCE,
                           board_list=BOARD_DICT.items())


@app.route("/rules")
def rules():
    """Generate and return page with rules."""
    return render_template("rules.html",
                           site_name=SITE_NAME,
                           announce=ANNOUNCE)


@app.route("/about")
def about():
    """Generate and return "About" page."""
    return render_template("about.html",
                           site_name=SITE_NAME,
                           announce=ANNOUNCE)


@app.route("/<board_name>/", methods=["GET", "POST"])
def board_handler(board_name):
    """Handler for board page (postback + PRG)."""
    if request.method == "GET":
        return get_board(board_name)
    else:
        return create_thread(board_name)


@app.route("/<board_name>/<int:thread_id>", methods=["GET", "POST"])
def thread_handler(board_name, thread_id):
    """Handler for thread page (postback + PRG)."""
    if request.method == "GET":
        return get_thread(board_name, thread_id)
    else:
        return create_post(board_name, thread_id)


@app.route("/<board_name>/arch/<int:thread_id>")
def archived_thread_handler(board_name, thread_id):
    """Handler for archived thread page."""
    return get_thread(board_name, thread_id, True)


def get_captcha():
    """Generate new CAPTCHA."""
    with CAPTCHA_LOCK:
        captcha = generate_captcha(
            webp=config.getboolean("Common", "EnableWebp"),
            uuid_set=captcha_values,
            img_dir=CAPTCHA_DIR)
        captcha_uuid = captcha[2]

        if len(captcha_queue) == MAX_CAPTCHA_QUEUE_SIZE:
            deleted_uuid = captcha_queue.popleft()
            del captcha_values[deleted_uuid]
        captcha_queue.append((captcha_uuid, captcha[0],))
        captcha_values[captcha_uuid] = captcha[1]

        return (captcha_uuid, Markup(captcha[0]),)


def verify_captcha(captcha_uuid, value):
    """Check if answer to CAPTCHA is correct."""
    with CAPTCHA_LOCK:
        if captcha_uuid not in captcha_values:
            return CaptchaResult.NOT_FOUND
        answer = captcha_values[captcha_uuid]
        del captcha_values[captcha_uuid]
        if answer != value:
            return CaptchaResult.WRONG
        return CaptchaResult.CORRECT


@app.route("/captcha/<filename>")
def get_captcha_image(filename):
    """Captcha image router"""
    full_name = CAPTCHA_DIR + '/' + filename
    if not os.path.exists(full_name):
        abort(404)
    return send_file(full_name)


def get_board(board_name):
    """Generate and return page of board."""
    if board_name not in BOARD_DICT:
        abort(404)
    captcha = get_captcha()
    cursor = get_db().cursor()
    result = cursor.execute("""
SELECT thread_id, title, creation_time
FROM thread_info
WHERE NOT archived AND board_name = :board_name
ORDER BY bumping_time DESC;""", {"board_name": board_name}).fetchall()
    converted_result = []
    for item in result:
        converted_result.append((item[0], item[1],
                                 datetime.strftime(
                                     datetime.strptime(
                                         item[2],
                                         "%Y-%m-%d %H:%M:%S.%f"),
                                     "%Y-%m-%d %H:%M:%S"),))
    return render_template("board.html",
                           site_name=SITE_NAME,
                           announce=ANNOUNCE,
                           board_info=(
                               board_name, BOARD_DICT[board_name],),
                           threads=converted_result,
                           captcha=captcha)


@app.route("/<board_name>/arch/")
def get_archive(board_name):
    """Generate and return page of "board archive"."""
    if board_name not in BOARD_DICT:
        abort(404)
    cursor = get_db().cursor()
    result = cursor.execute("""
SELECT thread_id, title, creation_time
FROM thread_info
WHERE archived AND board_name = :board_name
ORDER BY bumping_time DESC
LIMIT 20 OFFSET :offset;""", {"board_name": board_name,
                              "offset": 0}).fetchall()
    converted_result = []
    for item in result:
        converted_result.append((item[0], item[1],
                                 datetime.strftime(
                                     datetime.strptime(
                                         item[2],
                                         "%Y-%m-%d %H:%M:%S.%f"),
                                     "%Y-%m-%d %H:%M:%S"),))
    return render_template("archive.html",
                           site_name=SITE_NAME,
                           announce=ANNOUNCE,
                           board_info=(
                               board_name, BOARD_DICT[board_name],),
                           threads=converted_result)


def get_thread(board_name, thread_id, from_archive=False):
    """Generate and return page of thread."""
    if board_name not in BOARD_DICT:
        abort(404)
    if board_name != "sandbox":
        captcha = get_captcha()
    cursor = get_db().cursor()
    thread_info = cursor.execute("""
SELECT title, archived
FROM thread_info
WHERE board_name = :board_name
AND thread_id = :thread_id;""", {"board_name": board_name,
                                 "thread_id": thread_id}).fetchone()
    if thread_info is None:
        abort(404)
    if not from_archive and thread_info[1]:
        return redirect(url_for("archived_thread_handler",
                                board_name=board_name,
                                thread_id=thread_id), 301)

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
            (item[0], Markup(item[1]),
             datetime.strftime(
                 datetime.strptime(
                     item[2],
                     "%Y-%m-%d %H:%M:%S.%f"),
                 "%Y-%m-%d %H:%M:%S"),))
    return render_template("thread.html",
                           site_name=SITE_NAME,
                           announce=ANNOUNCE,
                           board_info=(
                               board_name, BOARD_DICT[board_name],),
                           thread_title=thread_info[0],
                           thread_id=thread_id,
                           posts=converted_result,
                           archived=thread_info[1],
                           captcha=captcha if "captcha" in locals() else None)


def verify_request_with_markdown(field_name):
    """Filter text from `field_name` and check its length."""
    if request.form[field_name] is None:
        abort(403, Markup("Value <code>{}</code> is required."
                          .format(field_name)))
    initial_text = markdown_to_html(request.form[field_name].replace(
        "\r\n", "\n"))
    string_length = len(initial_text[0])
    if string_length < 3 or string_length > 10000:
        abort(403, Markup("""\
Length of processed <code>{0}</code> must lie in range from 3 to 10000.
<br><br>
<code>{0}</code> after processing ({1} characters):
<pre><code>{2}</code></pre>
""".format(field_name,
           len(initial_text[0]),
           Markup.escape(initial_text[0]))))
    return initial_text[1]


def create_thread(board_name):
    """Create new thread in board."""
    if board_name not in BOARD_DICT:
        abort(404)
    if request.form["thread_title"] is None:
        abort(403, Markup("Value <code>thread_title</code> is required."))
    string_length = len(request.form["thread_title"])
    if string_length < 3 or string_length > 10000:
        abort(403, Markup("Length of <code>thread_title</code>" +
                          " must lie in range from 3 to 10000."))
    if board_name == "sandbox":
        text = request.form["initial_text"]
    else:
        text = verify_request_with_markdown("initial_text")

    result = verify_captcha(request.form["uuid"],
                            int(request.form["expr_value"]))
    if result == CaptchaResult.NOT_FOUND:
        abort(403, "Invalid CAPTCHA ID. Please go back and try again.")
    if result == CaptchaResult.WRONG:
        abort(403, "Wrong answer to CAPTCHA. Please go back and try again.")

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

        threads = cursor.execute("""
SELECT thread_id
FROM thread_info
WHERE NOT archived AND board_name = :board_name
ORDER BY bumping_time ASC;""", {"board_name": board_name}).fetchall()
        if len(threads) == config.getint("BumpLimits", board_name):
            thread_id = threads[0][0]
            cursor.execute("""
UPDATE thread_info
SET archived = 1
WHERE board_name = :board_name
AND thread_id = :thread_id;""", {"board_name": board_name,
                                 "thread_id": thread_id})

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
                        "content": text})

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
        return redirect(url_for("thread_handler",
                                board_name=board_name,
                                thread_id=post_id), 303)


def create_post(board_name, thread_id):
    """Create new post in thread."""
    if board_name not in BOARD_DICT:
        abort(404)
    if board_name == "sandbox":
        text = request.form["content"]
    else:
        text = verify_request_with_markdown("content")

    if board_name != "sandbox":
        result = verify_captcha(request.form["uuid"],
                                int(request.form["expr_value"]))
        if result == CaptchaResult.NOT_FOUND:
            abort(403,
                  "Invalid CAPTCHA ID. Please go back and try again.")
        if result == CaptchaResult.WRONG:
            abort(403,
                  "Wrong answer to CAPTCHA. Please go back and try again.")

    with DB_LOCK:
        conn = get_db()
        cursor = conn.cursor()

        thread_info = cursor.execute("""
SELECT thread_id, archived
FROM thread_info
WHERE board_name = :board_name
AND thread_id = :thread_id;""", {"board_name": board_name,
                                 "thread_id": thread_id}).fetchone()
        if thread_info is None:
            abort(404)
        if thread_info[1]:
            abort(403, "Thread has been archived.")

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
                        "content": text})

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
    return redirect(url_for("thread_handler",
                            board_name=board_name,
                            thread_id=thread_id), 303)


HANDLER = TimedRotatingFileHandler("logs/log.log", encoding="utf-8", utc=True)
HANDLER.setLevel(logging.INFO)
logging.root.handlers = [HANDLER]
