# -*- coding: utf-8 -*-

from pyload.network.RequestFactory import getURL
from pyload.plugins.internal.MultiHoster import MultiHoster


class PremiumTo(MultiHoster):
    __name__ = "PremiumTo"
    __type__ = "hook"
    __version__ = "0.04"

    __config__ = [("activated", "bool", "Activated", False),
                  ("hosterListMode", "all;listed;unlisted", "Use for downloads from supported hosters:", "all"),
                  ("hosterList", "str", "Hoster list (comma separated)", "")]

    __description__ = """Premium.to hook plugin"""
    __authors__ = [("RaNaN", "RaNaN@pyload.org"),
                   ("zoidberg", "zoidberg@mujmail.cz"),
                   ("stickell", "l.stickell@yahoo.it")]



    def getHoster(self):
        page = getURL("http://premium.to/api/hosters.php",
                      get={'username': self.account.username, 'password': self.account.password})
        return [x.strip() for x in page.replace("\"", "").split(";")]

    def coreReady(self):
        self.account = self.core.accountManager.getAccountPlugin("PremiumTo")

        user = self.account.selectAccount()[0]

        if not user:
            self.logError(_("Please add your premium.to account first and restart pyLoad"))
            return

        return MultiHoster.coreReady(self)
