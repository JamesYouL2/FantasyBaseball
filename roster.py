# -*- coding: utf-8 -*-
"""
Created on Mon Apr  1 11:56:27 2019

@author: jjy
"""

from yahoologin import yahoologin
import csv

def getgameid(game='mlb'):
    oauth = yahoologin()
    url = 'https://fantasysports.yahooapis.com/fantasy/v2/game/' + game
    response = oauth.session.get(url, params={'format': 'json'})
    data = response.json()
    return data['fantasy_content']['game'][0]['game_id']

def updateroster(leagueid,numteams):
    oauth = yahoologin()
    gameid = getgameid()
    with open('./teams/roster.txt', 'w+', newline = '') as outfile:        
        csvwriter = csv.writer(outfile, delimiter='\t')
        outfile.truncate()
        csvwriter.writerow(['playerid','player_name','team','percent_owned'])
        for team in range(1, numteams+1): #assumes 10-team league
            #print(url)
            url = 'https://fantasysports.yahooapis.com/fantasy/v2/team/'+str(gameid)+'.l.'+str(leagueid)+'.t.'+str(team)+'/players/percent_owned'
            response = oauth.session.get(url, params={'format': 'json'})
            data = response.json()
            playercount = 0
            for item in (data["fantasy_content"]["team"][1]["players"]):
                if 'count' not in item:
                    try:
                        percentowned = data["fantasy_content"]["team"][1]["players"][str(playercount)]["player"][1]['percent_owned'][1]['value']
                    except:
                        print(str(playercount),numteams)
                    finally:
                            row = [data["fantasy_content"]["team"][1]["players"][str(playercount)]["player"][0][1]["player_id"],data["fantasy_content"]["team"][1]["players"][str(playercount)]["player"][0][2]["name"]["full"],data["fantasy_content"]["team"][0][2]["name"],percentowned]
                            #print(row)
                            csvwriter.writerow(row)
                            playercount = playercount + 1