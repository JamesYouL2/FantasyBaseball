# -*- coding: utf-8 -*-
"""
Created on Wed Apr  3 13:24:09 2019

@author: jjy
"""


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

zipsh = pd.read_csv("./zipsh/FanGraphs Leaderboard.csv")
steamerh = pd.read_csv("./steamerh/FanGraphs Leaderboard.csv")
zipsp = pd.read_csv("./zipsp/FanGraphs Leaderboard.csv")
steamerp = pd.read_csv("./steamerp/FanGraphs Leaderboard.csv")
depthchartsp = pd.read_csv("./depthchartsp/FanGraphs Leaderboard.csv")
positions = pd.read_csv("./positions/FanGraphs Leaderboard.csv")
positionsold = pd.read_csv("./positionsold/FanGraphs Leaderboard.csv")
playeridmap = pd.read_csv("./playeridmap.txt",sep='\t',encoding='latin1')
##From CrunchTimeBaseball

zipsh['playerid'] = zipsh['playerid'].apply(str)

hitters = pd.concat((zipsh, steamerh))

hittersmean = hitters.groupby(hitters.playerid).mean().fillna(0)

########################
#CHANGE THE COLUMNS BELOW BASED ON SGP VALUES FOR YOUR LEAGUE
hittersmean['OBPVal'] = ((hittersmean['H']+hittersmean['BB']+hittersmean['HBP']+2037.4)/(hittersmean['PA']+6100)-.334)/.0016
hittersmean['AVGVal'] = ((hittersmean['H']+1768)/(hittersmean['AB']+6100)-.267)/.0024
hittersmean['value'] = hittersmean['OBPVal']+(hittersmean['R']/8.92+hittersmean['HR']/7.5+hittersmean['RBI']/8.92+hittersmean['SB']/6.0)
########################

positions['Pos']=positions['Pos'].replace(['LF','CF','RF'],'OF')
positionsold['Pos']=positionsold['Pos'].replace(['LF','CF','RF'],'OF')

positions_unique=positions.loc[(positions['G']>=10) | (positions['GS']>=5)].groupby('playerid')['Pos'].unique()
positions_oldunique=positionsold.loc[(positionsold['G']>=10) | (positionsold['GS']>=5)].groupby('playerid')['Pos'].unique()

positionjoin = dict()
positionjoin.update(positions_unique)
positionjoin.update(positions_oldunique)
positionjoin=pd.Series(positionjoin).to_frame()
positionjoin.index=positionjoin.index.map(str)
positionjoin.rename(columns={0:'Position'}, inplace=True)

hittersmean=pd.merge(hittersmean,positionjoin,how='left',left_index=True,right_index=True)

hittersmean['BestPos']=hittersmean['Position'].apply(GetPosition)

hittersmean['rank']=hittersmean.groupby('BestPos')['value'].rank(ascending=False)
hittersmean['utilrank']=hittersmean['value'].rank(ascending=False)

###customized league replacement value
replacementvalue=hittersmean.groupby('BestPos').value.nlargest(10).groupby('BestPos').min().reset_index(name='PosValue')
replacementvalue['UtilValue']=float(hittersmean.loc[hittersmean['utilrank']==80]['value'])

replacementvalue['ReplacementValue']=pd.DataFrame([replacementvalue['UtilValue'], replacementvalue['PosValue']]).min()

hittersmean=hittersmean.reset_index().merge(replacementvalue,on='BestPos')

hittersmean['VORP']=hittersmean['value']-hittersmean['ReplacementValue']

pitchers = pd.concat((zipsp, steamerp))

pitchersmean=pitchers.groupby(pitchers.playerid).mean().fillna(0)

########################
#CHANGE THE COLUMNS BELOW BASED ON SGP VALUES FOR YOUR LEAGUE
pitchersmean['ERA']=((525.55+pitchersmean['ER'])*9/(1350.0+pitchersmean['IP'])-3.5)/-0.1062
pitchersmean['WHIP'] =((1620.0+pitchersmean['H']+pitchersmean['BB'])/(1350.0+pitchersmean['IP'])-1.2)/-0.0201
pitchersmean['value'] = pitchersmean['ERA']+pitchersmean['WHIP']+(pitchersmean['W']/4.05+pitchersmean['K/9']*pitchersmean['IP']/(55.0*9.0)+pitchersmean['SV']/10.0)
########################

pitchersmean['utilrank']=pitchersmean['value'].rank(ascending=False)

###customized league replacement value
pitchersmean['ReplacementValue']=float(pitchersmean.loc[pitchersmean['utilrank']==70]['value'])

pitchersmean['VORP']=pitchersmean['value']-pitchersmean['ReplacementValue']

hittersmeanindex=hittersmean.reset_index()
pitchersmeanindex=pitchersmean.reset_index()

hittersmeanindex['playerid']=hittersmeanindex['playerid'].astype(str)
pitchersmeanindex['playerid']=pitchersmeanindex['playerid'].astype(str)

hittersmeanindex=hittersmeanindex.set_index('playerid')
pitchersmeanindex=pitchersmeanindex.set_index('playerid')

final=pd.concat([hittersmeanindex,pitchersmeanindex])

##get name
finalmerge=pd.merge(final,playeridmap,left_on='playerid',right_on='fg_id',how='left')

finalmerge.nlargest(500,['VORP']).to_csv("ZipsSteamer.txt",sep='\t')