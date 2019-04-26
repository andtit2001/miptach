import sqlite3

CONN = sqlite3.connect("db/imageboard.db")
CURSOR = CONN.cursor()

CURSOR.executescript("""
CREATE TABLE IF NOT EXISTS counters (
board_name VARCHAR(10) PRIMARY KEY,
post_counter INTEGER
);

CREATE TABLE IF NOT EXISTS thread_info (
board_name VARCHAR(10), thread_id INTEGER,
creation_time DATETIME, bumping_time DATETIME,
title VARCHAR(100), archived BOOLEAN,
PRIMARY KEY (board_name, thread_id)
);
CREATE TABLE IF NOT EXISTS thread_posts (
board_name VARCHAR(10), thread_id INTEGER, post_id INTEGER,
PRIMARY KEY (board_name, post_id),
FOREIGN KEY (board_name, thread_id)
REFERENCES thread_info (board_name, thread_id)
);

CREATE TABLE IF NOT EXISTS post_basic (
board_name VARCHAR(10), post_id INTEGER,
creation_time DATETIME, content VARCHAR(10000),
PRIMARY KEY (board_name, post_id),
FOREIGN KEY (board_name, post_id)
REFERENCES thread_posts (board_name, post_id)
);
CREATE TABLE IF NOT EXISTS post_resources (
board_name VARCHAR(10), post_id INTEGER,
res_index SMALLINT, res_id INTEGER,
PRIMARY KEY (board_name, post_id, res_index),
FOREIGN KEY (board_name, post_id)
REFERENCES thread_posts (board_name, post_id)
);

CREATE TABLE IF NOT EXISTS post_replies (
board_name VARCHAR(10), post_id INTEGER, reply_post_id INTEGER,
PRIMARY KEY (board_name, post_id, reply_post_id)
FOREIGN KEY (board_name, post_id)
REFERENCES thread_posts (board_name, post_id)
);

CREATE TABLE IF NOT EXISTS resources (
id INTEGER PRIMARY KEY, res_type VARCHAR(4), original_name TEXT
);
""")
CONN.commit()
CONN.close()
