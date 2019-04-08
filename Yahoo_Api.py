# -*- coding: utf-8 -*-
"""
Created on Mon Apr  1 10:42:47 2019

@author: jjy
"""
from yahoo_oauth import OAuth2

class Yahoo_Api():
    def __init__(self, consumer_key, consumer_secret,
                access_key):
        self._consumer_key = consumer_key
        self._consumer_secret = consumer_secret
        self._access_key = access_key
        self._authorization = None
    def _login(self):
        global oauth
        oauth = OAuth2(None, None, from_file='./auth/oauth2yahoo.json')
        if not oauth.token_is_valid():
            oauth.refresh_access_token()
        return oauth
