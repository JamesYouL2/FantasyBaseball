import os

import pandas as pd
import numpy as np
import pybaseball
from loguru import logger
import requests

# Edit these two lines once a year. They are named rather than inlined so the
# error messages below can tell you which season a failed fetch was for.
CURRENT_SEASON = 2026
PRIOR_SEASON = 2025

PLAYER_ID_MAP_FILE = "SFBB Player ID Map - PLAYERIDMAP.csv"
ROSTER_FILE = "./teams/roster.txt"
OUTPUT_FILE = "rankings.csv"

# Columns each feed has to supply for the formulas further down to mean
# anything. Checked up front so a renamed field reports itself by name instead
# of surfacing as a bare KeyError halfway through the arithmetic.
HITTER_COLUMNS = ('playerids', 'PlayerName', 'Team', 'PA', 'AB', 'OBP', 'SLG',
                  'H', 'R', 'HR', 'RBI', 'SB')
PITCHER_COLUMNS = ('playerids', 'PlayerName', 'Team', 'ER', 'IP', 'H', 'BB',
                   'SO', 'W', 'SV', 'HLD')
POSITION_COLUMNS = ('playerid', 'Pos', 'G', 'GS')
# The map supplies the id crosswalk only. Player names come from the
# projections feeds, which spell the column PlayerName; the map's own name
# column is PLAYERNAME and goes unused.
ID_MAP_COLUMNS = ('IDFANGRAPHS', 'YAHOOID')
ROSTER_COLUMNS = ('playerid', 'team', 'percent_owned')

# How many players deep the league's replacement level sits.
HITTER_REPLACEMENT_RANK = 70
PITCHER_REPLACEMENT_RANK = 90


class RankingsError(RuntimeError):
    """A failure reported with enough context to act on.

    Every raise site below names the feed or file at fault and what to do
    about it. The alternative is a KeyError on a column name from the middle
    of a formula, which says nothing about which of the four inputs broke.
    """


def _require_columns(frame, columns, source):
    """Fail early, and by name, when a feed drops a column we depend on."""
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        sample = ', '.join(sorted(frame.columns)[:12])
        raise RankingsError(
            f"{source} is missing the column(s) {', '.join(missing)}. "
            f"It has {len(frame.columns)} columns instead, beginning "
            f"{sample}. Upstream sources rename fields from time to time; "
            f"compare that list against the expected names at the top of "
            f"createrankings.py and update them together.")
    return frame


def _nth_best(series, n, what):
    """The nth largest value, or an explanation of why there isn't one."""
    ranked = series.dropna().nlargest(n)
    if len(ranked) < n:
        raise RankingsError(
            f"Need {n} {what} to set a replacement value, but only "
            f"{len(ranked)} have a usable one. Either the projections feed "
            f"returned a short list, or an input column arrived empty and "
            f"turned the whole value formula into NaN.")
    return float(ranked.iloc[-1])


def _read_local_csv(path, description, remedy, **kwargs):
    """Read a file this script expects to find beside it, or say why it can't."""
    try:
        frame = pd.read_csv(path, **kwargs)
    except FileNotFoundError:
        raise RankingsError(
            f"{description} not found at {os.path.abspath(path)}. {remedy}") from None
    except pd.errors.EmptyDataError:
        raise RankingsError(
            f"{description} at {os.path.abspath(path)} is empty. {remedy}") from None
    if frame.empty:
        raise RankingsError(
            f"{description} at {os.path.abspath(path)} has a header but no "
            f"rows. {remedy}")
    return frame


def _fetch_projections(stats, projection_type):
    """Pull one projections feed off Fangraphs, or explain the failure."""
    label = {'bat': 'hitter', 'pit': 'pitcher'}.get(stats, stats)
    url = f'https://www.fangraphs.com/api/projections?stats={stats}&type={projection_type}'
    try:
        frame = pd.read_json(url)
    except ValueError as e:
        raise RankingsError(
            f"Fangraphs returned something that is not JSON for the {label} "
            f"projections ({projection_type}). The endpoint serves an error "
            f"page rather than a JSON error, so this usually means the "
            f"projection type '{projection_type}' has been retired or "
            f"renamed. URL: {url}") from e
    except OSError as e:
        # urllib raises HTTPError/URLError, both OSError subclasses.
        raise RankingsError(
            f"Could not reach Fangraphs for the {label} projections "
            f"({projection_type}): {e}. URL: {url}") from e
    if frame.empty:
        raise RankingsError(
            f"Fangraphs returned no {label} projections for type "
            f"'{projection_type}'. Rest-of-season projections go empty once "
            f"the season ends; pass ros=False to fall back to full-season "
            f"ATC. URL: {url}")
    return frame


def GetPosition (array):
    if isinstance(array,np.ndarray):
        if array.__contains__('C'):
            return 'C'
        if array.__contains__('2B'):
            return '2B'
        if array.__contains__('3B'):
            return '3B'
        if array.__contains__('SS'):
            return 'SS'
        if array.__contains__('1B'):
            return '1B'
        if array.__contains__('OF'):
            return 'OF'
        else:
            return '1B'
    else:
        return '1B'

