# helper functions for liquid production rate
# Derek Fujimoto
# Oct 2024

import pandas as pd
import numpy as np
from scipy.stats import linregress
from settings import corr
import warnings
warnings.simplefilter('ignore')

from ucnhistory import ucnhistory

def get_data(loading_names, start, stop):
    """Load data from database and drop bad values

    Args:
        loading_names (list): one of levels or flows

    Returns:
        pd.DataFrame: dataframe with formatted data
    """

    hist = ucnhistory()

    df_list = []
    for load in loading_names:
        df = hist.get_data(**load, start=start, stop=stop)

        # round epoch_time to nearest 10s
        df['epoch_time'] = np.floor(df['epoch_time']/10)*10
        df['epoch_time'] = df['epoch_time'].astype(int)

        # drop duplicates
        df.drop_duplicates(subset='epoch_time', inplace=True)

        # set index
        df.set_index('epoch_time', inplace=True)

        # append
        df_list.append(df)
        
    # concat
    df_concat = pd.concat(df_list, axis='columns')
    
    # fill mismatched indices
    df_concat.interpolate(inplace=True)
    
    return df_concat.dropna()

def get_prod_rate(df_lvl, df_flw, do_correction=True):
    """Figure out the change in the total amount of liquid in the system

    Args:
        df_lvl (pd.DataFrame): level readings from 1K, 4K, and MD pots
        df_flw (pd.DataFrame): flow meter readings for return gas in SLM (liquid)
        do_correction (bool): if true, apply corrections found in settings.corr

    Returns:
        pd.Series: the slopes of the levels and the mean of the flows in liquid L/h
    """
    slopes = {}

    # draw and get slopes
    for col in df_lvl.columns:
        x = df_lvl.index
        y = df_lvl[col]

        result = linregress(x, y)
        slopes[col] = result.slope*3600 # L/h
        slopes[f'd{col}'] = result.stderr*3600 # L/h

    # convert to series
    slopes = pd.Series(slopes)
    slopes.name = np.mean(x)

    # add in flows
    for col in df_flw.columns:
        slopes[col] = df_flw[col].mean()*60
        slopes[f'd{col}'] = df_flw[col].std()*60

    # corrections for device issues
    if do_correction:
        for col in corr:
            slopes[col] = corr[col](slopes[col])

    return slopes
