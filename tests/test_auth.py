# -*- coding: utf-8 -*-
"""Tests for the Yahoo authorization layer.

Nothing here touches the network or a browser. The token endpoint is stubbed,
and the one test that does use a socket talks to auth.py's own redirect server
over loopback, which is the part most worth exercising for real: it is the
only place a browser hands data back to this project.

Every test runs against a temporary credential and token store, so a real
auth/token.json is never read and never overwritten.
"""

import json
import os
import socket
import stat
import threading
import time

import pytest
import requests

import auth
import config
import league_authorization as la

KEY = 'dj0yTESTKEY'
SECRET = 'deadbeef' * 5


@pytest.fixture
def store(tmp_path, monkeypatch):
    """A throwaway credential and token store, isolated from the real one."""
    monkeypatch.setenv('YAHOO_TOKEN_FILE', str(tmp_path / 'token.json'))
    monkeypatch.setenv('YAHOO_OAUTH_FILE', str(tmp_path / 'creds.json'))
    monkeypatch.setenv('YAHOO_CONSUMER_KEY', KEY)
    monkeypatch.setenv('YAHOO_CONSUMER_SECRET', SECRET)
    # The module caches tokens for the life of a process; each test gets a
    # clean one, and monkeypatch puts the original back afterwards.
    monkeypatch.setattr(la, '_tokens', None)
    return tmp_path


def stub_token_endpoint(monkeypatch, response):
    """Replace the token endpoint and record what was posted to it."""
    calls = []

    def post(url, auth=None, data=None, timeout=None):
        calls.append({'url': url, 'auth': auth, 'data': data})
        return response

    monkeypatch.setattr(la.requests, 'post', post)
    return calls


class Response:
    """Just enough of a requests response for the token code to read."""

    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code
        self.ok = status_code < 400

    def json(self):
        return self.payload

    def raise_for_status(self):
        if not self.ok:
            raise requests.HTTPError(self.status_code)


def granted(access_token='FRESH', refresh_token='R', expires_in=3600):
    return Response({'access_token': access_token,
                     'refresh_token': refresh_token,
                     'expires_in': expires_in})


# --- The token cache --------------------------------------------------------

def test_token_cache_roundtrips(store):
    config.write_tokens({'access_token': 'A', 'refresh_token': 'R',
                         'expires_at': 9e9})
    assert config.read_tokens()['refresh_token'] == 'R'


def test_token_file_is_owner_only_and_leaves_no_temp_file(store):
    config.write_tokens({'access_token': 'A', 'refresh_token': 'R',
                         'expires_at': 9e9})
    mode = stat.S_IMODE(os.stat(config.token_file()).st_mode)
    assert mode == 0o600, f"tokens are readable by others: {oct(mode)}"
    assert not os.path.exists(config.token_file() + '.tmp')


def test_credentials_file_is_never_written(store):
    """The consumer secret must survive anything the token path does."""
    original = {'consumer_key': 'K', 'consumer_secret': 'S'}
    with open(config.credentials_file(), 'w') as out:
        json.dump(original, out)

    config.write_tokens({'access_token': 'A', 'refresh_token': 'R',
                         'expires_at': 9e9})

    with open(config.credentials_file()) as handle:
        assert json.load(handle) == original


# --- Normalising a token response ------------------------------------------

def test_expires_in_becomes_a_deadline():
    tokens = la.tokens_from({'access_token': 'A', 'expires_in': '3600'}, 'R')
    assert 3500 < tokens['expires_at'] - time.time() < 3700


def test_refresh_token_is_kept_when_the_response_omits_it():
    tokens = la.tokens_from({'access_token': 'A', 'expires_in': 3600}, 'R')
    assert tokens['refresh_token'] == 'R'


def test_refresh_token_is_replaced_when_the_response_rotates_it():
    tokens = la.tokens_from(
        {'access_token': 'A', 'refresh_token': 'R2', 'expires_in': 3600}, 'R')
    assert tokens['refresh_token'] == 'R2'


# --- Refreshing -------------------------------------------------------------