def fg_fielding_leaders(season: int = CURRENT_SEASON, qual: int = 0) -> pd.DataFrame:
    url = "https://www.fangraphs.com/api/leaders/major-league/data"
    params = {
        "pos": "all",
        "stats": "fld",
        "lg": "all",
        "qual": qual,
        "type": "1",
        "season": season,
        "season1": season,
        "ind": "0",
        "month": "0",
        "team": "0",
        "rost": "0",
        "age": "",
        "pageitems": "500000",
    }
    try:
        resp = requests.get(url, params=params, timeout=60)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise RankingsError(
            f"Could not fetch the {season} fielding leaderboard from "
            f"Fangraphs: {e}") from e
    try:
        payload = resp.json()
    except ValueError as e:
        raise RankingsError(
            f"The {season} fielding leaderboard came back as "
            f"{resp.headers.get('Content-Type', 'an unknown type')} rather "
            f"than JSON, starting: {resp.text[:200]!r}") from e
    if "data" not in payload:
        raise RankingsError(
            f"The {season} fielding leaderboard has no 'data' key. Its keys "
            f"are {sorted(payload)}, so the response shape has changed.")
    return pd.DataFrame(payload["data"])


def _positions_by_player(frame, season):
    """Map each player to the positions they actually played that season."""
    if frame.empty:
        # Legitimate in March, when the current season has no games yet.
        logger.warning(
            f"Fangraphs returned no {season} fielding data; positions for "
            f"that season will not contribute to the rankings.")
        return {}
    _require_columns(frame, POSITION_COLUMNS, f"the {season} fielding leaderboard")
    frame = frame.copy()
    frame['Pos'] = frame['Pos'].replace(['LF','CF','RF'],'OF')
    qualified = frame.loc[(frame['G']>=10) | (frame['GS']>=5)]
    return dict(qualified.groupby('playerid')['Pos'].unique())


