import pandas as pd
import numpy as np
import pybaseball


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
    else:
        return '1B'

def exportrankings(ros=True):
    if ros:
        hittersmean = pd.read_json('https://www.fangraphs.com/api/projections?stats=bat&type=ratcdc')
        pitchersmean = pd.read_json('https://www.fangraphs.com/api/projections?stats=pit&type=ratcdc')
    else:
        hittersmean = pd.read_json('https://www.fangraphs.com/api/projections?stats=bat&type=atc')
        pitchersmean = pd.read_json('https://www.fangraphs.com/api/projections?stats=pit&type=atc')

    positionsold = pybaseball.fielding_stats(2023, qual=0)
    positions = pybaseball.fielding_stats(2024, qual=0)
    playeridmap = pd.read_csv("SFBB Player ID Map - PLAYERIDMAP.csv")
    ##From Smart Fantasy Baseball

    hittersmean['OBPOnTeam'] = (hittersmean['PA']*hittersmean['OBP']+2037.4)/(hittersmean['PA']+6100)
    hittersmean['SLGOnTeam'] = (hittersmean['AB']*hittersmean['SLG']+2420)/(hittersmean['AB']+5500)
    hittersmean['OPSValue'] = (hittersmean['OBPOnTeam']+hittersmean['SLGOnTeam']-.774)/.006

    hittersmean['AVGValue'] = ((hittersmean['H']+1768)/(hittersmean['AB']+6100)-.267)/.0024
    hittersmean['value'] = hittersmean['OPSValue']+hittersmean['R']/8.92+hittersmean['HR']/8.0+hittersmean['RBI']/8.92+hittersmean['SB']/5.0+hittersmean['H']/9.0

    positions['Pos']=positions['Pos'].replace(['LF','CF','RF'],'OF')
    positionsold['Pos']=positionsold['Pos'].replace(['LF','CF','RF'],'OF')

    positions_unique=positions.loc[(positions['G']>=10) | (positions['GS']>=5)].groupby('IDfg')['Pos'].unique()
    positions_oldunique=positionsold.loc[(positionsold['G']>=10) | (positionsold['GS']>=5)].groupby('IDfg')['Pos'].unique()

    positionjoin = dict()
    positionjoin.update(positions_unique)
    positionjoin.update(positions_oldunique)
    positionjoin=pd.Series(positionjoin).to_frame()
    positionjoin.rename(columns={0:'Position'}, inplace=True)

    positionjoin.index=positionjoin.index.map(str)
    #print(positionjoin.dtypes)
    #print(hittersmean.dtypes)

    hittersmean['playerid']=hittersmean['playerids']

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
    #I think that you can use SGP based on MLB league averages
    pitchersmean['ERA']=((525.55+pitchersmean['ER'])*9/(1350.0+pitchersmean['IP'])-3.5)/-0.106
    pitchersmean['WHIP'] =((1620.0+pitchersmean['H']+pitchersmean['BB'])/(1350.0+pitchersmean['IP'])-1.2)/-0.02
    pitchersmean['KBB'] = (((55*9+pitchersmean['SO'])/(55*3+pitchersmean['BB']))-3)/0.09
    pitchersmean['value'] = pitchersmean['KBB']+pitchersmean['ERA']+pitchersmean['WHIP']+(pitchersmean['W']/4.05+(pitchersmean['SV']+pitchersmean['HLD'])/10.0)
    ########################

    pitchersmean['utilrank']=pitchersmean['value'].rank(ascending=False)

    ###customized league replacement value
    pitchersmean['ReplacementValue']=float(pitchersmean.loc[pitchersmean['utilrank']==110]['value'])

    pitchersmean['VORP']=pitchersmean['value']-pitchersmean['ReplacementValue']
    pitchersmean['playerid']=pitchersmean['playerids']

    final=pd.concat([hittersmerge,pitchersmean])
    final['playerid']=final['playerid'].apply(str)

    ##get name
    finalmerge=pd.merge(final,playeridmap,left_on='playerid',right_on='IDFANGRAPHS',how='left')

    #finalmerge.nlargest(500,['VORP']).to_csv("ZipsSteamer.txt",sep='\t')

    roster = pd.read_csv("./teams/roster.txt",sep='\t')

    finalmerge['YAHOOID_int']=finalmerge['YAHOOID'].fillna(0).apply(int)
    finalmerge.drop_duplicates(subset=['Name', 'AB'],inplace=True)

    finalmerge.loc[(finalmerge.YAHOOID_int == 10835) & (finalmerge.PA > 0),'YAHOOID_int'] = 1000001
    finalmerge.loc[(finalmerge.YAHOOID_int == 10835) & (finalmerge.PA.isnull()),'YAHOOID_int'] = 1000002

    finalexport=pd.merge(finalmerge,roster,left_on='YAHOOID_int',right_on='playerid',how='left')
    
    #format player names
    finalexport['PlayerName']=finalexport['PlayerName'].str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8')

    finalexport[['PlayerName','Team','value','VORP','BestPos','team','G','GS','W','SV','percent_owned']].sort_values('VORP', ascending=False).nlargest(500,['VORP']).to_csv("rankings.tab", sep='\t')
