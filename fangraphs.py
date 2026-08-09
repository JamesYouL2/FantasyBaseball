# -*- coding: utf-8 -*-
"""HTTP transport for the Fangraphs API: identified, retried, and cached.

Fangraphs sits behind Cloudflare, but as a CDN rather than a wall. The
leaderboard endpoint advertises `Cache-Control: public, max-age=300`, and
repeat requests come back `cf-cache-status: HIT`, which means they are answered
at the edge and never reach the origin. Nothing here works around a block. It
makes this the kind of client that does not attract one, and keeps a run
useful when the network has other ideas:

    Identified   A User-Agent naming the project and, if you set one, a
                 contact address. An anonymous client is indistinguishable
                 from a scraper, and that is what gets challenged first.

    Retried      One 429 or 502 would otherwise take down the whole daily run.
                 Backoff is exponential, and Retry-After is honoured whenever
                 the server sends one.

    Cached       On disk, for the 300 seconds Fangraphs itself nominates. A
                 full run is four requests, so iterating on the formulas costs
                 nothing after the first. A stale entry is also the fallback
                 when a fetch fails outright: an outage degrades to this
                 morning's numbers rather than to no numbers.

A whole run is four requests once a day, which is less traffic than a person
loading the leaderboard twice. The politeness here is cheap insurance, not a
response to a problem that exists today.
"""

import hashlib
import json
import os
import time
import urllib.parse

import requests
from loguru import logger
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Identifying the client is the single most useful thing this module does. An
# email belongs in $FANGRAPHS_CONTACT rather than in source, because this
# repository is public and the address would be scraped out of it within days.
PROJECT_URL = 'https://github.com/JamesYouL2/FantasyBaseball'
CONTACT = os.environ.get('FANGRAPHS_CONTACT', '').strip()
USER_AGENT = (f"fantasybaseball/0.1 (+{PROJECT_URL}; {CONTACT})" if CONTACT
              else f"fantasybaseball/0.1 (+{PROJECT_URL})")

# What Fangraphs asks for in its own Cache-Control header.
CACHE_TTL_SECONDS = 300

# Retried statuses only. A 404 or a 400 means the request was wrong, and
# repeating it verbatim will not make it right.
RETRY_STATUSES = (429, 500, 502, 503, 504)
RETRY_ATTEMPTS = 4
BACKOFF_FACTOR = 1.0
TIMEOUT_SECONDS = 60


class FangraphsError(Exception):
    """A request to Fangraphs failed in a way worth explaining."""


def cache_dir():
    """Where cached responses live. $FANGRAPHS_CACHE_DIR overrides."""
    return os.path.expanduser(
        os.environ.get('FANGRAPHS_CACHE_DIR', '.cache/fangraphs'))


def cache_ttl():
    """Seconds a cached response stays fresh. Set to 0 to disable the cache."""
    try:
        return int(os.environ.get('FANGRAPHS_CACHE_TTL', CACHE_TTL_SECONDS))
    except ValueError:
        return CACHE_TTL_SECONDS


def build_session():
    """A session that identifies itself and retries the transient failures.

    urllib3 does the retrying, which matters for one specific reason: it
    honours Retry-After. A hand-rolled loop that ignores it is exactly the
    behaviour that turns a rate limit into a ban.
    """
    retry = Retry(
        total=RETRY_ATTEMPTS,
        backoff_factor=BACKOFF_FACTOR,
        status_forcelist=RETRY_STATUSES,
        allowed_methods=('GET',),
        respect_retry_after_header=True,
        # Hand the final failed response back rather than raising from deep
        # inside urllib3, so the message below can say what actually happened.
        raise_on_status=False,
    )
    session = requests.Session()
    session.headers['User-Agent'] = USER_AGENT
    session.mount('https://', HTTPAdapter(max_retries=retry))
    return session


_session = None


def session():
    """The shared session, built once per process."""
    global _session
    if _session is None:
        _session = build_session()
    return _session


# --- Cache ------------------------------------------------------------------

def _cache_file(url, params):
    """A stable filename for one url-and-parameters combination."""
    key = url + '?' + urllib.parse.urlencode(sorted((params or {}).items()))
    digest = hashlib.sha256(key.encode('utf-8')).hexdigest()[:32]
    return os.path.join(cache_dir(), f'{digest}.json')


def _read_cache(path):
    """A cached entry as (payload, age_in_seconds), or (None, None)."""
    try:
        with open(path) as handle:
            entry = json.load(handle)
        return entry['payload'], time.time() - entry['fetched_at']
    except (FileNotFoundError, ValueError, KeyError):
        return None, None


def _write_cache(path, payload):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    temporary = f'{path}.tmp'
    with open(temporary, 'w') as out:
        json.dump({'fetched_at': time.time(), 'payload': payload}, out)
    os.replace(temporary, path)


# --- Fetching ---------------------------------------------------------------

def get_json(url, params=None, description='Fangraphs'):
    """Fetch and parse one JSON response, via the cache where possible.

    Raises FangraphsError with something worth reading. The caller is expected
    to wrap it in whatever its own vocabulary is.
    """
    path = _cache_file(url, params)
    ttl = cache_ttl()

    if ttl > 0:
        payload, age = _read_cache(path)
        if payload is not None and age < ttl:
            logger.debug(f"{description}: cached, {int(age)}s old")
            return payload

    try:
        payload = _fetch_json(url, params, description)
    except FangraphsError as error:
        # stale-while-revalidate, by hand: yesterday's numbers beat none.
        stale, age = _read_cache(path)
        if stale is None:
            raise
        logger.warning(
            f"{description}: {error} Falling back to the cached copy from "
            f"{int(age // 60)} minutes ago.")
        return stale

    if ttl > 0:
        _write_cache(path, payload)
    return payload


def _fetch_json(url, params, description):
    """One request, after urllib3 has finished retrying it."""
    try:
        response = session().get(url, params=params, timeout=TIMEOUT_SECONDS)
    except requests.RequestException as error:
        raise FangraphsError(f"Could not reach Fangraphs for {description}: {error}.")

    if response.status_code in RETRY_STATUSES:
        raise FangraphsError(
            f"Fangraphs kept returning {response.status_code} for "
            f"{description} across {RETRY_ATTEMPTS} attempts"
            f"{_retry_after(response)}.")

    if response.status_code == 403 and _is_challenge(response):
        raise FangraphsError(
            f"Cloudflare challenged the request for {description} (403, "
            f"cf-ray {response.headers.get('CF-RAY', 'unknown')}). Set "
            f"$FANGRAPHS_CONTACT so the client is identifiable, and slow the "
            f"run down; do not try to look like a browser.")

    if not response.ok:
        raise FangraphsError(
            f"Fangraphs returned {response.status_code} for {description}.")

    try:
        return response.json()
    except ValueError:
        raise FangraphsError(
            f"{description} came back as "
            f"{response.headers.get('Content-Type', 'an unknown type')} rather "
            f"than JSON, starting: {response.text[:200]!r}.")


def _retry_after(response):
    header = response.headers.get('Retry-After')
    return f", asking us to wait {header}s" if header else ""


def _is_challenge(response):
    """Whether a 403 is Cloudflare's doing rather than the origin's."""
    return ('cf-mitigated' in response.headers
            or 'html' in response.headers.get('Content-Type', ''))
