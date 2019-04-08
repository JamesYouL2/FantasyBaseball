# -*- coding: utf-8 -*-
"""
Created on Wed Apr  3 13:19:21 2019

@author: jjy
"""

from roster import updateroster #gets roster from yahoo api
from fangraphsdownload import updatefangraphs #runs selenium on fangraphs in firefox to update roster

updateroster(leagueid=,numteams=)
updatefangraphs()

import zipssteamermerge
import yahooprojectionsmerge