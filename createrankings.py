import pandas as pd
import numpy as np

def GetPosition (array):
    if isinstance(array,np.ndarray):
        if array.__contains__('C'):
            return 'C'
        if array.__contains__('2B'):
            return '2B'
        if array.__contains__('SS'):
            return 'SS'
        if array.__contains__('3B'):
            return '3B'
        if array.__contains__('1B'):
            return '1B'
        if array.__contains__('OF'):
            return 'OF'
    else: 
        return '1B'

def exportrankings():
    hittersmean = pd.read_csv("./hitters/FanGraphs Leaderboard.csv")
    pitchersmean = pd.read_csv("./pitchers/FanGraphs Leaderboard.csv")
    positions = pd.read_csv("./positions/FanGraphs Leaderboard.csv")
    positionsold = pd.read_csv("./positionsold/FanGraphs Leaderboard.csv")
    playeridmap = pd.read_csv("SFBB Player ID Map - PLAYERIDMAP.csv")
    ##From Smart Fantasy Baseball

    hittersmean['OBPOnTeam'] = (hittersmean['PA']*hittersmean['OBP']+2037.4)/(hittersmean['PA']+6100)
    hittersmean['SLGOnTeam'] = (hittersmean['AB']*hittersmean['SLG']+2420)/(hittersmean['AB']+5500)
    hittersmean['OPSValue'] = (hittersmean['OBPOnTeam']+hittersmean['SLGOnTeam']-.774)/.006

    hittersmean['AVGValue'] = ((hittersmean['H']+1768)/(hittersmean['AB']+6100)-.267)/.0024
    hittersmean['value'] = hittersmean['OPSValue']+(hittersmean['R']/8.92+hittersmean['HR']/7.5+hittersmean['RBI']/8.92+hittersmean['SB']/6.0)

    positions['Pos']=positions['Pos'].replace(['LF','CF','RF'],'OF')
    positionsold['Pos']=positionsold['Pos'].replace(['LF','CF','RF'],'OF')

    positions_unique=positions.loc[(positions['G']>=10) | (positions['GS']>=5)].groupby('playerid')['Pos'].unique()
    positions_oldunique=positionsold.loc[(positionsold['G']>=10) | (positionsold['GS']>=5)].groupby('playerid')['Pos'].unique()

    positionjoin = dict()
    positionjoin.update(positions_unique)
    positionjoin.update(positions_oldunique)
    positionjoin=pd.Series(positionjoin).to_frame()
    positionjoin.rename(columns={0:'Position'}, inplace=True)

    positionjoin.index=positionjoin.index.map(str)

    hittersmerge=pd.merge(hittersmean,positionjoin,how='left',left_on='playerid',right_index=True)

    hittersmerge['BestPos']=hittersmerge['Position'].apply(GetPosition)

    hittersmerge['rank']=hittersmerge.groupby('BestPos')['value'].rank(ascending=False)
    hittersmerge['utilrank']=hittersmerge['value'].rank(ascending=False)

    ###customized league replacement value
    replacementvalue=hittersmerge.groupby('BestPos').value.nlargest(10).groupby('BestPos').min().reset_index(name='PosValue')
    replacementvalue['UtilValue']=float(hittersmerge.loc[hittersmerge['utilrank']==80]['value'])

    replacementvalue['ReplacementValue']=pd.DataFrame([replacementvalue['UtilValue'], replacementvalue['PosValue']]).min()

    hittersmerge=hittersmerge.reset_index().merge(replacementvalue,on='BestPos')

    hittersmerge['VORP']=hittersmerge['value']-hittersmerge['ReplacementValue']

    ########################
    #CHANGE THE COLUMNS BELOW BASED ON SGP VALUES FOR YOUR LEAGUE
    pitchersmean['ERA']=((525.55+pitchersmean['ER'])*9/(1350.0+pitchersmean['IP'])-3.5)/-0.1062
    pitchersmean['WHIP'] =((1620.0+pitchersmean['H']+pitchersmean['BB'])/(1350.0+pitchersmean['IP'])-1.2)/-0.0201
    pitchersmean['value'] = pitchersmean['ERA']+pitchersmean['WHIP']+(pitchersmean['W']/4.05+pitchersmean['K/9']*pitchersmean['IP']/(55.0*9.0)+(pitchersmean['SV']+pitchersmean['HLD'])/10.0)
    ########################

    pitchersmean['utilrank']=pitchersmean['value'].rank(ascending=False)

    ###customized league replacement value
    pitchersmean['ReplacementValue']=float(pitchersmean.loc[pitchersmean['utilrank']==110]['value'])

    pitchersmean['VORP']=pitchersmean['value']-pitchersmean['ReplacementValue']

    final=pd.concat([hittersmerge,pitchersmean])
    final['playerid']=final['playerid'].apply(str)

    ##get name
    finalmerge=pd.merge(final,playeridmap,left_on='playerid',right_on='IDFANGRAPHS',how='left')

    finalmerge.nlargest(500,['VORP']).to_csv("ZipsSteamer.txt",sep='\t')

    roster = pd.read_csv("./teams/roster.txt",sep='\t')

    finalmerge['YAHOOID_int']=finalmerge['YAHOOID'].fillna(0).apply(int)

    finalexport=pd.merge(finalmerge,roster,left_on='YAHOOID_int',right_on='playerid',how='left')

    finalexport[['Name','Team','VORP','BestPos','team','G','GS','W','SV']].sort_values('VORP', ascending=False).nlargest(500,['VORP']).to_csv("rankings.csv")
