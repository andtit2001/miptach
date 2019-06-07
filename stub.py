# -*- coding: utf-8 -*-
"""Stub site which is used for informing about maintainance."""
from configparser import ConfigParser

from flask import Flask, abort, redirect

config = ConfigParser()  # pylint: disable=invalid-name
config.read("config.ini", encoding="utf-8")
SITE_NAME = config["Common"]["SiteName"]

app = Flask(SITE_NAME)  # pylint: disable=invalid-name


@app.route("/")
def home():
    """Show message about maintainance."""
    abort(503)


# pylint: disable=unused-argument
@app.route("/<path:path>")
def deny(path):
    """Deny access to any page."""
    return redirect("/", 307)


app.run(host="0.0.0.0")
