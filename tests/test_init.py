# -*- coding: utf-8 -*-
"""Tests for the setup prompts.

The point of most of these is that a value typed at a prompt reaches disk
intact and owner-only, and that nothing existing is replaced silently.
"""

import json
import os
import stat

import pytest

import config
import init


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv('YAHOO_OAUTH_FILE', str(tmp_path / 'creds.json'))
    monkeypatch.setenv('YAHOO_TOKEN_FILE', str(tmp_path / 'token.json'))
    monkeypatch.chdir(tmp_path)          # leagueid.ini is written relatively
    return tmp_path


def answers(monkeypatch, typed, secret=None):
    """Script the prompts: typed lines for input(), one secret for getpass."""
    remaining = list(typed)
    monkeypatch.setattr('builtins.input', lambda *a: remaining.pop(0))
    if secret is not None:
        monkeypatch.setattr(init.getpass, 'getpass', lambda *a: secret)
    return remaining


# --- Values reach disk intact ----------------------------------------------

def test_credentials_are_written_owner_only(store, monkeypatch):
    key = 'dj0y' + 'k' * 40
    answers(monkeypatch, [key, 'y'], secret='s' * 40)

    assert init.collect_credentials() is True

    path = config.credentials_file()
    with open(path) as handle:
        assert json.load(handle) == {'consumer_key': key,
                                     'consumer_secret': 's' * 40}
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_league_id_is_written_where_league_id_reads_it(store, monkeypatch):
    answers(monkeypatch, ['123456'])

    assert init.collect_league_id() is True
    assert config.league_id() == '123456'


def test_pasted_whitespace_is_stripped(store, monkeypatch):
    """Copying a key out of a browser routinely brings a newline with it."""
    key = 'dj0y' + 'k' * 40
    answers(monkeypatch, [f'  {key}  ', 'y'], secret=f'  {"s" * 40}  ')

    init.collect_credentials()

    with open(config.credentials_file()) as handle:
        written = json.load(handle)
    assert written['consumer_key'] == key
    assert written['consumer_secret'] == 's' * 40


# --- Nothing is replaced silently -------------------------------------------

def test_existing_credentials_are_kept_when_the_answer_is_no(store, monkeypatch):
    original = {'consumer_key': 'KEEP', 'consumer_secret': 'KEEP'}
    with open(config.credentials_file(), 'w') as out:
        json.dump(original, out)
    answers(monkeypatch, ['n'])

    assert init.collect_credentials() is False

    with open(config.credentials_file()) as handle:
        assert json.load(handle) == original


def test_existing_credentials_are_replaced_when_confirmed(store, monkeypatch):
    with open(config.credentials_file(), 'w') as out:
        json.dump({'consumer_key': 'OLD', 'consumer_secret': 'OLD'}, out)
    key = 'dj0y' + 'n' * 40
    answers(monkeypatch, ['y', key, 'y'], secret='new' * 20)

    assert init.collect_credentials() is True

    with open(config.credentials_file()) as handle:
        assert json.load(handle)['consumer_key'] == key


# --- Validation catches the realistic mistakes ------------------------------

def test_a_league_url_pasted_whole_is_rejected_with_advice():
    complaint = init.validate_league_id(
        'https://baseball.fantasysports.yahoo.com/b1/12345')
    assert complaint and '12345' in complaint


def test_league_id_accepts_digits():
    assert init.validate_league_id('12345') is None


def test_truncated_consumer_key_is_rejected():
    assert init.validate_key('dj0ytooshort') is not None


def test_unusual_consumer_key_prefix_is_a_warning_not_a_rejection(capsys):
    """Yahoo's key format is theirs to change; do not hard-fail on it."""
    assert init.validate_key('xx0y' + 'k' * 40) is None
    assert 'dj0y' in capsys.readouterr().out


def test_prompt_reasks_until_the_answer_is_valid(monkeypatch, capsys):
    answers(monkeypatch, ['', 'not-digits', '4321'])
    assert init.prompt('League id', validate=init.validate_league_id) == '4321'


