import config
from roster import YahooRoster  # gets roster from yahoo api
# fetches the fangraphs projections over http and joins them to the roster
from createrankings import exportrankings

YahooRoster(leagueid=config.league_id()).updateroster()

exportrankings(ros=True)
