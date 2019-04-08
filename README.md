# FantasyBaseball2019

This project is designed to update a spreadsheet every day with a blend of zips and steamer projections from fangraphs and sync it with a yahoo fantasy baseball league.

It is definitely a work in progress, there are major issues.

To run it, you need to change example.json in the auth folder to oauth2yahoo.json and add a consumer key and consumer secret.

You also need Python and numpy and pandas (I use an anaconda distribution).

You need Firefox and Selenium in Firefox. Once you do that, you can run main.py and you should be fine.

Refer here: https://github.com/yahoo-fantasy/nfl-fantasy-football for reference (copied most of the API handling from here).
