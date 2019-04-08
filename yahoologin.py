# -*- coding: utf-8 -*-
"""
Created on Mon Apr  1 11:42:30 2019

@author: jjy
"""

import json
from Yahoo_Api import Yahoo_Api

def yahoologin():
    # Yahoo Keys
    with open('./auth/oauth2yahoo.json') as json_yahoo_file:
        auths = json.load(json_yahoo_file)
    yahoo_consumer_key = auths['consumer_key']
    yahoo_consumer_secret = auths['consumer_secret']
    yahoo_access_key = auths['access_token']
    yahoo_api = Yahoo_Api(yahoo_consumer_key, yahoo_consumer_secret, yahoo_access_key)#, yahoo_access_secret)
    return yahoo_api._login()
    