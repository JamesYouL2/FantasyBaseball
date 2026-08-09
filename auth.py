# -*- coding: utf-8 -*-
"""One-time Yahoo authorization.

    uv run auth.py

Authorizing is not something a daily job should ever do, so it lives apart from
the code that runs daily. This is the only module that opens a browser or reads
from a terminal, and nothing imports it. Run it once; after that the refresh
token in the cache carries every later run on its own, and only a revoked grant
or a changed password brings you back here.

Yahoo returns the authorization code to whichever redirect URI the app is
registered with, and refuses the request outright for any other, so that
registration decides the flow:

    http://localhost:PORT/...   a one-shot local server catches the redirect,
                                and there is nothing to copy at all
    oob                         Yahoo shows the code on screen to be pasted
    anything else               the browser lands somewhere that cannot
                                receive it, so the address bar gets pasted back

Yahoo's app form does not accept a loopback redirect URI on every app, so the
loopback flow is offered rather than assumed. A request it will not honour is
answered with a redirect to Yahoo's own error page, which in a browser reads
only as "something went wrong" -- so the request is put to Yahoo first, where
the same response carries a description worth printing, and the out-of-band
fallback is offered before a browser is ever opened.

$YAHOO_REDIRECT_URI overrides everything. Otherwise the choice is remembered
beside the credentials once it works.
"""

import http.server
import secrets
import subprocess
import time
import urllib.parse
import webbrowser

import requests

import config
from league_authorization import TOKEN_URL, error_code, tokens_from

AUTHORIZE_URL = 'https://api.login.yahoo.com/oauth2/request_auth'

# Yahoo's out-of-band flow: it shows the code on screen instead of redirecting.
# The fallback when an app has no redirect URI a local server can receive.
OOB_REDIRECT = 'oob'

# Long enough to find the browser window and log in, short enough that a
# forgotten terminal does not sit on the port all day.
REDIRECT_TIMEOUT_SECONDS = 300


def main():
    redirect = config.redirect_uri()
    # Echoed back by Yahoo and compared on return, so that a redirect this run
    # did not ask for cannot hand it a code.
    state = secrets.token_urlsafe(24)
    key, secret = config.client_credentials()

    complaint = preflight(authorize_url(key, redirect, state))
    if complaint:
        redirect = resolve(complaint, key, redirect, state)

    url = authorize_url(key, redirect, state)
    loopback = loopback_address(redirect)
    code = (catch_redirect(loopback, url, state) if loopback
            else ask_for_code(url, redirect))

    config.write_tokens(exchange(code, redirect, key, secret))
    print(f"\nAuthorized. Tokens written to {config.token_file()}, owner-only.")
    print("Nothing else needs a browser: main.py refreshes from here on.")


def authorize_url(key, redirect, state):
    return f'{AUTHORIZE_URL}?' + urllib.parse.urlencode({
        'client_id': key,
        'redirect_uri': redirect,
        'response_type': 'code',
        'state': state,
    })


# --- Asking Yahoo before asking the browser ---------------------------------

def preflight(url):
    """Yahoo's complaint about this request, or None if it has none.

    An unusable authorize request is answered with a redirect to Yahoo's own
    error page, which renders in a browser as an unattributed "something went
    wrong" -- no field named, nothing to act on. The same redirect read here
    carries error_description, so the failure can be named before a browser is
    ever opened.
    """
    try:
        response = requests.get(url, timeout=30, allow_redirects=False)
    except requests.RequestException:
        return None                  # offline: let the browser report that

    location = response.headers.get('Location', '')
    if '/oauth2/error' not in location:
        return None
    query = urllib.parse.parse_qs(urllib.parse.urlparse(location).query)
    return query.get('error_description', query.get('error', ['rejected']))[0]


def resolve(complaint, key, redirect, state):
    """Explain Yahoo's complaint, and offer the fallback when there is one."""
    print(f"Yahoo rejected the authorization request: {complaint}.\n")

    if 'redirect' not in complaint.lower():
        raise SystemExit(
            f"Check that the consumer key and secret match the app at "
            f"https://developer.yahoo.com/apps/ and that it has Fantasy "
            f"Sports read permission.")

    print(f"The app is not registered with the redirect URI this is using:\n"
          f"    {redirect}\n"
          f"Yahoo only accepts a redirect URI that the app itself lists.\n")

    if redirect != OOB_REDIRECT and preflight(
            authorize_url(key, OOB_REDIRECT, state)) is None:
        print("Yahoo does accept out-of-band authorization for this app, which\n"
              "works the same way but shows you a code to paste instead of\n"
              "redirecting. Nothing else about the setup changes.\n")
        if confirm("Use out-of-band authorization and remember that choice?",
                   default=True):
            config.save_redirect_uri(OOB_REDIRECT)
            print(f"  Saved to {config.credentials_file()}.\n")
            return OOB_REDIRECT

    raise SystemExit(
        f"Set the app's redirect URI at https://developer.yahoo.com/apps/ to "
        f"match, or point $YAHOO_REDIRECT_URI at whatever it does list.")


def confirm(question, default=False):
    suffix = "[Y/n]" if default else "[y/N]"
    answer = input(f"{question} {suffix} ").strip().lower()
    return default if not answer else answer.startswith('y')


