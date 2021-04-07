# FantasyBaseball

This project is designed to update a spreadsheet every day with the depth chart projections from fangraphs and sync it with a yahoo fantasy baseball league.

To run it, you need to change example.json in the auth folder to oauth2yahoo.json and add a consumer key and consumer secret.

You also need Python and numpy and pandas (I really should add a requirements.txt).

You need Firefox and Selenium in Chrome. Once you do that, you can run main.py and you should be fine.

Also need to put in your league id and the number of teams into a leagueid.ini config file.

Refer here: https://github.com/yahoo-fantasy/nfl-fantasy-football for reference (copied most of the API handling from here).

PlayerIDMap: From Smart Fantasy Baseball.
