# -*- coding: utf-8 -*-
# @author: RaNaN, spoob, mkaay

import os
import time
from builtins import _, object, str, HOMEDIR
from itertools import islice
from random import randint

from pyload.utils.utils import fs_decode, fs_encode, save_join, save_path

if os.name != "nt":
    from pwd import getpwnam
    from grp import getgrnam


def chunks(iterable, size):
    it = iter(iterable)
    item = list(islice(it, size))
    while item:
        yield item
        item = list(islice(it, size))


class Abort(Exception):
    """
    raised when aborted.
    """


class Fail(Exception):
    """
    raised when failed.
    """


class Reconnect(Exception):
    """
    raised when reconnected.
    """


class Retry(Exception):
    """
    raised when start again from beginning.
    """


class SkipDownload(Exception):
    """
    raised when download should be skipped.
    """


class Base(object):
    """
    A Base class with log/config/db methods *all* plugin types can use.
    """

    __name__ = "Base"

    def __init__(self, core):
        #: Core instance
        self.pyload = core
        #: logging instance
        self.log = core.log
        #: core config
        self.config = core.config

    # log functions
    def logInfo(self, *args):
        self.log.info(
            "{}: {}".format(
                self.__name__,
                " | ".join(a if isinstance(a, str) else str(a) for a in args),
            )
        )

    def logWarning(self, *args):
        self.log.warning(
            "{}: {}".format(
                self.__name__,
                " | ".join(a if isinstance(a, str) else str(a) for a in args),
            )
        )

    def logError(self, *args):
        self.log.error(
            "{}: {}".format(
                self.__name__,
                " | ".join(a if isinstance(a, str) else str(a) for a in args),
            )
        )

    def logDebug(self, *args):
        self.log.debug(
            "{}: {}".format(
                self.__name__,
                " | ".join(a if isinstance(a, str) else str(a) for a in args),
            )
        )

    def setConfig(self, option, value):
        """
        Set config value for current plugin.

        :param option:
        :param value:
        :return:
        """
        self.pyload.config.setPlugin(self.__name__, option, value)

    def getConfig(self, option):
        """
        Returns config value for current plugin.

        :param option:
        :return:
        """
        return self.pyload.config.getPlugin(self.__name__, option)

    def setStorage(self, key, value):
        """
        Saves a value persistently to the database.
        """
        self.pyload.db.setStorage(self.__name__, key, value)

    def store(self, key, value):
        """
        same as `setStorage`
        """
        self.pyload.db.setStorage(self.__name__, key, value)

    def getStorage(self, key=None, default=None):
        """
        Retrieves saved value or dict of all saved entries if key is None.
        """
        if key is not None:
            return self.pyload.db.getStorage(self.__name__, key) or default
        return self.pyload.db.getStorage(self.__name__, key)

    def retrieve(self, *args, **kwargs):
        """
        same as `getStorage`
        """
        return self.getStorage(*args, **kwargs)

    def delStorage(self, key):
        """
        Delete entry in db.
        """
        self.pyload.db.delStorage(self.__name__, key)


