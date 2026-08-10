# -*- coding: utf-8 -*-
"""
Created on Mon Apr  1 11:56:27 2019

@author: jjy
"""

import csv
import os
from loguru import logger
from league_authorization import session
import config
from config import shape


class YahooAPIError(RuntimeError):
    """A Yahoo API call that failed, reported with what to do about it."""


def _yahoo_error(response):
    """The description out of a Yahoo error body, without the rest of it."""
    try:
        return response.json()['error']['description']
    except (ValueError, KeyError, TypeError):
        return response.text[:200].strip() or '(no detail)'


class YahooRoster:
    def __init__(self, leagueid):
        self.leagueid = leagueid
        self.session = session()

    def _get(self, url):
        """One Yahoo API call, with the failures named rather than left to bite.

        Without this, a refusal returns a JSON error body and the first
        subscript reads it as a missing key -- so a permissions problem
        surfaces as `KeyError: 'fantasy_content'`, which points at the payload
        shape rather than at the account setting actually at fault.
        """
        response = self.session.get(url, params={'format': 'json'})

        if response.status_code == 401:
            raise YahooAPIError(
                f"Yahoo rejected the access token (401): "
                f"{_yahoo_error(response)}\n"
                f"  Re-authorize with: uv run auth.py")

        if response.status_code == 403:
            raise YahooAPIError(
                f"Yahoo refused the request (403): {_yahoo_error(response)}\n"
                f"\n"
                f"The token itself is fine -- Yahoo answers an invalid one with "
                f"401, not 403 -- and this survives a fresh authorization.\n"
                f"\n"
                f"Yahoo moved the Fantasy Sports API behind an approval process. "
                f"It is no longer self-serve: Fantasy Sports is gone from the "
                f"permission list when creating an app, and an app that still "
                f"lists it from before can pass authorization and be refused "
                f"here. Request access at:\n"
                f"  https://sports.yahoo.com/developer/access/\n"
                f"\n"
                f"Keep the existing app. Its client id is what the form asks "
                f"for, and a new one cannot be given this permission.\n"
                f"\n"
                f"If access was already granted, the token may predate it: "
                f"re-run `uv run auth.py` (it asks for {config.scope()}).")

        if not response.ok:
            raise YahooAPIError(
                f"Yahoo returned {response.status_code} for "
                f"{url.split('/v2/')[-1]}: {_yahoo_error(response)}")

        try:
            return response.json()
        except ValueError:
            raise YahooAPIError(
                f"Yahoo returned "
                f"{response.headers.get('Content-Type', 'an unknown type')} "
                f"rather than JSON for {url.split('/v2/')[-1]}, starting: "
                f"{response.text[:200]!r}")

    def getgameid(self, game='mlb'):
        url = 'https://fantasysports.yahooapis.com/fantasy/v2/game/' + game
        data = self._get(url)
        return data['fantasy_content']['game'][0]['game_id']

    def _get_team_keys(self, leagueid):
        gameid = self.getgameid()
        url = f'https://fantasysports.yahooapis.com/fantasy/v2/league/{str(gameid)}.l.{str(leagueid)}/standings'
        data = self._get(url)
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
                data = self._get(url)
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
