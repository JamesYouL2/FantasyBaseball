# FantasyBaseball

This project is designed to update a spreadsheet every day with the depth chart projections from fangraphs and sync it with a yahoo fantasy baseball league.

## Running it

Dependencies are managed with [uv](https://docs.astral.sh/uv/). `pyproject.toml`
is the dependency list and `uv.lock` pins the exact resolved versions, so a
checkout reproduces the same environment. There is no requirements.txt.

```
uv sync          # create .venv from the lockfile
uv run main.py   # run against that environment
```

`uv sync` reads `.python-version` (3.12) and fetches that interpreter if you do
not have it, so there is nothing to install first beyond uv itself.

To change a dependency, edit `pyproject.toml` and re-lock:

```
uv add <package>     # or edit pyproject.toml by hand, then:
uv lock              # regenerate uv.lock
```

Commit `pyproject.toml` and `uv.lock` together — a lockfile that disagrees with
`pyproject.toml` makes `uv sync --locked` fail.

## Configuration

`config.py` is the only place that reads configuration. It draws on two files,
both gitignored, and each one can be replaced by an environment variable:

| What | File | Environment variable |
| --- | --- | --- |
| Consumer key, secret, tokens | `auth/oauth2yahoo.json` | `YAHOO_OAUTH_FILE` (path) |
| League id | `leagueid.ini` | `YAHOO_LEAGUE_ID` (value) |

They stay separate because `yahoo_oauth` owns the JSON file: it rewrites it in
place every time the access token is refreshed, so its format and location are
the library's to decide, not ours.

To set up:

```
cp auth/example.json auth/oauth2yahoo.json    # then add your key and secret
cp example.ini leagueid.ini                   # then fill in leagueid=
```

Or skip both files entirely:

```
export YAHOO_OAUTH_FILE=~/.config/fantasybaseball/oauth2yahoo.json
export YAHOO_LEAGUE_ID=123456
```

See "Keeping credentials out of the repo" below before you start.

## Keeping credentials out of the repo

This repository is public, so nothing secret can live inside it.

Enable the commit guard and the notebook filter once per clone:

```
git config core.hooksPath .githooks
git config filter.nbstrip.clean "python3 scripts/nbstrip.py"
```

Both are local config and do not travel with a clone, so run them again on any
new machine.

The hook refuses any commit that stages a credential file, a real Yahoo key or
token, a league id (in a config file or hardcoded in source), league roster
data, or a notebook with saved cell outputs. Bypass it deliberately with
`git commit --no-verify`.

The `nbstrip` filter clears notebook outputs on the way into git, so your
working copy keeps its outputs while the committed blob never has them. Outputs
are the easiest way to leak from this project: they embed local filesystem
paths, scraped league data, and whatever a cell printed. The hook double-checks
the staged blob, so a clone that forgot the filter still gets caught.

To clean a notebook on disk (rather than just on commit):

```
python3 scripts/nbstrip.py --inplace draft/draft.ipynb
```

Better still, keep the credential file outside the working tree altogether:

```
mkdir -p ~/.config/fantasybaseball
cp auth/example.json ~/.config/fantasybaseball/oauth2yahoo.json
export YAHOO_OAUTH_FILE=~/.config/fantasybaseball/oauth2yahoo.json
```

`yahoo_oauth` rewrites that file on every token refresh, so it ends up holding
the consumer secret, the access token and the refresh token. The code chmods it
to `0600` and silences the oauth libraries, which otherwise log token payloads
at INFO.

To audit the whole history for leaked values:

```
pipx run detect-secrets scan --all-files
# or
docker run --rm -v "$PWD:/repo" zricethezav/gitleaks:latest detect -s /repo -v
```

Refer here: https://github.com/yahoo-fantasy/nfl-fantasy-football for reference (copied most of the API handling from here).

PlayerIDMap: From Smart Fantasy Baseball. Link here: https://www.smartfantasybaseball.com/tools/