class Plugin(Base):
    """
    Base plugin for hoster/crypter.

    Overwrite `process` / `decrypt` in your subclassed plugin.
    """

    __name__ = "Plugin"
    __version__ = "0.4"
    __pattern__ = None
    __type__ = "hoster"
    __config__ = [("name", "type", "desc", "default")]
    __description__ = """Base Plugin"""
    __author_name__ = ("RaNaN", "spoob", "mkaay")
    __author_mail__ = ("RaNaN@pyload.net", "spoob@pyload.net", "mkaay@mkaay.de")

    def __init__(self, pyfile):
        Base.__init__(self, pyfile.m.pyload)

        self.wantReconnect = False
        #: enables simultaneous processing of multiple downloads
        self.multiDL = True
        self.limitDL = 0
        #: chunk limit
        self.chunkLimit = 1
        self.resumeDownload = False

        #: time.time() + wait in seconds
        self.waitUntil = 0
        self.waiting = False

        self.ocr = None  # captcha reader instance
        #: account handler instance, see :py:class:`Account`
        self.account = pyfile.m.pyload.accountManager.getAccountPlugin(self.__name__)

        #: premium status
        self.premium = False
        #: username/login
        self.user = None

        if self.account and not self.account.canUse():
            self.account = None
        if self.account:
            self.user, data = self.account.selectAccount()
            #: Browser instance, see `network.Browser`
            self.req = self.account.getAccountRequest(self.user)
            self.chunkLimit = -1  # chunk limit, -1 for unlimited
            #: enables resume (will be ignored if server dont accept chunks)
            self.resumeDownload = True
            self.multiDL = (
                True
            )  # every hoster with account should provide multiple downloads
            #: premium status
            self.premium = self.account.isPremium(self.user)
        else:
            self.req = pyfile.m.pyload.requestFactory.getRequest(self.__name__)

        #: associated pyfile instance, see `PyFile`
        self.pyfile = pyfile
        self.thread = None  # holds thread in future

        #: location where the last call to download was saved
        self.lastDownload = ""
        #: re match of the last call to `checkDownload`
        self.lastCheck = None
        #: js engine, see `JsEngine`
        self.js = self.pyload.js
        self.cTask = None  # captcha task

        self.retries = 0  # amount of retries already made
        self.html = None  # some plugins store html code here

        self.init()

    def getChunkCount(self):
        if self.chunkLimit <= 0:
            return self.config.get("download", "chunks")
        return min(self.config.get("download", "chunks"), self.chunkLimit)

    def __call__(self):
        return self.__name__

    def init(self):
        """
        initialize the plugin (in addition to `__init__`)
        """
        pass

    def setup(self):
        """
        setup for enviroment and other things, called before downloading
        (possibly more than one time)
        """
        pass

    def preprocessing(self, thread):
        """
        handles important things to do before starting.
        """
        self.thread = thread

        if self.account:
            self.account.checkLogin(self.user)
        else:
            self.req.clearCookies()

        self.setup()

        self.pyfile.setStatus("starting")

        return self.process(self.pyfile)

    def process(self, pyfile):
        """
        the 'main' method of every plugin, you **have to** overwrite it.
        """
        raise NotImplementedError

    def resetAccount(self):
        """
        dont use account and retry download.
        """
        self.account = None
        self.req = self.pyload.requestFactory.getRequest(self.__name__)
        self.retry()

    def checksum(self, local_file=None):
        """
        return codes:

        0  - checksum ok
        1  - checksum wrong
        5  - can't get checksum
        10 - not implemented
        20 - unknown error
        """
        # TODO: checksum check addon

        return True, 10

    def setWait(self, seconds, reconnect=False):
        """
        Set a specific wait time later used with `wait`

        :param seconds: wait time in seconds
        :param reconnect: True if a reconnect would avoid wait time
        """
        if reconnect:
            self.wantReconnect = True
        self.pyfile.waitUntil = time.time() + int(seconds)

    def wait(self):
        """
        waits the time previously set.
        """
        self.waiting = True
        self.pyfile.setStatus("waiting")

        while self.pyfile.waitUntil > time.time():
            self.thread.m.reconnecting.wait(2)

            if self.pyfile.abort:
                raise Abort
            if self.thread.m.reconnecting.isSet():
                self.waiting = False
                self.wantReconnect = False
                raise Reconnect

        self.waiting = False
        self.pyfile.setStatus("starting")

    def fail(self, reason):
        """
        fail and give reason.
        """
        raise Fail(reason)

    def offline(self):
        """
        fail and indicate file is offline.
        """
        raise Fail("offline")

    def tempOffline(self):
        """
        fail and indicates file ist temporary offline, the core may take
        consequences.
        """
        raise Fail("temp. offline")

    def retry(self, max_tries=3, wait_time=1, reason=""):
        """
        Retries and begin again from the beginning.

        :param max_tries: number of maximum retries
        :param wait_time: time to wait in seconds
        :param reason: reason for retrying, will be passed to fail if max_tries reached
        """
        if 0 < max_tries <= self.retries:
            if not reason:
                reason = "Max retries reached"
            raise Fail(reason)

        self.wantReconnect = False
        self.setWait(wait_time)
        self.wait()

        self.retries += 1
        raise Retry(reason)

    def invalidCaptcha(self):
        if self.cTask:
            self.cTask.invalid()

    def correctCaptcha(self):
        if self.cTask:
            self.cTask.correct()

    def decryptCaptcha(
        self,
        url,
        get={},
        post={},
        cookies=False,
        forceUser=False,
        imgtype="jpg",
        result_type="textual",
    ):
        """
        Loads a captcha and decrypts it with ocr, plugin, user input.

        :param url: url of captcha image
        :param get: get part for request
        :param post: post part for request
        :param cookies: True if cookies should be enabled
        :param forceUser: if True, ocr is not used
        :param imgtype: Type of the Image
        :param result_type: 'textual' if text is written on the captcha\
        or 'positional' for captcha where the user have to click\
        on a specific region on the captcha

        :return: result of decrypting
        """

        img = self.load(url, get=get, post=post, cookies=cookies)

        id = "{:.2f}".format(time.time())[-6:].replace(".", "")
        with open(
            os.path.join(
                HOMEDIR, '.pyload'
                "tmp", "tmpCaptcha_{}_{}.{}".format(self.__name__, id, imgtype)
            ),
            "wb",
        ) as temp_file:
            temp_file.write(img)

        has_plugin = self.__name__ in self.pyload.pluginManager.captchaPlugins

        if self.pyload.captcha:
            Ocr = self.pyload.pluginManager.loadClass("captcha", self.__name__)
        else:
            Ocr = None

        if Ocr and not forceUser:
            time.sleep(randint(3000, 5000) / 1000.0)
            if self.pyfile.abort:
                raise Abort

            ocr = Ocr()
            result = ocr.get_captcha(temp_file.name)
        else:
            captchaManager = self.pyload.captchaManager
            task = captchaManager.newTask(img, imgtype, temp_file.name, result_type)
            self.cTask = task
            captchaManager.handleCaptcha(task)

            while task.isWaiting():
                if self.pyfile.abort:
                    captchaManager.os.removeTask(task)
                    raise Abort
                time.sleep(1)

            captchaManager.os.removeTask(task)

            if (
                task.error and has_plugin
            ):  # ignore default error message since the user could use OCR
                self.fail(
                    _(
                        "Pil and tesseract not installed and no Client connected for captcha decrypting"
                    )
                )
            elif task.error:
                self.fail(task.error)
            elif not task.result:
                self.fail(
                    _(
                        "No captcha result obtained in appropiate time by any of the plugins."
                    )
                )

            result = task.result
            self.log.debug("Received captcha result: {}".format(str(result)))

        if not self.pyload.debug:
            try:
                os.remove(temp_file.name)
            except Exception:
                pass

        return result

    def load(
        self,
        url,
        get={},
        post={},
        ref=True,
        cookies=True,
        just_header=False,
        decode=False,
    ):
        """
        Load content at url and returns it.

        :param url:
        :param get:
        :param post:
        :param ref:
        :param cookies:
        :param just_header: if True only the header will be retrieved and returned as dict
        :param decode: Wether to decode the output according to http header, should be True in most cases
        :return: Loaded content
        """
        if self.pyfile.abort:
            raise Abort
        # utf8 vs decode -> please use decode attribute in all future plugins
        if isinstance(url, str):
            url = str(url)

        res = self.req.load(url, get, post, ref, cookies, just_header, decode=decode)

        if self.pyload.debug:
            from inspect import currentframe

            frame = currentframe()
            os.makedirs(os.path.join(HOMEDIR, '.pyload', "tmp", self.__name__), exist_ok=True)

            with open(
                os.path.join(
                    HOMEDIR,
                    '.pyload',
                    "tmp",
                    self.__name__,
                    "{}_line{}.dump.html".format(
                        frame.f_back.f_code.co_name, frame.f_back.f_lineno
                    ),
                ),
                "wb",
            ) as f:
                del frame  # delete the frame or it wont be cleaned

                try:
                    tmp = res.encode("utf8")
                except Exception:
                    tmp = res

                f.write(tmp)

        if just_header:
            # parse header
            header = {"code": self.req.code}
            for line in res.splitlines():
                line = line.strip()
                if not line or ":" not in line:
                    continue

                key, none, value = line.partition(":")
                key = key.lower().strip()
                value = value.strip()

                if key in header:
                    if isinstance(header[key], list):
                        header[key].append(value)
                    else:
                        header[key] = [header[key], value]
                else:
                    header[key] = value
            res = header

        return res

    def download(self, url, get={}, post={}, ref=True, cookies=True, disposition=False):
        """
        Downloads the content at url to download folder.

        :param url:
        :param get:
        :param post:
        :param ref:
        :param cookies:
        :param disposition: if True and server provides content-disposition header\
        the filename will be changed if needed
        :return: The location where the file was saved
        """

        self.checkForSameFiles()

        self.pyfile.setStatus("downloading")

        download_folder = self.config.get("general", "download_folder")

        location = save_join(download_folder, self.pyfile.package().folder)

        os.makedirs(
            location, int(self.pyload.config.get("permission", "folder"), 8), exist_ok=True
        )

        if self.pyload.config.get("permission", "change_dl") and os.name != "nt":
            try:
                uid = getpwnam(self.config.get("permission", "user"))[2]
                gid = getgrnam(self.config.get("permission", "group"))[2]

                os.chown(location, uid, gid)
            except Exception as e:
                self.log.warning(
                    _("Setting User and Group failed: {}").format(str(e))
                )

        # convert back to unicode
        location = fs_decode(location)
        name = save_path(self.pyfile.name)

        filename = os.path.join(location, name)

        self.pyload.addonManager.dispatchEvent(
            "downloadStarts", self.pyfile, url, filename
        )

        try:
            newname = self.req.httpDownload(
                url,
                filename,
                get=get,
                post=post,
                ref=ref,
                cookies=cookies,
                chunks=self.getChunkCount(),
                resume=self.resumeDownload,
                progressNotify=self.pyfile.setProgress,
                disposition=disposition,
            )
        finally:
            self.pyfile.size = self.req.size

        if disposition and newname and newname != name:  # triple check, just to be sure
            self.log.info(
                "{name} saved as {newname}".format(**{"name": name, "newname": newname})
            )
            self.pyfile.name = newname
            filename = os.path.join(location, newname)

        fs_filename = fs_encode(filename)

        if self.pyload.config.get("permission", "change_file"):
            os.chmod(fs_filename, int(self.pyload.config.get("permission", "file"), 8))

        if self.pyload.config.get("permission", "change_dl") and os.name != "nt":
            try:
                uid = getpwnam(self.config.get("permission", "user"))[2]
                gid = getgrnam(self.config.get("permission", "group"))[2]

                os.chown(fs_filename, uid, gid)
            except Exception as e:
                self.log.warning(_("Setting User and Group failed: {}").format(str(e)))

        self.lastDownload = filename
        return self.lastDownload

    def checkDownload(
        self, rules, api_size=0, max_size=50000, delete=True, read_size=0
    ):
        """
        checks the content of the last downloaded file, re match is saved to
        `lastCheck`

        :param rules: dict with names and rules to match (compiled regexp or strings)
        :param api_size: expected file size
        :param max_size: if the file is larger then it wont be checked
        :param delete: delete if matched
        :param read_size: amount of bytes to read from files larger then max_size
        :return: dictionary key of the first rule that matched
        """
        lastDownload = fs_encode(self.lastDownload)
        if not os.path.exists(lastDownload):
            return None

        size = os.stat(lastDownload)
        size = size.st_size

        if api_size and api_size <= size:
            return None
        elif size > max_size and not read_size:
            return None
        self.log.debug("Download Check triggered")
        with open(lastDownload, "rb") as f:
            content = f.read(read_size if read_size else -1)
        # produces encoding errors, better log to other file in the future?
        # self.log.debug("Content: {}".format(content))
        for name, rule in rules.items():
            if type(rule) in (str, bytes):
                if rule in content:
                    if delete:
                        os.remove(lastDownload)
                    return name
            elif hasattr(rule, "search"):
                m = rule.search(content)
                if m:
                    if delete:
                        os.remove(lastDownload)
                    self.lastCheck = m
                    return name

    def getPassword(self):
        """
        get the password the user provided in the package.
        """
        password = self.pyfile.package().password
        if not password:
            return ""
        return password

    def checkForSameFiles(self, starting=False):
        """
        checks if same file was/is downloaded within same package.

        :param starting: indicates that the current download is going to start
        :raises SkipDownload:
        """

        pack = self.pyfile.package()

        for pyfile in self.pyload.files.cache.values():
            if (
                pyfile != self.pyfile
                and pyfile.name == self.pyfile.name
                and pyfile.package().folder == pack.folder
            ):
                if pyfile.status in (0, 12):  # finished or downloading
                    raise SkipDownload(pyfile.pluginname)
                elif (
                    pyfile.status in (5, 7) and starting
                ):  # a download is waiting/starting and was appenrently started before
                    raise SkipDownload(pyfile.pluginname)

        download_folder = self.config.get("general", "download_folder")
        location = save_join(download_folder, pack.folder, self.pyfile.name)

        if (
            starting
            and self.pyload.config.get("download", "skip_existing")
            and os.path.exists(location)
        ):
            size = os.stat(location).st_size
            if size >= self.pyfile.size:
                raise SkipDownload("File exists.")

        pyfile = self.pyload.db.findDuplicates(
            self.pyfile.id, self.pyfile.package().folder, self.pyfile.name
        )
        if pyfile:
            if os.path.exists(location):
                raise SkipDownload(pyfile[0])

            self.log.debug(
                "File {} not skipped, because it does not exists.".format(
                    self.pyfile.name
                )
            )

    def clean(self):
        """
        clean everything and os.remove references.
        """
        if hasattr(self, "pyfile"):
            del self.pyfile
        if hasattr(self, "req"):
            self.req.close()
            del self.req
        if hasattr(self, "thread"):
            del self.thread
        if hasattr(self, "html"):
            del self.html