def exportrankings(ros=True):
    projection_type = 'ratcdc' if ros else 'atc'
    hittersmean = _fetch_projections('bat', projection_type)
    pitchersmean = _fetch_projections('pit', projection_type)
    _require_columns(hittersmean, HITTER_COLUMNS,
                     f"The hitter projections feed ({projection_type})")
    _require_columns(pitchersmean, PITCHER_COLUMNS,
                     f"The pitcher projections feed ({projection_type})")

    positionsold = fg_fielding_leaders(PRIOR_SEASON, qual=0)
    positions = fg_fielding_leaders(CURRENT_SEASON, qual=0)
    ##From Smart Fantasy Baseball
    playeridmap = _read_local_csv(
        PLAYER_ID_MAP_FILE,
        "The Smart Fantasy Baseball player id map",
        "It is committed to the repository, so either the file was deleted or "
        "this script is being run from a directory other than the project "
        "root. Run it as 'uv run main.py' from the repository root.")
    _require_columns(playeridmap, ID_MAP_COLUMNS, "The player id map")

    hittersmean['OBPOnTeam'] = (hittersmean['PA']*hittersmean['OBP']+2037.4)/(hittersmean['PA']+6100)
    hittersmean['SLGOnTeam'] = (hittersmean['AB']*hittersmean['SLG']+2420)/(hittersmean['AB']+5500)
    hittersmean['OPSValue'] = (hittersmean['OBPOnTeam']+hittersmean['SLGOnTeam']-.774)/.006

    hittersmean['AVGValue'] = ((hittersmean['H']+1768)/(hittersmean['AB']+6100)-.267)/.0024
    hittersmean['value'] = hittersmean['OPSValue']+hittersmean['R']/8.92+hittersmean['HR']/8.0+hittersmean['RBI']/8.92+hittersmean['SB']/6.0+hittersmean['H']/9.0

    # Prior season first, current season second. dict.update means the current
    # season wins wherever a player appears in both, so an in-season position
    # change takes effect as soon as the player qualifies at the new spot.
    positionjoin = dict()
    positionjoin.update(_positions_by_player(positionsold, PRIOR_SEASON))
    positionjoin.update(_positions_by_player(positions, CURRENT_SEASON))
    if not positionjoin:
        raise RankingsError(
            f"Neither the {CURRENT_SEASON} nor the {PRIOR_SEASON} fielding "
            f"leaderboard produced a single qualified player, so every hitter "
            f"would be ranked at first base. Check that CURRENT_SEASON and "
            f"PRIOR_SEASON in createrankings.py point at seasons that have "
            f"been played.")
    positionjoin=pd.Series(positionjoin).to_frame()
    positionjoin.rename(columns={0:'Position'}, inplace=True)

    positionjoin.index=positionjoin.index.map(str)

    hittersmean['playerid']=hittersmean['playerids']

    hittersmerge=pd.merge(hittersmean,positionjoin,how='left',left_on='playerid',right_index=True)

    hittersmerge['BestPos']=hittersmerge['Position'].apply(GetPosition)

    hittersmerge['rank']=hittersmerge.groupby('BestPos')['value'].rank(ascending=False)
    hittersmerge['utilrank']=hittersmerge['value'].rank(ascending=False, method='first')

    ###customized league replacement value
    replacementvalue=hittersmerge.groupby('BestPos').value.nlargest(10).groupby('BestPos').min().reset_index(name='PosValue')
    # The 70th best hitter. Selected by nlargest rather than utilrank==70:
    # ranking ties average to 69.5/70.5, so the equality match can hit no rows.
    replacementvalue['UtilValue']=_nth_best(
        hittersmerge['value'], HITTER_REPLACEMENT_RANK, 'ranked hitters')

    replacementvalue['ReplacementValue']=pd.DataFrame([replacementvalue['UtilValue'], replacementvalue['PosValue']]).min()

    hittersmerge=hittersmerge.reset_index().merge(replacementvalue,on='BestPos')

    hittersmerge['VORP']=hittersmerge['value']-hittersmerge['ReplacementValue']

    ########################
    #CHANGE THE COLUMNS BELOW BASED ON SGP VALUES FOR YOUR LEAGUE
    #I think that you can use SGP based on MLB league averages
    pitchersmean['ERA']=((525.55+pitchersmean['ER'])*9/(1350.0+pitchersmean['IP'])-3.5)/-0.106
    pitchersmean['WHIP'] =((1620.0+pitchersmean['H']+pitchersmean['BB'])/(1350.0+pitchersmean['IP'])-1.2)/-0.02
    pitchersmean['KBB'] = (((55*9+pitchersmean['SO'])/(55*3+pitchersmean['BB']))-3)/0.09
    pitchersmean['value'] = (pitchersmean['W']/8.0)+pitchersmean['ERA']+pitchersmean['WHIP']+(pitchersmean['SO']/50.0)+(pitchersmean['SV']+pitchersmean['HLD'])/10.0
    ########################

    pitchersmean['utilrank']=pitchersmean['value'].rank(ascending=False, method='first')

    ###customized league replacement value
    # The 90th best pitcher. See the hitter equivalent above.
    pitchersmean['ReplacementValue']=_nth_best(
        pitchersmean['value'], PITCHER_REPLACEMENT_RANK, 'ranked pitchers')

    pitchersmean['VORP']=pitchersmean['value']-pitchersmean['ReplacementValue']
    pitchersmean['playerid']=pitchersmean['playerids']

    final=pd.concat([hittersmerge,pitchersmean])
    final['playerid']=final['playerid'].apply(str)

    ##get name
    finalmerge=pd.merge(final,playeridmap,left_on='playerid',right_on='IDFANGRAPHS',how='left')

    # IDFANGRAPHS comes from the map, so a non-null one means the row matched.
    matched = finalmerge['IDFANGRAPHS'].notna().sum()
    if matched == 0:
        raise RankingsError(
            "Not one Fangraphs id matched the player id map, so no row could "
            "be given a Yahoo id and the export would be empty of ownership "
            "data. The map's IDFANGRAPHS column and the projections' "
            "playerids column have stopped agreeing on a format. Refresh the "
            "map from Smart Fantasy Baseball.")
    logger.info(f"Matched {matched} of {len(finalmerge)} projected players to the id map")

    roster = _read_local_csv(
        ROSTER_FILE, "The Yahoo roster export",
        "It is written by YahooRoster.updateroster(); run 'uv run main.py' to "
        "produce it before exporting rankings.", sep='\t')
    _require_columns(roster, ROSTER_COLUMNS, "The Yahoo roster export")

    finalmerge['YAHOOID_int']=finalmerge['YAHOOID'].fillna(0).apply(int)
    finalmerge.drop_duplicates(subset=['PlayerName', 'AB'],inplace=True)

    #Shohei Ohtani handling
    finalmerge.loc[(finalmerge.YAHOOID_int == 10835) & (finalmerge.PA > 0),'YAHOOID_int'] = 1000001
    finalmerge.loc[(finalmerge.YAHOOID_int == 10835) & (finalmerge.PA.isnull()),'YAHOOID_int'] = 1000002

    finalexport=pd.merge(finalmerge,roster,left_on='YAHOOID_int',right_on='playerid',how='left')

    rostered = finalexport['team'].notna().sum()
    if rostered == 0:
        logger.warning(
            f"None of the {len(roster)} rostered players matched a projected "
            f"player, so the team and percent_owned columns will be empty. "
            f"The roster's Yahoo ids and the id map's YAHOOID column have "
            f"stopped agreeing.")
    else:
        logger.info(f"Matched {rostered} rostered players to a projection")

    #format player names
    finalexport['PlayerName']=finalexport['PlayerName'].str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8')

    export_columns = ['PlayerName','Team','value','VORP','BestPos','team','G','GS','W','SV','percent_owned']
    _require_columns(finalexport, export_columns, "The merged ranking table")
    finalexport[export_columns].sort_values('VORP', ascending=False).nlargest(500,['VORP']).to_csv(OUTPUT_FILE)
    logger.info(f"Wrote {OUTPUT_FILE}")
