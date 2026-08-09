# -*- coding: utf-8 -*-
"""First-run setup: collect the three values this project needs.

    uv run init.py

Asks for the league id, the consumer key and the consumer secret, writes each
where config.py looks for it, and then hands over to the browser authorization
in auth.py. Safe to re-run: it replaces nothing without asking first.

Why prompts rather than command-line arguments, which would be less typing:

    An argument is written to your shell history, where it stays for months.
    It is visible in `ps` output to every other user on the machine for as
    long as the process runs. On a shared box it lands in process accounting
    too. None of that is true of a prompt.

The secret is read with getpass, so it is not echoed as you type it and does
not survive in the terminal scrollback either. Reading it from $stdin or an
environment variable would be fine as well -- what should not happen is the
secret appearing in argv.
"""

import getpass
import os
import sys

import config

# Yahoo consumer keys have started with this for years. Worth checking, but
# only as a warning: it is their format to change, not ours to enforce.
KEY_PREFIX = 'dj0y'

BANNER = """\
Fantasy Baseball setup
======================

You will need a Yahoo app. If you do not have one, create it at

    https://developer.yahoo.com/apps/create/

with Fantasy Sports read permission, and set the redirect URI to

    {redirect}

The app page then shows a Consumer Key and a Consumer Secret.

The league id is the number in your league's URL:
https://baseball.fantasysports.yahoo.com/b1/<league id>
"""


def main():
    if not sys.stdin.isatty():
        raise SystemExit(
            "init.py needs a terminal to prompt on. To configure without one, "
            "set YAHOO_LEAGUE_ID, YAHOO_CONSUMER_KEY and "
            "YAHOO_CONSUMER_SECRET in the environment instead.")

    print(BANNER.format(redirect=config.redirect_uri()))

    wrote_credentials = collect_credentials()
    wrote_league = collect_league_id()

    if not (wrote_credentials or wrote_league):
        print("Nothing changed.")

    # A grant belongs to the app that issued it. New credentials mean a
    # different app, so any cached tokens are dead weight -- keeping them would
    # make this report success and leave the next run failing on a refresh the
    # new consumer key cannot sign.
    if wrote_credentials and config.discard_tokens():
        print(f"  Discarded the old tokens: they were issued to the previous "
              f"app and cannot be refreshed with these credentials.")
    elif config.read_tokens_if_any():
        print("\nYou already have Yahoo tokens. Re-authorize only if they "
              "stopped working: uv run auth.py")
        return

    if confirm("\nAuthorize with Yahoo in a browser now?", default=True):
        import auth
        auth.main()
    else:
        print("Authorize later with: uv run auth.py")


# --- The three values -------------------------------------------------------

def collect_credentials():
    """Prompt for the consumer key and secret, and write them out."""
    path = config.credentials_file()
    if not replaceable(path, "consumer key and secret"):
        return False

    key = prompt("Consumer Key", validate=validate_key)
    # getpass, so the secret is never echoed and never enters the scrollback.
    secret = prompt_secret("Consumer Secret")

    config.write_credentials(key, secret)
    print(f"  Wrote {path}, readable only by you.")
    return True


def collect_league_id():
    """Prompt for the league id and write leagueid.ini."""
    path = config.LEAGUE_ID_FILE
    if not replaceable(path, "league id"):
        return False

    league_id = prompt("League id", validate=validate_league_id)
    config.write_league_id(league_id)
    print(f"  Wrote {path}.")
    return True


# --- Validation -------------------------------------------------------------

def validate_key(value):
    """Yahoo consumer keys are long and start with dj0y."""
    if len(value) < 20:
        return "That looks too short for a consumer key."
    if not value.startswith(KEY_PREFIX):
        # A warning, not a rejection: the format is Yahoo's to change.
        print(f"  Note: consumer keys usually start with '{KEY_PREFIX}'. "
              f"Continuing anyway.")
    return None


def validate_league_id(value):
    """League ids are the bare number out of the league URL."""
    if not value.isdigit():
        return ("A league id is just digits. From a URL like "
                ".../b1/12345, that is 12345.")
    return None


# --- Prompting --------------------------------------------------------------

def prompt(label, validate=None):
    """Ask until the answer is usable. Whitespace is stripped: pastes carry it."""
    while True:
        value = input(f"{label}: ").strip()
        if not value:
            print("  Required.")
            continue
        complaint = validate(value) if validate else None
        if complaint:
            print(f"  {complaint}")
            continue
        return value


def prompt_secret(label):
    """Read a secret without echoing it, and confirm it by length alone.

    Echoing back even part of a secret would put it in the scrollback, which
    is the thing getpass exists to avoid. The length is enough to catch the
    realistic mistake, which is a truncated or empty paste.
    """
    while True:
        value = getpass.getpass(f"{label} (not shown as you type): ").strip()
        if not value:
            print("  Required.")
            continue
        if confirm(f"  Read {len(value)} characters. Is that the whole secret?",
                   default=True):
            return value


def confirm(question, default=False):
    suffix = "[Y/n]" if default else "[y/N]"
    answer = input(f"{question} {suffix} ").strip().lower()
    if not answer:
        return default
    return answer.startswith('y')


def replaceable(path, what):
    """True when it is safe to write path, asking first if something is there."""
    if not os.path.exists(path):
        return True
    return confirm(f"{path} already has a {what}. Replace it?")


if __name__ == '__main__':
    main()
