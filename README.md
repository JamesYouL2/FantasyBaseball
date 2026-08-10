# FantasyBaseball

This project is designed to update a spreadsheet every day with the depth chart projections from fangraphs and sync it with a yahoo fantasy baseball league.

## Running it

Dependencies are managed with [uv](https://docs.astral.sh/uv/). `pyproject.toml`
is the dependency list and `uv.lock` pins the exact resolved versions, so a
checkout reproduces the same environment. There is no requirements.txt.

```
uv sync          # create .venv from the lockfile
uv run init.py   # first time only: credentials, league id, authorization
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

`config.py` is the only place that reads configuration. Values are split by how
long they live, because that decides how carefully each has to be handled:

| What | Lives for | File | Environment variable |
| --- | --- | --- | --- |
| Consumer key and secret | Until you rotate them | `auth/oauth2yahoo.json` | `YAHOO_OAUTH_FILE` (path), or `YAHOO_CONSUMER_KEY` / `YAHOO_CONSUMER_SECRET` (values) |
| Access and refresh tokens | An hour / until revoked | `auth/token.json` | `YAHOO_TOKEN_FILE` (path) |
| League id | — | `leagueid.ini` | `YAHOO_LEAGUE_ID` (value) |
| Redirect URI | — | — | `YAHOO_REDIRECT_URI` (value) |
| OAuth scope | — | — | `YAHOO_SCOPE` (default `fspt-r`) |

The token file is the only one the daily path ever writes, and it holds nothing
that cannot be thrown away: delete it and `uv run auth.py` mints another. The
credential file is written once by `init.py` and only read from then on, so
nothing that runs daily can damage it. All of them are gitignored.

First you need a Yahoo app, which is where the consumer key and secret come
from. Create one at [developer.yahoo.com/apps/create](https://developer.yahoo.com/apps/create/)
and set:

- **API Permissions** → tick **Fantasy Sports**, with **Read**. Nothing works
  without this; it is what makes the `fspt-r` scope grantable.
- **OAuth Client Type** → **Confidential Client**. The token exchange here
  authenticates with the consumer secret.
- **Redirect URI** → anything valid, e.g. `https://localhost:8080/callback`.
  It is not used by default, but the form requires one.

Yahoo rejects any `http://` redirect URI, loopback included, so the flow where
a local server catches the redirect and there is nothing to copy is not
available on Yahoo. Authorization uses `oob` instead: Yahoo shows a code and
you paste it once. If you do register a URI a local server can serve, set
`$YAHOO_REDIRECT_URI` and `auth.py` will use it.

Then:

```
uv run init.py
```

It asks for the three values, writes them owner-only, and hands straight over
to the browser authorization. Re-running it replaces nothing without asking.

It prompts rather than taking arguments on purpose: a command-line argument
lands in your shell history and is visible in `ps` to everyone else on the
machine for as long as the process runs. The secret is read with `getpass`, so
it is not echoed and does not stay in the scrollback either.

To do it by hand instead:

```
cp auth/example.json auth/oauth2yahoo.json    # then add your key and secret
cp example.ini leagueid.ini                   # then fill in leagueid=
uv run auth.py                                # authorize once, in a browser
```

Or skip the files entirely:

```
export YAHOO_CONSUMER_KEY=... YAHOO_CONSUMER_SECRET=...
export YAHOO_TOKEN_FILE=~/.config/fantasybaseball/token.json
export YAHOO_LEAGUE_ID=123456
```

See "Keeping credentials out of the repo" below before you start.

## Authorizing

`uv run auth.py` is a one-time step. It opens Yahoo in a browser, you approve,
Yahoo shows a code, you paste it once, and the tokens are written.

A redirect URI has to match what the app registers, exactly, or Yahoo refuses
the whole request — and the browser renders that refusal as an unattributed
"something went wrong", naming no field. So `auth.py` puts the request to Yahoo
first and prints the real reason instead:

```
Yahoo rejected the authorization request: invalid redirect uri.
```

It then offers `oob` and remembers the choice beside the credentials, so later
runs skip the exchange entirely. If you set `$YAHOO_REDIRECT_URI` to an
`http://localhost:PORT/…` URI that your app really lists, `auth.py` serves it
with a one-shot local server and nothing needs copying at all — but Yahoo does
not currently accept registering one.

Inside WSL, `webbrowser` picks a handler with no desktop behind it and silently
opens nothing, so the URL is opened through Windows interop (`wslview`, then
PowerShell, then `explorer.exe`) and printed either way.

The request asks for the `fspt-r` scope — Fantasy Sports, read. This is not
optional and not inherited from the app's settings: Yahoo grants a token
exactly the scopes its authorization named, so a request that names none
produces a token that authenticates perfectly and is then refused every
endpoint with `403 This application is not authorized to perform this action`.
If you see that, the token predates the scope being requested; re-run
`auth.py`. Read rather than write on purpose — nothing here writes to a
league, and Yahoo refuses `fspt-w` outright for apps not permitted it.

After that, nothing opens a browser again. Refresh tokens last until they are
revoked, so `main.py` renews the hourly access token by itself and can run
unattended. `league_authorization.py` cannot prompt — if the grant is ever
revoked it exits and tells you to re-run `auth.py`, rather than blocking a
scheduled run on a prompt nobody is there to answer.

## Talking to Fangraphs

`fangraphs.py` is the only thing that makes outbound requests to Fangraphs. A
full run is four of them, once a day — two projections feeds and two seasons of
fielding — which is less traffic than a person loading the leaderboard twice.

Fangraphs sits behind Cloudflare, as a CDN rather than a wall: the endpoint
advertises `Cache-Control: public, max-age=300` and repeat requests come back
`cf-cache-status: HIT`, meaning they are answered at the edge and never reach
the origin. Nothing here works around a block. It makes this the kind of client
that does not attract one:

| Environment variable | Default | What it does |
| --- | --- | --- |
| `FANGRAPHS_CONTACT` | unset | An email added to the User-Agent. Set it — an anonymous client is the one that gets challenged first, and being identifiable is what gets you an email instead of a silent ban. |
| `FANGRAPHS_CACHE_DIR` | `.cache/fangraphs` | Where responses are cached |
| `FANGRAPHS_CACHE_TTL` | `300` | Seconds a cached response stays fresh, matching Fangraphs' own header. `0` disables the cache. |

Requests are retried on 429 and 5xx with exponential backoff, honouring
`Retry-After` when the server sends one. A 404 is not retried, because
repeating a wrong request will not make it right. When a fetch fails outright
and a stale cache entry exists, that is served with a warning — an outage costs
you freshness rather than the whole run.

If Cloudflare ever does challenge a request, it fails with a message saying so
and quoting the `CF-RAY`. The fix is to set `FANGRAPHS_CONTACT` and slow down,
or to ask Fangraphs — not to imitate a browser, which is fragile, breaks
silently at the worst time, and is the thing their terms actually prohibit.

## Tests

```
uv run pytest
```

They cover the authorization layer and the Fangraphs transport, and touch the
network only over loopback — a local server stands in for Yahoo's redirect and
for a rate-limiting Fangraphs.

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

Better still, keep both files outside the working tree altogether:

```
mkdir -p ~/.config/fantasybaseball
cp auth/example.json ~/.config/fantasybaseball/oauth2yahoo.json
export YAHOO_OAUTH_FILE=~/.config/fantasybaseball/oauth2yahoo.json
export YAHOO_TOKEN_FILE=~/.config/fantasybaseball/token.json
```

The token file is created `0600` at the moment it is opened rather than
chmodded afterwards, and is written to a sibling and renamed, so an interrupted
write cannot leave a half-file where the working tokens were.

To audit the whole history for leaked values:

```
pipx run detect-secrets scan --all-files
# or
docker run --rm -v "$PWD:/repo" zricethezav/gitleaks:latest detect -s /repo -v
```

Refer here: https://github.com/yahoo-fantasy/nfl-fantasy-football for reference (copied most of the API handling from here).

PlayerIDMap: From Smart Fantasy Baseball. Link here: https://www.smartfantasybaseball.com/tools/
