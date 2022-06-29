import json
from turtle import update
from league_authorization import main as leagueauth
from roster import updateroster  # gets roster from yahoo api
# runs selenium on fangraphs in firefox to update roster
from fangraphsdownload import updatefangraphs
from createrankings import exportrankings
import configparser

config = configparser.ConfigParser()

config.read('leagueid.ini')

link_dict = {
    'hitters': 'https://www.fangraphs.com/projections.aspx?pos=all&stats=bat&type=rthebatx&team=0&lg=all&players=0',
    'pitchers': 'https://www.fangraphs.com/projections.aspx?pos=all&stats=pit&type=rthebat&team=0&lg=all&players=0',
    'positions': 'https://www.fangraphs.com/leaders.aspx?pos=all&stats=fld&lg=all&qual=0&type=0&season=2022&month=0&season1=2022&ind=0&team=0&rost=0&age=0&filter=&players=0'
}

for path, link in link_dict.items():
    try:
        updatefangraphs(link=link, path=path, debug=False)
    except Exception as e:
        print("Exception", e)
        updatefangraphs(link=link,path=path,debug=True)
#updatefangraphs(link='https://www.fangraphs.com/leaders.aspx?pos=all&stats=fld&lg=all&qual=0&type=0&season=2021&month=0&season1=2021&ind=0&team=&rost=&age=&filter=&players=&startdate=&enddate=', path='positionsold', debug=True)

with open('./auth/example.json') as json_yahoo_file:
    auths = json.load(json_yahoo_file)
    if 'access_token' not in (list(auths)):
        leagueauth()

updateroster(leagueid=str(config['DEFAULT']['leagueid']), numteams=int(
    config['DEFAULT']['numteams']))

exportrankings()
