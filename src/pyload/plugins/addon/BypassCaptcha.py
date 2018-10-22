# -*- coding: utf-8 -*-
from builtins import _

import pycurl
from pyload.core.network.http_request import BadHeader
from pyload.core.network.request_factory import getRequest as get_request
from pyload.plugins.internal.addon import Addon
from pyload.plugins.utils import threaded


class BypassCaptchaException(Exception):
    def __init__(self, err):
        self.err = err

    def get_code(self):
        return self.err

    def __str__(self):
        return "<BypassCaptchaException {}>".format(self.err)

    def __repr__(self):
        return "<BypassCaptchaException {}>".format(self.err)


class BypassCaptcha(Addon):
    __name__ = "BypassCaptcha"
    __type__ = "addon"
    __version__ = "0.14"
    __status__ = "testing"

    __pyload_version__ = "0.5"

    __config__ = [
        ("activated", "bool", "Activated", False),
        ("passkey", "password", "Access key", ""),
        ("check_client", "bool", "Don't use if client is connected", True),
    ]

    __description__ = """Send captchas to BypassCaptcha.com"""
    __license__ = "GPLv3"
    __authors__ = [
        ("RaNaN", "RaNaN@pyload.net"),
        ("Godofdream", "soilfcition@gmail.com"),
        ("zoidberg", "zoidberg@mujmail.cz"),
    ]

    PYLOAD_KEY = "4f771155b640970d5607f919a615bdefc67e7d32"

    SUBMIT_URL = "http://bypasscaptcha.com/upload.php"
    RESPOND_URL = "http://bypasscaptcha.com/check_value.php"
    GETCREDITS_URL = "http://bypasscaptcha.com/ex_left.php"

    def get_credits(self):
        res = self.load(self.GETCREDITS_URL, post={"key": self.config.get("passkey")})

        data = dict(x.split(" ", 1) for x in res.splitlines())
        return int(data["Left"])

    def submit(self, captcha, captchaType="file", match=None):
        with get_request() as req:

            #: Raise timeout threshold
            req.c.setopt(pycurl.LOW_SPEED_TIME, 80)

            res = self.load(
                self.SUBMIT_URL,
                post={
                    "vendor_key": self.PYLOAD_KEY,
                    "key": self.config.get("passkey"),
                    "gen_task_id": "1",
                    "file": (pycurl.FORM_FILE, captcha),
                },
                req=req,
            )

        data = dict(x.split(" ", 1) for x in res.splitlines())
        if not data or "Value" not in data:
            raise BypassCaptchaException(res)

        result = data["Value"]
        ticket = data["TaskId"]
        self.log_debug("Result {} : {}".format(ticket, result))

        return ticket, result

    def respond(self, ticket, success):
        try:
            res = self.load(
                self.RESPOND_URL,
                post={
                    "task_id": ticket,
                    "key": self.config.get("passkey"),
                    "cv": 1 if success else 0,
                },
            )
        except BadHeader as e:
            self.log_error(self._("Could not send response"), e)

    def captcha_task(self, task):
        if "service" in task.data:
            return False

        if not task.isTextual():
            return False

        if not self.config.get("passkey"):
            return False

        if self.pyload.isClientConnected() and self.config.get("check_client"):
            return False

        if self.get_credits() > 0:
            task.handler.append(self)
            task.data["service"] = self.classname
            task.setWaiting(100)
            self._process_captcha(task)

        else:
            self.log_info(self._("Your account has not enough credits"))

    def captcha_correct(self, task):
        if task.data["service"] == self.classname and "ticket" in task.data:
            self.respond(task.data["ticket"], True)

    def captcha_invalid(self, task):
        if task.data["service"] == self.classname and "ticket" in task.data:
            self.respond(task.data["ticket"], False)

    @threaded
    def _process_captcha(self, task):
        c = task.captchaParams["file"]
        try:
            ticket, result = self.submit(c)
        except BypassCaptchaException as e:
            task.error = e.get_code()
            return

        task.data["ticket"] = ticket
        task.setResult(result)