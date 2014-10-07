# -*- coding: utf-8 -*-

from pyload.plugins.internal.DeadHoster import DeadHoster, create_getInfo


class HellspyCz(DeadHoster):
    __name__ = "HellspyCz"
    __type__ = "hoster"
    __version__ = "0.28"

    __pattern__ = r'http://(?:www\.)?(?:hellspy\.(?:cz|com|sk|hu|pl)|sciagaj.pl)(/\S+/\d+)/?.*'

    __description__ = """HellSpy.cz hoster plugin"""
    __authors__ = [("zoidberg", "zoidberg@mujmail.cz")]


getInfo = create_getInfo(HellspyCz)
