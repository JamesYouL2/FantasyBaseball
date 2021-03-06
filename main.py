import json
from league_authorization import main as leagueauth
from roster import updateroster #gets roster from yahoo api
from fangraphsdownload import updatefangraphs #runs selenium on fangraphs in firefox to update roster
from createrankings import exportrankings
import configparser

config = configparser.ConfigParser()

config.read('leagueid.ini')

updatefangraphs(link='https://www.fangraphs.com/projections.aspx?pos=all&stats=bat&type=rfangraphsdc&team=0&lg=all&players=0',path='hitters')
updatefangraphs(link='https://www.fangraphs.com/projections.aspx?pos=all&stats=pit&type=rfangraphsdc&team=0&lg=all&players=0',path='pitchers')
updatefangraphs(link='https://www.fangraphs.com/leaders.aspx?pos=all&stats=fld&lg=all&qual=0&type=0&season=2021&month=0&season1=2021&ind=0&team=0&rost=0&age=0&filter=&players=0',path='positions')
updatefangraphs(link='https://www.fangraphs.com/leaders.aspx?pos=all&stats=fld&lg=all&qual=0&type=0&season=2020&month=0&season1=2020&ind=0&team=0&rost=0&age=0&filter=&players=0&startdate=&enddate=',path='positionsold')

with open('./auth/example.json') as json_yahoo_file:
    auths = json.load(json_yahoo_file)
    if 'access_token' not in (list(auths)):
            leagueauth()

updateroster(leagueid=str(config['DEFAULT']['leagueid']),numteams=int(config['DEFAULT']['numteams']))

exportrankings()
