# -*- coding: utf-8 -*-
"""Everything this project needs configured before it can run.

Two files hold that configuration, and the split is forced rather than chosen:

    auth/oauth2yahoo.json   Consumer key and secret, plus the access and
                            refresh tokens. yahoo_oauth owns this file's
                            format and rewrites it in place on every token
                            refresh, so it cannot be folded into the ini.

    leagueid.ini            The league id. Not a secret, but not public
                            either, and it should never reach a commit.

Both are gitignored, and either can be pointed outside the working tree with
an environment variable so nothing sensitive has to sit in the repo at all:

    export YAHOO_OAUTH_FILE=~/.config/fantasybaseball/oauth2yahoo.json
    export YAHOO_LEAGUE_ID=123456
"""

import configparser
import logging
import os
import stat

DEFAULT_OAUTH_FILE = 'auth/oauth2yahoo.json'
LEAGUE_ID_FILE = 'leagueid.ini'

# yahoo_oauth and oauthlib log full token payloads at INFO.
_NOISY_LOGGERS = ('yahoo_oauth', 'oauthlib', 'requests_oauthlib')


# --- Yahoo credentials ------------------------------------------------------

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


def consumer_key(env_var="YAHOO_CONSUMER_KEY"):
    """Consumer key from the environment, if you would rather not use a file.

    Unused by the current flow: yahoo_oauth reads the key straight out of
    oauth_file() because it needs to write refreshed tokens back to it.
    """
    return os.environ.get(env_var)


def consumer_secret(env_var="YAHOO_CONSUMER_SECRET"):
    """Consumer secret from the environment. See consumer_key()."""
    return os.environ.get(env_var)


# --- League ----------------------------------------------------------------

def league_id():
    """Read the league id from the environment or leagueid.ini.

    Kept out of source so it never lands in a commit: $YAHOO_LEAGUE_ID wins,
    otherwise leagueid.ini, which is gitignored. Copy example.ini to create it.
    """
    from_env = os.environ.get('YAHOO_LEAGUE_ID')
    if from_env:
        return from_env

    parser = configparser.ConfigParser()
    parser.read(LEAGUE_ID_FILE)
    from_file = parser.get('DEFAULT', 'leagueid', fallback='').strip()
    if not from_file:
        raise SystemExit(
            f"No league id configured. Either set YAHOO_LEAGUE_ID, or "
            f"copy example.ini to {LEAGUE_ID_FILE} and fill in leagueid. "
            f"Both stay out of git.")
    return from_file


# --- Logging helpers -------------------------------------------------------

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
