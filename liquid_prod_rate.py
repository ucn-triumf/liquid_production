#!/usr/bin/python3

# Read flow levels and calculate liquifier He production rate
# Derek Fujimoto
# Oct 2024

import pandas as pd
import datetime
import plotly.graph_objs as go
import numpy as np
from toolkit import get_data
from settings import *
from scipy.ndimage import gaussian_filter

## Settings -------------------------------------------------

# times in minutes
total_time=60*24*7
sigma = 30

# get now minus total time
t0 = str(datetime.datetime.now() - datetime.timedelta(minutes=total_time))
t1 = None

## END Settings -------------------------------------------------

# read levels data
df_lvl = get_data(levels, t0, t1)
df_lvl *= conv

# read the flows in liquid L/min
df_flw = get_data(flows, t0, t1)
df_flw /= 745

# drop all nan columns
df_lvl.dropna(axis='columns', how='all', inplace=True)
df_flw.dropna(axis='columns', how='all', inplace=True)

# data smoothing
df_flw = df_flw.apply(gaussian_filter, sigma=sigma, axis='index')
df_lvl = df_lvl.apply(gaussian_filter, sigma=sigma, axis='index')

# differentiate
dt = df_lvl.index[1] - df_lvl.index[0]
df_lvl = df_lvl.diff()/dt

# per hour
df_lvl *= 3600
df_flw *= 60

# ensure timestamps at least have a chance of matching
df_lvl.index = df_lvl.index.astype(int)
df_flw.index = df_flw.index.astype(int)

# concatenate
rates = pd.concat((df_lvl, df_flw), axis='columns')

# fill mismatched indices
rates.interpolate(inplace=True)

# corrections
for col in corr:
    rates[col] = corr[col](rates[col])

# get production rate
rates.rename(columns=labels, inplace=True)
prod_rate = rates.sum(axis='columns')

# get time in current timezone
x = pd.to_datetime(rates.index.values, unit='s', utc=True).tz_convert('America/Vancouver')

# draw
data = []
for col in rates:
    if 'd' == col[0]: continue

    data.append(go.Line(x=x,
                        y=rates[col].values,
                        name=col))

data.append(go.Line(x=x,
                    y=prod_rate.values,
                    name='Amount of liquified He (sum)',
                    line=dict(width=5, color='black'))
                )
fig = go.Figure(data)

fig.update_layout(
    title=f'Rate of Change in Levels<br><sup>Gaussian filter smoothing σ: {sigma*dt/60:0.1g} min</sup>',
    yaxis_title='Change in Level or Flow (Liquid L/h)',
    font=dict(
        family="Arial",
        size=18,
        color="Black"
    ),
    plot_bgcolor='rgba(0,0,0,0)',
    width=1200*0.75,
    height=800*0.75,
)

fig.update_xaxes(showline=True, linewidth=2, linecolor='black', gridcolor='Gray', zerolinecolor='Gray')
fig.update_yaxes(showline=True, linewidth=2, linecolor='black', gridcolor='Gray', zerolinecolor='Gray')

# write figure for later insertion into web page
fig.write_html('/home/ucn/online/ucn-web-control/liquid_production/liquid_prod_rate_fig.html')
