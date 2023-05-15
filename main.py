import json
from turtle import update
from league_authorization import main as leagueauth
from roster import updateroster  # gets roster from yahoo api
# runs selenium on fangraphs in firefox to update roster
from createrankings import exportrankings
import configparser

config = configparser.ConfigParser()

config.read('leagueid.ini')

with open('./auth/example.json') as json_yahoo_file:
    auths = json.load(json_yahoo_file)
    if 'access_token' not in (list(auths)):
        leagueauth()

updateroster(leagueid=str(config['DEFAULT']['leagueid']), numteams=int(
    config['DEFAULT']['numteams']))

exportrankings()
