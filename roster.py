# -*- coding: utf-8 -*-
"""
Created on Mon Apr  1 11:56:27 2019

@author: jjy
"""

from yahoologin import yahoologin
import csv

def updateroster(leagueid,numteams,gameid=388):
    oauth = yahoologin()
    with open('./teams/roster.txt', 'w', newline = '') as outfile:        
        csvwriter = csv.writer(outfile, delimiter='\t')
        outfile.truncate()
        csvwriter.writerow(['playerid','team'])
        for team in range(1, numteams+1): #assumes 10-team league
            url = 'https://fantasysports.yahooapis.com/fantasy/v2/team/'+str(gameid)+'.l.'+str(leagueid)+'.t.'+str(team)+'/roster'
            response = oauth.session.get(url, params={'format': 'json'})
            data = response.json()
            playercount = 0
            for item in (data["fantasy_content"]["team"][1]["roster"]["0"]["players"]):
                if 'count' not in item:
                    csvwriter.writerow([data["fantasy_content"]["team"][1]["roster"]["0"]["players"][str(playercount)]["player"][0][1]["player_id"],data["fantasy_content"]["team"][0][2]["name"]])
                    playercount = playercount + 1