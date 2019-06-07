# -*- coding: utf-8 -*-
"""Script that provides shell-like control for the server"""
from cmd import Cmd
from configparser import ConfigParser
from enum import Enum
import os
from subprocess import DEVNULL, Popen, TimeoutExpired
from uuid import uuid4


DEFAULT_PORT = 5000
APP_FILE = "app.py"
STUB_APP_FILE = "stub.py"

RunningState = Enum(  # pylint: disable=invalid-name
    "RUNNING_STATE", "IDLE MAIN STUB")


class MainShell(Cmd):
    """Shell for server control"""
    prompt = "> "
    null_file = open("output.txt", "a")

    args = ["python", "-m", "flask", "run", "--host=0.0.0.0", None]
    port = DEFAULT_PORT
    state = RunningState.IDLE
    auto_stub = False

    def __init__(self, auto_stub=False):
        super().__init__()
        self.server_process = Popen("", stdout=DEVNULL, shell=True)
        self.server_process.terminate()
        config = ConfigParser()
        config.read("config.ini", encoding="utf-8")
        self.db_file = config["Common"]["DatabaseFile"]
        self.auto_stub = auto_stub
        if auto_stub:
            self._start(True)

    def _start(self, stub=False, port=None):
        if self.state != RunningState.IDLE:
            self.stdout.write("Error: process is already running\n")
            return
        if port is not None:
            self.port = port
        self.args[-1] = "--port={}".format(self.port)
        os.environ["FLASK_APP"] = STUB_APP_FILE if stub else APP_FILE
        self.server_process = Popen(self.args, stdout=self.null_file)
        self.stdout.write("Started {} server on port {}\n"
                          .format("stub" if stub else "main",
                                  self.port))
        self.state = RunningState.STUB if stub else RunningState.MAIN

    def _stop(self, arg=None):
        self.server_process.terminate()
        self.state = RunningState.IDLE
        return arg

    def _stop_and_wait(self):
        self._stop()
        while True:
            try:
                self.server_process.wait(1)
                break
            except TimeoutExpired:
                pass

    @staticmethod
    def _get_port(arg):
        port = DEFAULT_PORT
        try:
            port = int(arg)
            if port not in range(2 ** 16):
                port = DEFAULT_PORT
        except ValueError:
            pass
        return port

    def do_exit(self, arg):
        # pylint: disable=unused-argument
        """Exit from shell"""
        return self._stop(True)

    def do_EOF(self, arg):
        # pylint: disable=invalid-name,unused-argument
        """Exit from shell"""
        return self._stop(True)

    def do_start(self, arg):
        """Start the server"""
        if self.auto_stub and self.state == RunningState.STUB:
            self._stop_and_wait()
        self._start(port=self._get_port(arg))

    def do_stub(self, arg):
        """Start stub server for informing about maintenance"""
        self._start(stub=True, port=self._get_port(arg))

    def do_stop(self, arg):
        """Stop the server"""
        # pylint: disable=unused-argument
        if self.auto_stub:
            self._stop_and_wait()
            self._start(True)
        else:
            self._stop()

    def do_restart(self, arg):
        """Restart the server"""
        # pylint: disable=unused-argument
        self._stop_and_wait()
        self._start()

    def do_status(self, arg):
        """Show status of the server"""
        # pylint: disable=unused-argument
        if self.server_process.poll() is None:
            self.stdout.write("Running\n")
        else:
            self.stdout.write("Stopped\n")

    def do_wipe(self, arg):
        """Delete database of the server"""
        # pylint: disable=unused-argument
        self._stop()
        passwd = uuid4().hex[:8]
        self.stdout.write("Are you sure? Write '{}' to confirm:\n"
                          .format(passwd))
        user_input = self.stdin.readline().strip("\n\r ")
        if user_input != passwd:
            self.stdout.write("Error: wrong input\n")
            return
        os.remove(self.db_file)


SHELL = MainShell(True)
SHELL.cmdloop()