def test_expiring_token_is_refreshed_and_persisted(store, monkeypatch):
    calls = stub_token_endpoint(monkeypatch, granted())
    # Inside the expiry margin: still valid, but not for long enough to use.
    config.write_tokens({'access_token': 'STALE', 'refresh_token': 'R',
                         'expires_at': time.time() + 10})

    assert la.access_token() == 'FRESH'
    assert calls[0]['url'] == la.TOKEN_URL
    assert calls[0]['auth'] == (KEY, SECRET), "not authenticated as the client"
    assert calls[0]['data']['grant_type'] == 'refresh_token'

    with open(config.token_file()) as handle:
        assert json.load(handle)['access_token'] == 'FRESH'


def test_a_run_refreshes_at_most_once(store, monkeypatch):
    calls = stub_token_endpoint(monkeypatch, granted())
    config.write_tokens({'access_token': 'STALE', 'refresh_token': 'R',
                         'expires_at': 0})

    for _ in range(5):
        la.access_token()

    assert len(calls) == 1, f"hit the token endpoint {len(calls)} times"


def test_valid_token_is_reused(store, monkeypatch):
    calls = stub_token_endpoint(monkeypatch, granted())
    config.write_tokens({'access_token': 'GOOD', 'refresh_token': 'R',
                         'expires_at': time.time() + 3600})

    assert la.access_token() == 'GOOD'
    assert not calls, "refreshed a token that was still good"


def test_session_attaches_the_bearer_header_per_request(store, monkeypatch):
    config.write_tokens({'access_token': 'GOOD', 'refresh_token': 'R',
                         'expires_at': time.time() + 3600})
    seen = {}

    def capture(self, method, url, **kwargs):
        seen['authorization'] = self.headers.get('Authorization')

    monkeypatch.setattr(requests.Session, 'request', capture)
    la.session().get('https://example.invalid')

    assert seen['authorization'] == 'Bearer GOOD'


# --- Failing without hanging ------------------------------------------------

def test_revoked_refresh_token_exits_with_the_fix(store, monkeypatch):
    stub_token_endpoint(monkeypatch,
                        Response({'error': 'invalid_grant'}, status_code=400))
    config.write_tokens({'access_token': 'X', 'refresh_token': 'DEAD',
                         'expires_at': 0})

    with pytest.raises(SystemExit) as raised:
        la.access_token()

    assert 'invalid_grant' in str(raised.value)
    assert 'auth.py' in str(raised.value), "does not say how to recover"
    assert 'DEAD' not in str(raised.value), "leaked the token into the error"


def test_missing_tokens_exit_rather_than_prompt(store):
    """A scheduled run must fail loudly, never block on a terminal."""
    with pytest.raises(SystemExit) as raised:
        la.access_token()
    assert 'auth.py' in str(raised.value)


def test_missing_tokens_with_credentials_point_at_auth(store):
    """Credentials in hand means only the browser trip is missing."""
    with pytest.raises(SystemExit) as raised:
        config.read_tokens()

    message = str(raised.value)
    assert 'auth.py' in message
    assert 'init.py' not in message, "would make them re-enter a secret they have"


def test_missing_everything_points_at_init(store, monkeypatch):
    """A fresh checkout must not be sent to auth.py, which would fail again."""
    monkeypatch.delenv('YAHOO_CONSUMER_KEY')
    monkeypatch.delenv('YAHOO_CONSUMER_SECRET')

    with pytest.raises(SystemExit) as raised:
        config.read_tokens()

    assert 'init.py' in str(raised.value)


def test_missing_credentials_point_at_init(store, monkeypatch):
    monkeypatch.delenv('YAHOO_CONSUMER_KEY')
    monkeypatch.delenv('YAHOO_CONSUMER_SECRET')

    with pytest.raises(SystemExit) as raised:
        config.client_credentials()

    assert 'init.py' in str(raised.value)


def test_missing_league_id_points_at_init(store, monkeypatch, tmp_path):
    monkeypatch.delenv('YAHOO_LEAGUE_ID', raising=False)
    monkeypatch.chdir(tmp_path)          # no leagueid.ini here

    with pytest.raises(SystemExit) as raised:
        config.league_id()

    assert 'init.py' in str(raised.value)


def test_missing_credentials_name_what_to_set(store, monkeypatch):
    monkeypatch.delenv('YAHOO_CONSUMER_KEY')
    monkeypatch.delenv('YAHOO_CONSUMER_SECRET')
    with pytest.raises(SystemExit) as raised:
        config.client_credentials()
    assert 'YAHOO_CONSUMER_KEY' in str(raised.value)


