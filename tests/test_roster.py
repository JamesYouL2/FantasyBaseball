# -*- coding: utf-8 -*-
"""Tests for how roster.py reports a Yahoo API call that fails.

The case that motivated these: a 403 used to surface as
`KeyError: 'fantasy_content'`, which names the payload rather than the account
setting actually at fault, and sends you reading response shapes instead of
app permissions.
"""

import json

import pytest

import config
import roster


class Response:
    def __init__(self, status_code=200, payload=None, text=None, content_type='application/json'):
        self.status_code = status_code
        self.ok = status_code < 400
        self._payload = payload
        self.text = text if text is not None else json.dumps(payload or {})
        self.headers = {'Content-Type': content_type}

    def json(self):
        if self._payload is None:
            raise ValueError('not json')
        return self._payload


def yahoo_says(monkeypatch, response):
    """A YahooRoster whose every call returns one canned response."""
    monkeypatch.setattr(roster, 'session', lambda: None)
    instance = roster.YahooRoster(leagueid='1')
    monkeypatch.setattr(instance, 'session',
                        type('S', (), {'get': lambda self, url, params=None: response})())
    return instance


def refusal(status_code, description):
    return Response(status_code, {'error': {'description': description}})


# --- The failure that started this ------------------------------------------

def test_403_names_permissions_not_the_payload(monkeypatch):
    api = yahoo_says(monkeypatch, refusal(
        403, 'This application is not authorized to perform this action.'))

    with pytest.raises(roster.YahooAPIError) as raised:
        api.getgameid()

    message = str(raised.value)
    assert 'This application is not authorized' in message
    assert 'developer.yahoo.com' in message
    assert 'Fantasy Sports' in message


def test_403_says_the_token_must_be_reminted(monkeypatch):
    """Changing the app permission does not upgrade an already-issued grant."""
    api = yahoo_says(monkeypatch, refusal(403, 'not authorized'))

    with pytest.raises(roster.YahooAPIError) as raised:
        api.getgameid()

    message = str(raised.value)
    assert config.token_file() in message
    assert 'auth.py' in message


def test_403_does_not_send_you_to_re_login(monkeypatch):
    """A 403 is not a login problem, and saying so would waste the next hour."""
    api = yahoo_says(monkeypatch, refusal(403, 'not authorized'))

    with pytest.raises(roster.YahooAPIError) as raised:
        api.getgameid()

    assert '401' in str(raised.value), "should explain why this is not a token problem"


# --- The other ways a call fails --------------------------------------------

def test_401_points_at_re_authorizing(monkeypatch):
    api = yahoo_says(monkeypatch, refusal(401, 'Please provide valid credentials'))

    with pytest.raises(roster.YahooAPIError) as raised:
        api.getgameid()

    message = str(raised.value)
    assert 'auth.py' in message
    assert 'developer.yahoo.com' not in message, "401 is a token problem, not a permissions one"


def test_500_is_reported_with_the_status(monkeypatch):
    api = yahoo_says(monkeypatch, Response(500, text='upstream boom'))

    with pytest.raises(roster.YahooAPIError) as raised:
        api.getgameid()

    assert '500' in str(raised.value)


def test_html_instead_of_json_is_quoted(monkeypatch):
    api = yahoo_says(monkeypatch, Response(
        200, payload=None, text='<html>maintenance</html>', content_type='text/html'))

    with pytest.raises(roster.YahooAPIError) as raised:
        api.getgameid()

    message = str(raised.value)
    assert 'text/html' in message and 'maintenance' in message


def test_an_error_body_without_a_description_still_reports(monkeypatch):
    api = yahoo_says(monkeypatch, Response(403, {'unexpected': 'shape'}))

    with pytest.raises(roster.YahooAPIError) as raised:
        api.getgameid()

    assert '403' in str(raised.value)


# --- The success path is untouched ------------------------------------------

def test_a_good_response_still_parses(monkeypatch):
    api = yahoo_says(monkeypatch, Response(200, {
        'fantasy_content': {'game': [{'game_id': '431'}]}}))

    assert api.getgameid() == '431'
