from yahoo_oauth import OAuth2
from loguru import logger
import os

import credentials


def get_consumer_key(env_var="YAHOO_CONSUMER_KEY"):
    # Load consumer key and secret from environment variables or set them directly
    consumer_key = os.environ.get(env_var)
    return consumer_key


def get_consumer_secret(env_var="YAHOO_CONSUMER_SECRET"):
    consumer_secret = os.environ.get(env_var)
    return consumer_secret


def initialize_oauth_file(
    file_path=None,
):
    # credentials.prepare locks the file to 0600 and silences the oauth
    # libraries, which otherwise log token payloads at INFO. Defaults to
    # auth/oauth2yahoo.json, or $YAHOO_OAUTH_FILE to keep it out of the repo.
    file_path = credentials.prepare(file_path)
    oauth = OAuth2(None, None, from_file=file_path)
    if not oauth.token_is_valid():
        oauth.refresh_access_token()
    return oauth