# --- Upgrading from yahoo_oauth --------------------------------------------

def test_refresh_token_is_inherited_from_a_yahoo_oauth_file(store, monkeypatch):
    monkeypatch.delenv('YAHOO_CONSUMER_KEY')
    monkeypatch.delenv('YAHOO_CONSUMER_SECRET')
    with open(config.credentials_file(), 'w') as out:
        json.dump({'consumer_key': 'K', 'consumer_secret': 'S',
                   'access_token': 'old', 'refresh_token': 'LEGACY'}, out)

    tokens = config.read_tokens()

    assert tokens['refresh_token'] == 'LEGACY', "an existing setup must not " \
        "have to re-authorize through the browser"
    assert tokens['expires_at'] == 0, "the inherited access token must be " \
        "treated as dead, since no expiry came with it"
    assert config.client_credentials() == ('K', 'S')


# --- auth.py: which flow a redirect URI gets --------------------------------

@pytest.mark.parametrize('redirect, expected', [
    ('http://localhost:8731/callback', ('localhost', 8731)),
    ('http://127.0.0.1:9000/cb', ('127.0.0.1', 9000)),
    ('https://localhost:8731/cb', None),      # would need a trusted certificate
    ('https://example.com/cb', None),         # not ours to listen on
    ('oob', None),
])
def test_only_plain_http_loopback_is_served(redirect, expected):
    assert auth.loopback_address(redirect) == expected


@pytest.mark.parametrize('pasted, expected', [
    ('https://example.com/cb?code=ABC&state=x', 'ABC'),
    ('https://example.com/cb?state=x&code=ABC', 'ABC'),
    ('ABC', 'ABC'),
])
def test_code_is_read_from_a_pasted_url_or_taken_bare(pasted, expected):
    assert auth.code_from(pasted) == expected


@pytest.mark.parametrize('pasted', ['', 'https://example.com/cb?state=x'])
def test_junk_paste_is_rejected(pasted):
    with pytest.raises(SystemExit):
        auth.code_from(pasted)


# --- auth.py: the redirect server, over a real socket -----------------------

@pytest.fixture
def loopback(monkeypatch):
    """A free loopback port, with the browser and the timeout neutralised."""
    monkeypatch.setattr(auth.webbrowser, 'open', lambda url: None)
    monkeypatch.setattr(auth, 'REDIRECT_TIMEOUT_SECONDS', 15)
    monkeypatch.setattr(auth.RedirectHandler, 'query', None)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return '127.0.0.1', probe.getsockname()[1]


def catch_in_background(loopback, state):
    """Run catch_redirect off-thread and hand back a getter for its outcome."""
    outcome = {}

    def run():
        try:
            outcome['code'] = auth.catch_redirect(loopback, 'http://unused', state)
        except SystemExit as error:
            outcome['error'] = str(error)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    for _ in range(100):                      # wait for the socket to be up
        try:
            requests.get(f'http://{loopback[0]}:{loopback[1]}/ping', timeout=1)
            break
        except requests.RequestException:
            time.sleep(0.05)
    return thread, outcome


def test_redirect_is_captured_despite_an_unrelated_request(loopback):
    thread, outcome = catch_in_background(loopback, 'STATE123')
    host, port = loopback

    requests.get(f'http://{host}:{port}/favicon.ico', timeout=5)
    response = requests.get(
        f'http://{host}:{port}/callback?code=REAL&state=STATE123', timeout=5)
    thread.join(timeout=20)

    assert outcome.get('code') == 'REAL'
    assert response.status_code == 200
    assert 'close this tab' in response.text


def test_redirect_with_the_wrong_state_is_refused(loopback):
    thread, outcome = catch_in_background(loopback, 'STATE123')
    host, port = loopback

    requests.get(f'http://{host}:{port}/callback?code=EVIL&state=WRONG',
                 timeout=5)
    thread.join(timeout=20)

    assert 'code' not in outcome, "accepted a redirect it did not initiate"
    assert 'state' in outcome.get('error', '')


def test_yahoo_refusing_authorization_is_reported(loopback):
    thread, outcome = catch_in_background(loopback, 'STATE123')
    host, port = loopback

    requests.get(f'http://{host}:{port}/callback?error=access_denied', timeout=5)
    thread.join(timeout=20)

    assert 'access_denied' in outcome.get('error', '')
