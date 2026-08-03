# -*- coding: utf-8 -*-
"""Credential handling for the Yahoo Fantasy API.

The oauth file holds the consumer secret, the access token and the refresh
token, and yahoo_oauth rewrites it in place every time the token is refreshed.
It is the one file in this project that must never reach git.

Set YAHOO_OAUTH_FILE to keep it outside the repo entirely, e.g.

    export YAHOO_OAUTH_FILE=~/.config/fantasybaseball/oauth2yahoo.json
"""

import logging
import os
import stat

DEFAULT_OAUTH_FILE = 'auth/oauth2yahoo.json'

# yahoo_oauth and oauthlib log full token payloads at INFO.
_NOISY_LOGGERS = ('yahoo_oauth', 'oauthlib', 'requests_oauthlib')


def oauth_file():
    """Path to the yahoo_oauth credential file, overridable via env var."""
    return os.path.expanduser(
        os.environ.get('YAHOO_OAUTH_FILE', DEFAULT_OAUTH_FILE))


def silence_token_logging():
    """Stop the oauth libraries from printing tokens to stdout and logs."""
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


def prepare(path=None):
    """Return the credential file path, owner-locked and ready to use."""
    path = path or oauth_file()
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"No Yahoo credentials at {path}. Copy auth/example.json there and "
            f"fill in your consumer key and secret, or point YAHOO_OAUTH_FILE "
            f"at a copy outside this repository.")
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 0600
    except OSError:
        # Windows drives mounted under WSL do not honour POSIX modes.
        pass
    silence_token_logging()
    return path


def shape(data):
    """Describe an API response without echoing league, team or player data.

    Yahoo responses carry team names, manager nicknames and league ids, so the
    full payload must never reach a log file or a pasted traceback.
    """
    if isinstance(data, dict):
        return f"dict(keys={sorted(data)})"
    if isinstance(data, list):
        return f"list(len={len(data)})"
    return type(data).__name__
