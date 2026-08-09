# -*- coding: utf-8 -*-
"""
Created on Mon Apr  1 11:56:27 2019

@author: jjy
"""

import csv
import os
from loguru import logger
from league_authorization import session
from config import shape

class YahooRoster:
    def __init__(self, leagueid):
        self.leagueid = leagueid
        self.session = session()

    def getgameid(self, game='mlb'):
        url = 'https://fantasysports.yahooapis.com/fantasy/v2/game/' + game
        response = self.session.get(url, params={'format': 'json'})
        data = response.json()
        return data['fantasy_content']['game'][0]['game_id']

    def _get_team_keys(self, leagueid):
        gameid = self.getgameid()
        url = f'https://fantasysports.yahooapis.com/fantasy/v2/league/{str(gameid)}.l.{str(leagueid)}/standings'
        response = self.session.get(url, params={'format': 'json'})
        data = response.json()
        team_list = list()
        try:
            for i in data['fantasy_content']['league'][1]['standings'][0]['teams']:
                if i == 'count':
                    continue
                team_key=data['fantasy_content']['league'][1]['standings'][0]['teams'][f"{str(i)}"]['team'][0][0]['team_key']
                team_list.append(team_key)
        except Exception as e:
            logger.error("Could not read standings for the configured league")
            logger.error(f"Response shape: {shape(data)}")
            raise e
        return team_list

    def updateroster(self):
        gameid = self.getgameid()
        logger.info(f"Game ID: {gameid}")

        team_list = self._get_team_keys(self.leagueid)

        self.createfolder()
        with open('./teams/roster.txt', 'w+', newline = '') as outfile:
            csvwriter = csv.writer(outfile, delimiter='\t')
            outfile.truncate()
            csvwriter.writerow(['playerid','player_name','team','percent_owned'])
            for team in team_list:
                url = f'https://fantasysports.yahooapis.com/fantasy/v2/team/{str(team)}/players/percent_owned'
                response = self.session.get(url, params={'format': 'json'})
                data = response.json()
                playercount = 0
                try:
                    for item in (data["fantasy_content"]["team"][1]["players"]):
                        if 'count' not in item:
                            # Reset per player: bound inside the try below, it
                            # would otherwise be undefined for the first player
                            # missing percent_owned, and carry the previous
                            # player's number for every one after that.
                            percentowned = ''
                            try:
                                percentowned = data["fantasy_content"]["team"][1]["players"][str(playercount)]["player"][1]['percent_owned'][1]['value']
                            except (KeyError, IndexError, TypeError):
                                logger.warning(f"No percent_owned for entry {shape(item)}")
                            finally:
                                    row = [data["fantasy_content"]["team"][1]["players"][str(playercount)]["player"][0][1]["player_id"],data["fantasy_content"]["team"][1]["players"][str(playercount)]["player"][0][2]["name"]["full"],data["fantasy_content"]["team"][0][2]["name"],percentowned]
                                    #print(row)
                                    csvwriter.writerow(row)
                                    playercount = playercount + 1
                except KeyError as e:
                    logger.error("Could not read the roster for a team")
                    logger.error(f"Response shape: {shape(data)}")
                    raise e

    def createfolder(self):
        path = "teams"
        # Check whether the specified path exists or not
        isExist = os.path.exists(path)
        if not isExist:
        # Create a new directory because it does not exist
            os.makedirs(path)
            print("The new directory is created!")
