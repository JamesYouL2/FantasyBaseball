# -*- coding: utf-8 -*-
"""
Created on Mon Apr  8 11:33:38 2019

@author: jjy
"""

import pandas as pd

def merge():
    zipssteamer = pd.read_csv("./ZipsSteamer.txt",sep='\t')
    roster = pd.read_csv("./teams/roster.txt",sep='\t')

    ##get name
    final=pd.merge(zipssteamer,roster,left_on='nfbc_id',right_on='playerid',how='left')

    final.nlargest(500,['VORP']).to_csv("FINALPROJECTIONS.txt",sep='\t')