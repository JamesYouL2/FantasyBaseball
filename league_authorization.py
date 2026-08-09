# -*- coding: utf-8 -*-
"""The Yahoo session every run uses. Never prompts, never opens a browser.

Authorization is a one-time event and lives in auth.py. This module only
spends what auth.py produced: it trades the refresh token for an access token
whenever the current one is close to expiring, and hands back an ordinary
requests session with the bearer header attached.

The separation is the safety property, not a tidiness one. The library this
replaced would fall through to an input() prompt whenever it found no valid
token, which in a scheduled run means hanging on a terminal nobody is watching.
Nothing reachable from here can block: a missing or rejected refresh token
raises, and says which command fixes it.
"""

import time

import requests

import config

TOKEN_URL = 'https://api.login.yahoo.com/oauth2/get_token'

# Yahoo access tokens last an hour. Renew a minute early so that a token cannot
# expire in the gap between the check and the request it was fetched for.
EXPIRY_MARGIN_SECONDS = 60

# Process-wide, so a run refreshes at most once however many calls it makes.
_tokens = None


class YahooSession(requests.Session):
    """A requests session whose bearer token cannot go stale underneath it.

    The header is resolved per request rather than fixed at construction. A
    session built at the start of a long run would otherwise be carrying a
    dead token by the end of it, and the failure would land in the middle of
    the work rather than before any of it.
    """

    def request(self, method, url, **kwargs):
        self.headers['Authorization'] = f'Bearer {access_token()}'
        return super().request(method, url, **kwargs)


def session():
    """A requests session authorized against the Yahoo Fantasy API."""
    return YahooSession()


def access_token():
    """A currently valid access token, refreshed if this one is about to go."""
    global _tokens
    if _tokens is None:
        _tokens = config.read_tokens()
    if time.time() >= _tokens.get('expires_at', 0) - EXPIRY_MARGIN_SECONDS:
        _tokens = config.write_tokens(refresh(_tokens['refresh_token']))
    return _tokens['access_token']


def refresh(refresh_token):
    """Exchange the refresh token for a new access token."""
    key, secret = config.client_credentials()
    response = requests.post(
        TOKEN_URL,
        auth=(key, secret),
        data={
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'redirect_uri': config.redirect_uri(),
        },
        timeout=30)

    if response.status_code in (400, 401):
        raise SystemExit(
            f"Yahoo rejected the refresh token ({error_code(response)}). It has "
            f"been revoked, or the consumer key and secret no longer match the "
            f"account that granted it.\n"
            f"  Re-authorize with: uv run auth.py")
    response.raise_for_status()
    return tokens_from(response.json(), refresh_token)


def tokens_from(payload, previous_refresh_token=None):
    """Normalise a Yahoo token response into what the cache stores.

    expires_in is a duration, and a duration only means something next to the
    moment it was measured from. Storing the deadline instead keeps the
    arithmetic here, where the response actually arrived, rather than leaving
    every later reader to reconstruct it.

    A refresh response does not always carry a new refresh token, and the old
    one stays good when it does not, so it is kept unless replaced.
    """
    return {
        'access_token': payload['access_token'],
        'refresh_token': payload.get('refresh_token') or previous_refresh_token,
        'expires_at': time.time() + int(payload.get('expires_in', 3600)),
    }


def error_code(response):
    """The error field of a failed token response, without the payload.

    A token endpoint's error body is not supposed to carry credentials, but it
    is one field away from things that do, so only the code is ever quoted.
    """
    try:
        return response.json().get('error', response.status_code)
    except ValueError:
        return response.status_code
