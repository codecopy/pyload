# -*- coding: utf-8 -*-

from pyload.plugins.internal.SimpleCrypter import SimpleCrypter


class FiletramCom(SimpleCrypter):
    __name__ = "FiletramCom"
    __type__ = "crypter"
    __version__ = "0.02"

    __pattern__ = r'http://(?:www\.)?filetram.com/[^/]+/.+'

    __description__ = """Filetram.com decrypter plugin"""
    __authors__ = [("igel", "igelkun@myopera.com"),
                   ("stickell", "l.stickell@yahoo.it")]


    LINK_PATTERN = r'\s+(http://.+)'
    TITLE_PATTERN = r'<title>(.+?) - Free Download'
