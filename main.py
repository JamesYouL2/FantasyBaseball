import json
from league_authorization import initialize_oauth
from roster import YahooRoster  # gets roster from yahoo api
# runs selenium on fangraphs in firefox to update roster
from createrankings import exportrankings
import configparser

config = configparser.ConfigParser()

YahooRoster(leagueid=str(config['DEFAULT']['leagueid']))

exportrankings(ros=True)
