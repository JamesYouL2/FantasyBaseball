# -*- coding: utf-8 -*-
"""Everything this project needs configured before it can run.

Configuration is split by how long a value lives, because that is what decides
how carefully it has to be handled:

    Consumer key and secret   Issued once by Yahoo and never rotated. Written
                              once by init.py and only read from then on, so
                              nothing in the daily path can corrupt them. From
                              $YAHOO_CONSUMER_KEY and $YAHOO_CONSUMER_SECRET,
                              or from the JSON file at $YAHOO_OAUTH_FILE.

    Tokens                    The refresh token lasts until it is revoked; the
                              access token lasts an hour. Both are disposable
                              -- delete the file and `uv run auth.py` mints new
                              ones -- so this is the only file the code writes,
                              and it holds nothing that cannot be replaced.

    League id                 Not a secret, but not public either.
                              $YAHOO_LEAGUE_ID or leagueid.ini.

Keeping the tokens out of the credential file is the point of the split. The
library this replaced kept all four in one file and rewrote the whole thing on
every refresh, which put the consumer secret at risk hourly to save a value
that expires in an hour anyway.

Everything except the example files is gitignored, and each path can be pointed
outside the working tree so nothing sensitive has to sit in the repo at all:

    export YAHOO_OAUTH_FILE=~/.config/fantasybaseball/oauth2yahoo.json
    export YAHOO_TOKEN_FILE=~/.config/fantasybaseball/token.json
    export YAHOO_LEAGUE_ID=123456
"""

import configparser
import json
import os
import stat

DEFAULT_CREDENTIALS_FILE = 'auth/oauth2yahoo.json'
DEFAULT_TOKEN_FILE = 'auth/token.json'
LEAGUE_ID_FILE = 'leagueid.ini'

# Loopback, because a redirect to 127.0.0.1 is the only kind auth.py can catch
# by itself. See auth.py for what happens when the app is registered otherwise.
DEFAULT_REDIRECT_URI = 'http://localhost:8731/callback'


# --- Paths ------------------------------------------------------------------

def credentials_file():
    """Path to the consumer key and secret. Written only by init.py."""
    return os.path.expanduser(
        os.environ.get('YAHOO_OAUTH_FILE', DEFAULT_CREDENTIALS_FILE))


def token_file():
    """Path to the token cache. The only file this project writes."""
    return os.path.expanduser(
        os.environ.get('YAHOO_TOKEN_FILE', DEFAULT_TOKEN_FILE))


def redirect_uri():
    """Where Yahoo sends the authorization code back to.

    This has to match the redirect URI registered on the Yahoo app exactly,
    on both the authorize request and the token exchange, or Yahoo refuses
    the whole request with "invalid redirect uri". $YAHOO_REDIRECT_URI wins;
    otherwise whatever auth.py last settled on and stored beside the
    credentials, so the choice survives without an env var to remember.
    """
    from_env = os.environ.get('YAHOO_REDIRECT_URI')
    if from_env:
        return from_env
    return _read_json(credentials_file()).get('redirect_uri') or DEFAULT_REDIRECT_URI


def save_redirect_uri(value):
    """Remember a redirect URI that Yahoo actually accepts."""
    data = _read_json(credentials_file())
    data['redirect_uri'] = value
    _write_private(credentials_file(), json.dumps(data, indent=2))
    return value


# --- Yahoo credentials ------------------------------------------------------

def client_credentials():
    """The consumer key and secret, from the environment or the JSON file."""
    key = os.environ.get('YAHOO_CONSUMER_KEY')
    secret = os.environ.get('YAHOO_CONSUMER_SECRET')
    if key and secret:
        return key, secret

    path = credentials_file()
    data = _read_json(path)
    key = key or data.get('consumer_key')
    secret = secret or data.get('consumer_secret')
    if key and secret:
        return key, secret

    raise SystemExit(
        f"No Yahoo consumer key and secret. Set up with:\n"
        f"  uv run init.py\n"
        f"Or export YAHOO_CONSUMER_KEY and YAHOO_CONSUMER_SECRET, or copy "
        f"auth/example.json to {path} and fill them in.")


def have_credentials():
    """Whether a key and secret can be found, without failing if they cannot."""
    try:
        client_credentials()
        return True
    except SystemExit:
        return False


def setup_command():
    """The command that fixes a missing setup, given how much is already done.

    Someone holding a key and secret only needs the browser trip. Someone
    holding neither needs to enter them first, and sending them to auth.py
    would just produce a second and more confusing error.
    """
    if have_credentials():
        return "Authorize once with:\n  uv run auth.py"
    return "Set up with:\n  uv run init.py"


# --- Tokens -----------------------------------------------------------------

def read_tokens():
    """The cached tokens, or whatever a previous yahoo_oauth setup left behind.

    yahoo_oauth stored its tokens in the credential file. Picking a refresh
    token up from there means an existing checkout upgrades without a trip
    through the browser; the next write lands in the token cache, and the old
    copy is never read again.
    """
    tokens = _read_json(token_file())
    if tokens.get('refresh_token'):
        return tokens

    inherited = _read_json(credentials_file()).get('refresh_token')
    if inherited:
        # No expiry is recorded, so the access token beside it is treated as
        # already dead and the first call refreshes.
        return {'refresh_token': inherited, 'expires_at': 0}

    raise SystemExit(f"No Yahoo tokens at {token_file()}. {setup_command()}")


def read_tokens_if_any():
    """The cached tokens, or None where their absence is not an error."""
    try:
        return read_tokens()
    except SystemExit:
        return None


def write_tokens(tokens):
    """Write the token cache owner-only and atomically, and return it."""
    _write_private(token_file(), json.dumps(tokens, indent=2))
    return tokens


def discard_tokens():
    """Throw the cached tokens away. True if there were any to throw."""
    try:
        os.remove(token_file())
        return True
    except FileNotFoundError:
        return False


def write_credentials(key, secret):
    """Write the consumer key and secret. Only init.py has cause to call this."""
    path = credentials_file()
    _write_private(path, json.dumps(
        {'consumer_key': key, 'consumer_secret': secret}, indent=2))
    return path


def write_league_id(value):
    """Write leagueid.ini in the form league_id() reads back."""
    _write_private(LEAGUE_ID_FILE, f"[DEFAULT]\nleagueid = {value}\n")
    return LEAGUE_ID_FILE


def _write_private(path, text):
    """Write a file only its owner can read, without ever exposing a partial one.

    Created 0600 rather than chmodded afterwards: a chmod leaves a window in
    which the contents are on disk under the default umask. Written to a
    sibling and renamed, because os.replace is atomic -- an interrupted write
    cannot leave a half-file where the working one used to be.
    """
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    temporary = f'{path}.tmp'
    handle = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                     stat.S_IRUSR | stat.S_IWUSR)
    with os.fdopen(handle, 'w') as out:
        out.write(text)
    os.replace(temporary, path)


def _read_json(path):
    """Parse a JSON file, treating a missing one as empty."""
    try:
        with open(path) as handle:
            return json.load(handle)
    except FileNotFoundError:
        return {}
    except ValueError as error:
        raise SystemExit(f"{path} is not valid JSON: {error}")


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
            f"No league id configured. Set up with:\n"
            f"  uv run init.py\n"
            f"Or set YAHOO_LEAGUE_ID, or copy example.ini to "
            f"{LEAGUE_ID_FILE} and fill in leagueid. Both stay out of git.")
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
