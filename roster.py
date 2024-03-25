# -*- coding: utf-8 -*-
"""
Created on Mon Apr  1 11:56:27 2019

@author: jjy
"""

from yahoologin import yahoologin
import csv
import os
import logging

def getgameid(game='mlb'):
    oauth = yahoologin()
    url = 'https://fantasysports.yahooapis.com/fantasy/v2/game/' + game
    response = oauth.session.get(url, params={'format': 'json'})
    data = response.json()
    return data['fantasy_content']['game'][0]['game_id']

def _get_team_keys(leagueid):
    oauth = yahoologin()
    gameid = getgameid()
    url = f'https://fantasysports.yahooapis.com/fantasy/v2/league/{str(gameid)}.l.{str(leagueid)}/standings'
    response = oauth.session.get(url, params={'format': 'json'})
    data = response.json()
    team_list = list()
    try:
        for i in data['fantasy_content']['league'][1]['standings'][0]['teams']:
            if i == 'count':
                continue
            team_key=data['fantasy_content']['league'][1]['standings'][0]['teams'][f"{str(i)}"]['team'][0][0]['team_key']    
            team_list.append(team_key)
    except Exception as e:
        logging.error(f"Error in url: {url}")
        logging.error(f"Error in Data: {data}")
        raise e
    return team_list

def updateroster(leagueid,numteams):
    oauth = yahoologin()
    gameid = getgameid()
    logging.info(f"Game ID: {gameid}")
    team_list = _get_team_keys(leagueid)

    createfolder()
    with open('./teams/roster.txt', 'w+', newline = '') as outfile:        
        csvwriter = csv.writer(outfile, delimiter='\t')
        outfile.truncate()
        csvwriter.writerow(['playerid','player_name','team','percent_owned'])
        for team in team_list:
            url = f'https://fantasysports.yahooapis.com/fantasy/v2/team/{str(team)}/players/percent_owned'
            response = oauth.session.get(url, params={'format': 'json'})
            data = response.json()
            playercount = 0
            try:
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
            except KeyError as e:
                logging.error(f"Error in Data: {data}")
                raise e

def createfolder():
    path = "teams"
    # Check whether the specified path exists or not
    isExist = os.path.exists(path)
    if not isExist:
    # Create a new directory because it does not exist
        os.makedirs(path)
        print("The new directory is created!")
