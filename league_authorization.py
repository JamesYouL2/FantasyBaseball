from yahoo_oauth import OAuth2

import config


def initialize_oauth_file(
    file_path=None,
):
    # config.prepare locks the file to 0600 and silences the oauth libraries,
    # which otherwise log token payloads at INFO. Defaults to
    # auth/oauth2yahoo.json, or $YAHOO_OAUTH_FILE to keep it out of the repo.
    file_path = config.prepare(file_path)
    oauth = OAuth2(None, None, from_file=file_path)
    if not oauth.token_is_valid():
        oauth.refresh_access_token()
    return oauth
