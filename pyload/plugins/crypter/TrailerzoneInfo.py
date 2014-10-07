# -*- coding: utf-8 -*-

from pyload.plugins.internal.DeadCrypter import DeadCrypter


class TrailerzoneInfo(DeadCrypter):
    __name__ = "TrailerzoneInfo"
    __type__ = "crypter"
    __version__ = "0.03"

    __pattern__ = r'http://(?:www\.)?trailerzone.info/.*?'

    __description__ = """TrailerZone.info decrypter plugin"""
    __authors__ = [("godofdream", "soilfiction@gmail.com")]
