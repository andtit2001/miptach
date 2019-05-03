# -*- coding: utf-8 -*-
"""Stub site which is used for informing about maintainance."""
from configparser import ConfigParser

from flask import Flask, abort, redirect

CONFIG = ConfigParser()
CONFIG.read("config.ini", encoding="utf-8")
SITE_NAME = CONFIG["Common"]["SiteName"]
SERVER = Flask(SITE_NAME)


@SERVER.route("/")
def home():
    """Show message about maintainance."""
    abort(503)


# pylint: disable=unused-argument
@SERVER.route("/<path:path>")
def deny(path):
    """Deny access to any page."""
    return redirect("/", 307)


SERVER.run(host="0.0.0.0")
