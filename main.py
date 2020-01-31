# -*- coding: utf-8 -*-
"""
Created on Wed Apr  3 13:19:21 2019

@author: jjy
"""
import json
from league_authorization import main as leagueauth
from roster import updateroster #gets roster from yahoo api
from fangraphsdownload import updatefangraphs #runs selenium on fangraphs in firefox to update roster
from yahooprojectionsmerge import merge as yahooprojectionsmerge

with open('./auth/example.json') as json_yahoo_file:
    auths = json.load(json_yahoo_file)
    if 'access_token' not in (list(auths)):
            leagueauth()

updateroster(leagueid=,numteams=)
updatefangraphs()

import zipssteamermerge
yahooprojectionsmerge()