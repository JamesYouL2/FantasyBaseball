import config
from roster import YahooRoster  # gets roster from yahoo api
# runs selenium on fangraphs in firefox to update roster
from createrankings import exportrankings

YahooRoster(leagueid=config.league_id()).updateroster()

exportrankings(ros=True)
