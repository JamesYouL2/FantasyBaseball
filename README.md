# FantasyBaseball

This project is designed to update a spreadsheet every day with the depth chart projections from fangraphs and sync it with a yahoo fantasy baseball league.

To run it, you need to copy example.json in the auth folder to oauth2yahoo.json and add a consumer key and consumer secret. See "Keeping credentials out of the repo" below before you do.

I actually put a requirements.txt which I think works now.

Set your league id in `LEAGUE_ID` at the top of main.py.

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
token, a configured league id, league roster data, or a notebook with saved cell
outputs. Bypass it deliberately with `git commit --no-verify`.

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
