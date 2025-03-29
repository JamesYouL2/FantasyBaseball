import json
from league_authorization import initialize_oauth
from roster import YahooRoster  # gets roster from yahoo api
# runs selenium on fangraphs in firefox to update roster
from createrankings import exportrankings
import configparser

# Adjust this to your league ID
LEAGUE_ID = 33235

config = configparser.ConfigParser()

YahooRoster(leagueid=LEAGUE_ID)

exportrankings(ros=True)
