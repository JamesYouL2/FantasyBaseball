# FantasyBaseball

This project is designed to update a spreadsheet every day with the depth chart projections from fangraphs and sync it with a yahoo fantasy baseball league.

To run it, you need to change example.json in the auth folder to oauth2yahoo.json and add a consumer key and consumer secret.

I actually put a requirements.txt which I think works now.

Also need to put in your league id and the number of teams into a leagueid.ini config file.

Refer here: https://github.com/yahoo-fantasy/nfl-fantasy-football for reference (copied most of the API handling from here).

PlayerIDMap: From Smart Fantasy Baseball. Link here: https://www.smartfantasybaseball.com/tools/