def test_secret_is_never_echoed(monkeypatch, capsys):
    """The length is confirmed; the secret itself must not reach the screen."""
    answers(monkeypatch, ['y'], secret='s3cr3t' * 8)

    init.prompt_secret('Consumer Secret')

    assert 's3cr3t' not in capsys.readouterr().out


def test_empty_secret_is_reasked(monkeypatch):
    typed = ['y']
    monkeypatch.setattr('builtins.input', lambda *a: typed.pop(0))
    secrets = ['', 'realsecret']
    monkeypatch.setattr(init.getpass, 'getpass', lambda *a: secrets.pop(0))

    assert init.prompt_secret('Consumer Secret') == 'realsecret'


# --- Switching to a different Yahoo app -------------------------------------

def test_new_credentials_discard_the_old_apps_tokens(store, monkeypatch, capsys):
    """A grant belongs to the app that issued it, so it cannot come along."""
    config.write_tokens({'access_token': 'OLD', 'refresh_token': 'OLD',
                         'expires_at': 9e9})
    with open(config.credentials_file(), 'w') as out:
        json.dump({'consumer_key': 'OLD', 'consumer_secret': 'OLD'}, out)

    key = 'dj0y' + 'n' * 40
    # replace credentials? y | key | secret confirm y | replace league id? n
    # | authorize now? n
    answers(monkeypatch, ['y', key, 'y', 'n', 'n'], secret='new' * 20)
    monkeypatch.setattr(init.sys.stdin, 'isatty', lambda: True)
    with open(config.LEAGUE_ID_FILE, 'w') as out:
        out.write('[DEFAULT]\nleagueid = 1\n')

    init.main()

    assert config.read_tokens_if_any() is None, "kept a grant from another app"
    assert 'Discarded the old tokens' in capsys.readouterr().out


def test_switching_apps_still_offers_authorization(store, monkeypatch, capsys):
    """The old bug: stale tokens made init report success and stop."""
    config.write_tokens({'access_token': 'OLD', 'refresh_token': 'OLD',
                         'expires_at': 9e9})
    with open(config.credentials_file(), 'w') as out:
        json.dump({'consumer_key': 'OLD', 'consumer_secret': 'OLD'}, out)
    with open(config.LEAGUE_ID_FILE, 'w') as out:
        out.write('[DEFAULT]\nleagueid = 1\n')

    key = 'dj0y' + 'n' * 40
    answers(monkeypatch, ['y', key, 'y', 'n', 'n'], secret='new' * 20)
    monkeypatch.setattr(init.sys.stdin, 'isatty', lambda: True)

    init.main()

    output = capsys.readouterr().out
    assert 'You already have Yahoo tokens' not in output
    assert 'Authorize later with' in output, "never offered to authorize"


def test_keeping_existing_credentials_keeps_the_tokens(store, monkeypatch, capsys):
    config.write_tokens({'access_token': 'KEEP', 'refresh_token': 'KEEP',
                         'expires_at': 9e9})
    with open(config.credentials_file(), 'w') as out:
        json.dump({'consumer_key': 'K', 'consumer_secret': 'S'}, out)
    with open(config.LEAGUE_ID_FILE, 'w') as out:
        out.write('[DEFAULT]\nleagueid = 1\n')

    answers(monkeypatch, ['n', 'n'])          # replace neither
    monkeypatch.setattr(init.sys.stdin, 'isatty', lambda: True)

    init.main()

    assert config.read_tokens_if_any()['refresh_token'] == 'KEEP'
    assert 'You already have Yahoo tokens' in capsys.readouterr().out


# --- Non-interactive use ----------------------------------------------------

def test_running_without_a_terminal_says_what_to_set_instead(monkeypatch):
    monkeypatch.setattr(init.sys.stdin, 'isatty', lambda: False)

    with pytest.raises(SystemExit) as raised:
        init.main()

    assert 'YAHOO_CONSUMER_KEY' in str(raised.value)
