# -*- coding: utf-8 -*-
"""Tests for the Fangraphs transport: retries, caching and failure messages.

The retry tests run against a local HTTP server rather than a mocked adapter,
because the behaviour under test belongs to urllib3 rather than to this
project. Whether Retry-After is honoured is precisely the sort of thing a mock
would happily lie about, and getting it wrong is what turns a rate limit into
a ban.
"""

import http.server
import json
import socket
import threading
import time

import pytest
import requests

import fangraphs


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Cache to a temporary directory and never reuse a session between tests."""
    monkeypatch.setenv('FANGRAPHS_CACHE_DIR', str(tmp_path / 'cache'))
    monkeypatch.setattr(fangraphs, '_session', None)
    # Real backoff is measured in seconds and would dominate the suite. Cutting
    # it also sharpens the Retry-After test below: with backoff this small, a
    # retry that waits a second can only have got that from the header.
    monkeypatch.setattr(fangraphs, 'BACKOFF_FACTOR', 0.01)


@pytest.fixture
def server():
    """A local HTTP server whose responses each test scripts in advance."""
    responses = []
    received = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            received.append(self)
            status, headers, body = (responses.pop(0) if responses
                                     else (200, {}, json.dumps({'data': []})))
            encoded = body.encode('utf-8')
            self.send_response(status)
            for name, value in headers.items():
                self.send_header(name, value)
            self.send_header('Content-Length', str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, *args):
            pass

    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]

    httpd = http.server.HTTPServer(('127.0.0.1', port), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    class Fixture:
        url = f'http://127.0.0.1:{port}/api'
        queue = responses
        requests_received = received

    yield Fixture
    httpd.shutdown()


def mount_on_http(monkeypatch):
    """The retry adapter is mounted on https://; the test server speaks http."""
    session = fangraphs.build_session()
    adapter = session.adapters['https://']
    session.mount('http://', adapter)
    monkeypatch.setattr(fangraphs, '_session', session)
    return session


# --- Identification ---------------------------------------------------------

def test_requests_identify_the_project(server, monkeypatch):
    mount_on_http(monkeypatch)
    fangraphs.get_json(server.url)

    agent = server.requests_received[0].headers['User-Agent']
    assert 'fantasybaseball' in agent
    assert 'github.com' in agent, "an anonymous client is the one that gets blocked"


def test_contact_address_is_included_when_set(monkeypatch):
    monkeypatch.setenv('FANGRAPHS_CONTACT', 'someone@example.com')
    import importlib
    reloaded = importlib.reload(fangraphs)
    try:
        assert 'someone@example.com' in reloaded.USER_AGENT
    finally:
        monkeypatch.delenv('FANGRAPHS_CONTACT')
        importlib.reload(fangraphs)


# --- Retrying ---------------------------------------------------------------

def test_429_is_retried_and_retry_after_is_honoured(server, monkeypatch):
    mount_on_http(monkeypatch)
    server.queue.append((429, {'Retry-After': '1'}, 'slow down'))

    started = time.monotonic()
    payload = fangraphs.get_json(server.url)
    elapsed = time.monotonic() - started

    assert payload == {'data': []}, "did not recover on the retry"
    assert len(server.requests_received) == 2
    assert elapsed >= 1, f"retried after {elapsed:.2f}s, ignoring Retry-After: 1"


def test_transient_5xx_is_retried(server, monkeypatch):
    mount_on_http(monkeypatch)
    server.queue.append((502, {}, 'bad gateway'))
    server.queue.append((503, {}, 'unavailable'))

    assert fangraphs.get_json(server.url) == {'data': []}
    assert len(server.requests_received) == 3


def test_404_is_not_retried(server, monkeypatch):
    """A 404 means the request was wrong; repeating it will not fix that."""
    mount_on_http(monkeypatch)
    server.queue.append((404, {}, 'nope'))

    with pytest.raises(fangraphs.FangraphsError) as raised:
        fangraphs.get_json(server.url)

    assert len(server.requests_received) == 1
    assert '404' in str(raised.value)