# --- Opening a browser ------------------------------------------------------

def open_browser(url):
    """Open a URL, including from WSL, where webbrowser usually cannot.

    Inside WSL, Python picks whatever it can find -- often 'gio' -- and there
    is no Linux desktop for it to hand the URL to, so the call quietly does
    nothing. The Windows browser is reachable over interop instead.
    """
    if _is_wsl():
        for command in (['wslview', url],
                        ['powershell.exe', '-NoProfile', '-Command',
                         f"Start-Process '{url}'"],
                        ['explorer.exe', url]):
            try:
                subprocess.run(command, timeout=20,
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
                return True
            except (FileNotFoundError, subprocess.SubprocessError):
                continue
        return False
    try:
        return webbrowser.open(url)
    except webbrowser.Error:
        return False


def _is_wsl():
    try:
        with open('/proc/version') as handle:
            return 'microsoft' in handle.read().lower()
    except OSError:
        return False


# --- Catching the redirect --------------------------------------------------

def loopback_address(redirect):
    """(host, port) if this redirect URI is one a local server can receive.

    Only plain http on the loopback interface qualifies. An https redirect
    would need a certificate the browser trusts, which is a worse problem than
    pasting a URL, and a remote host cannot be listened on at all.
    """
    parts = urllib.parse.urlparse(redirect)
    if parts.scheme != 'http' or parts.hostname not in ('localhost', '127.0.0.1'):
        return None
    return parts.hostname, parts.port or 80


class RedirectHandler(http.server.BaseHTTPRequestHandler):
    """Captures the first request that actually carries the redirect."""

    query = None

    def do_GET(self):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if 'code' not in query and 'error' not in query:
            # A favicon request, or a stray tab. Not what is being waited for.
            self.send_error(404)
            return

        type(self).query = query
        body = b"<h2>Authorized.</h2><p>You can close this tab.</p>"
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        """Silence the access log: the request line contains the code."""


def catch_redirect(loopback, url, state):
    """Serve the redirect URI just long enough to receive one code."""
    host, port = loopback
    try:
        server = http.server.HTTPServer((host, port), RedirectHandler)
    except OSError as error:
        raise SystemExit(
            f"Cannot listen on {host}:{port} ({error}). Something else is on "
            f"that port; free it, or register a different redirect URI with "
            f"Yahoo and set $YAHOO_REDIRECT_URI to match.")

    print(f"Opening Yahoo in your browser. If it does not open, visit:\n\n  {url}\n")
    print(f"Waiting for the redirect back to {host}:{port} ...")
    open_browser(url)

    # Polled rather than blocked on, so that a 404 for some unrelated request
    # does not consume the one chance to catch the real redirect.
    deadline = time.monotonic() + REDIRECT_TIMEOUT_SECONDS
    with server:
        server.timeout = 5
        while RedirectHandler.query is None and time.monotonic() < deadline:
            server.handle_request()

    query = RedirectHandler.query
    if query is None:
        raise SystemExit(
            f"Gave up after {REDIRECT_TIMEOUT_SECONDS}s with no redirect. If the "
            f"browser showed a Yahoo error, the app's registered redirect URI "
            f"does not match {config.redirect_uri()}.")
    if 'error' in query:
        raise SystemExit(f"Yahoo refused authorization: {query['error'][0]}")
    if query.get('state', [None])[0] != state:
        raise SystemExit("Redirect carried the wrong state value; discarded.")
    return query['code'][0]


def ask_for_code(url, redirect):
    """Fall back to the browser as courier when the redirect cannot be served."""
    opened = open_browser(url)
    where = "Your browser should be open at" if opened else "Open this and approve access"
    print(f"{where}:\n\n  {url}\n")
    if redirect == OOB_REDIRECT:
        print("Yahoo will show you a code once you approve. Paste it here.")
    else:
        print("Then paste the address you were redirected to -- the whole "
              "thing, even if\nthe page failed to load. The code is in it.")
    return code_from(input('> ').strip())


def code_from(pasted):
    """Pull the code out of a pasted redirect URL, or accept a bare code.

    Retyping a code off a page is the step people get wrong. An address bar
    can be copied whole and without reading it, so that is what is asked for,
    and a bare code is still accepted for the redirect URIs that display one.
    """
    if not pasted:
        raise SystemExit("Nothing pasted.")
    if pasted.startswith('http') or '?' in pasted:
        query = urllib.parse.parse_qs(urllib.parse.urlparse(pasted).query)
        if 'code' not in query:
            raise SystemExit("That URL has no ?code= in it.")
        return query['code'][0]
    return pasted


# --- Spending the code ------------------------------------------------------

def exchange(code, redirect, key, secret):
    """Trade the authorization code for the tokens that outlive it."""
    response = requests.post(
        TOKEN_URL,
        auth=(key, secret),
        data={
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': redirect,
        },
        timeout=30)

    if not response.ok:
        raise SystemExit(
            f"Yahoo rejected the authorization code ({error_code(response)}). "
            f"Codes expire within minutes and are single-use, so the usual fix "
            f"is to run auth.py again and finish it promptly. Failing that, "
            f"check that the consumer key, secret and redirect URI all match "
            f"the app at https://developer.yahoo.com/apps/.")
    return tokens_from(response.json())


if __name__ == '__main__':
    main()
