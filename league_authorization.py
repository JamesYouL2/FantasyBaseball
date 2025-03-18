from yahoo_oauth import OAuth2
import json
import os
from loguru import logger

class Yahoo_Api():
    def __init__(self,
                 consumer_key,
                 consumer_secret
                ):
        self._consumer_key = consumer_key
        self._consumer_secret = consumer_secret
        self._authorization = None
        
    def _login(self):
        global oauth
        oauth = OAuth2(None, None, from_file='./auth/oauth2yahoo.json')
        if not oauth.token_is_valid():
            oauth.refresh_access_token()

class Authorize():
    def AuthorizeLeague(self):
        # UPDATE LEAGUE GAME ID
        yahoo_api._login()
        url = 'https://fantasysports.yahooapis.com/fantasy/v2/league/380.l.XXXXXX/transactions'
        response = oauth.session.get(url, params={'format': 'json'})
        r = response.json()
        logger.info(r)
        
class Bot():
    def __init__(self, yahoo_api):
        self._yahoo_api = yahoo_api
    def run(self):
        # Data Updates
        at = Authorize()
        at.AuthorizeLeague()
        logger.info('Authorization Complete')

def get_token():
    with open('./auth/oauth2yahoo.json') as json_yahoo_file:
        auths = json.load(json_yahoo_file)
    yahoo_consumer_key = auths['consumer_key']
    yahoo_consumer_secret = auths['consumer_secret']
    json_yahoo_file.close()
    return yahoo_consumer_key, yahoo_consumer_secret

def main():
    yahoo_consumer_key, yahoo_consumer_secret = get_token()
    global yahoo_api
    yahoo_api = Yahoo_Api(yahoo_consumer_key, yahoo_consumer_secret,)
    bot = Bot(yahoo_api)
    bot.run()

if __name__ == "__main__":
    main()