def test_persistent_429_reports_the_wait_it_was_asked_for(server, monkeypatch):
    monkeypatch.setattr(fangraphs, 'RETRY_ATTEMPTS', 1)
    mount_on_http(monkeypatch)
    for _ in range(4):
        server.queue.append((429, {'Retry-After': '0'}, 'slow down'))

    with pytest.raises(fangraphs.FangraphsError) as raised:
        fangraphs.get_json(server.url, description='the leaderboard')

    assert '429' in str(raised.value)
    assert 'the leaderboard' in str(raised.value)


# --- Diagnosing a block -----------------------------------------------------

def test_cloudflare_challenge_is_named_as_such(server, monkeypatch):
    mount_on_http(monkeypatch)
    server.queue.append((403, {'cf-mitigated': 'challenge', 'CF-RAY': 'abc123'},
                         '<!DOCTYPE html><html>go away</html>'))

    with pytest.raises(fangraphs.FangraphsError) as raised:
        fangraphs.get_json(server.url)

    message = str(raised.value)
    assert 'Cloudflare' in message and 'abc123' in message
    assert 'FANGRAPHS_CONTACT' in message, "does not say how to become identifiable"


def test_html_instead_of_json_quotes_the_start_of_it(server, monkeypatch):
    mount_on_http(monkeypatch)
    server.queue.append((200, {'Content-Type': 'text/html'},
                         '<!DOCTYPE html><html>an error page</html>'))

    with pytest.raises(fangraphs.FangraphsError) as raised:
        fangraphs.get_json(server.url)

    assert 'text/html' in str(raised.value)
    assert '<!DOCTYPE html' in str(raised.value)


def test_unreachable_host_is_reported_not_raised_raw(monkeypatch):
    mount_on_http(monkeypatch)
    with pytest.raises(fangraphs.FangraphsError) as raised:
        fangraphs.get_json('http://127.0.0.1:1/api', description='the leaderboard')
    assert 'the leaderboard' in str(raised.value)


# --- Caching ----------------------------------------------------------------

def test_second_call_is_served_from_cache(server, monkeypatch):
    mount_on_http(monkeypatch)

    first = fangraphs.get_json(server.url)
    second = fangraphs.get_json(server.url)

    assert first == second
    assert len(server.requests_received) == 1, "went back out for a cached response"


def test_cache_distinguishes_different_parameters(server, monkeypatch):
    mount_on_http(monkeypatch)

    fangraphs.get_json(server.url, {'season': 2025})
    fangraphs.get_json(server.url, {'season': 2026})

    assert len(server.requests_received) == 2, "served one season from another's cache"


def test_cache_expires(server, monkeypatch):
    mount_on_http(monkeypatch)
    monkeypatch.setenv('FANGRAPHS_CACHE_TTL', '0')

    fangraphs.get_json(server.url)
    fangraphs.get_json(server.url)

    assert len(server.requests_received) == 2, "used a cache that was disabled"


def test_stale_cache_rescues_a_failed_fetch(server, monkeypatch):
    """An outage should cost you freshness, not the whole run."""
    mount_on_http(monkeypatch)
    server.queue.append((200, {}, json.dumps({'data': ['yesterday']})))
    fangraphs.get_json(server.url)

    monkeypatch.setenv('FANGRAPHS_CACHE_TTL', '-1')      # everything is stale
    server.queue.append((500, {}, 'down'))
    server.queue.append((500, {}, 'down'))
    server.queue.append((500, {}, 'down'))
    server.queue.append((500, {}, 'down'))
    server.queue.append((500, {}, 'down'))

    assert fangraphs.get_json(server.url) == {'data': ['yesterday']}


def test_failure_with_no_cache_at_all_still_raises(server, monkeypatch):
    mount_on_http(monkeypatch)
    server.queue.append((404, {}, 'nope'))

    with pytest.raises(fangraphs.FangraphsError):
        fangraphs.get_json(server.url)


def test_corrupt_cache_entry_is_ignored(server, monkeypatch):
    mount_on_http(monkeypatch)
    fangraphs.get_json(server.url)

    path = fangraphs._cache_file(server.url, None)
    with open(path, 'w') as out:
        out.write('{ truncated')

    assert fangraphs.get_json(server.url) == {'data': []}
    assert len(server.requests_received) == 2, "trusted a corrupt cache entry"
