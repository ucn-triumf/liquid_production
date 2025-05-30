#!/usr/bin/python3

# Read flow levels and calculate liquifier He production rate
# Derek Fujimoto
# Oct 2024

import pandas as pd
import datetime
import plotly.graph_objs as go
import numpy as np
from toolkit import get_data
import settings
from scipy.ndimage import gaussian_filter
import json, demjson
import midas
import midas.client

def calc_production_rate(t0, t1, window_size, window=None, **window_kwargs):

    # save original epoch times to later trim the dataframes
    t0_orig = int(t0.timestamp())
    t1_orig = int(min(t1.timestamp(), datetime.datetime.now().timestamp()-window_size))

    # expand the timestamps by the window size
    t0 -= datetime.timedelta(seconds=window_size)
    t1 += datetime.timedelta(seconds=window_size)

    # read levels data
    df_lvl = get_data(settings.levels, t0, t1)
    df_lvl *= settings.conv

    # read the flows in liquid L/min
    df_flw = get_data(settings.flows, t0, t1)
    df_flw /= 745

    # drop all nan columns
    df_lvl.dropna(axis='columns', how='all', inplace=True)
    df_flw.dropna(axis='columns', how='all', inplace=True)

    # window to seconds
    window_size = int(window_size/10)

    # data smoothing
    if window_size > 0:
        df_flw = df_flw.rolling(window=window_size,
                                min_periods=window_size,
                                center=True,
                                axis='index',
                                win_type=window,
                                ).mean(**window_kwargs)

        df_lvl = df_lvl.rolling(window=window_size,
                                min_periods=window_size,
                                center=True,
                                axis='index',
                                win_type=window,
                                ).mean(**window_kwargs)

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
    for col in settings.corr:
        rates[col] = settings.corr[col](rates[col])

    # get production rate
    rates.rename(columns=settings.labels, inplace=True)
    prod_rate = rates.sum(axis='columns')

    # downsample
    if len(rates) > 1000:
        factor = int(len(rates)/1000)
        rates = rates.loc[::factor]
        prod_rate = prod_rate.loc[::factor]

    # trim
    rates = rates.loc[t0_orig:t1_orig]
    prod_rate = prod_rate.loc[t0_orig:t1_orig]

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
        title='',
        yaxis_title='Change in Level or Flow (Liquid L/h)',
        font=dict(
            family="Arial",
            size=16,
            color="Black"
        ),
        plot_bgcolor='rgba(0,0,0,0)',
        width=900,
        height=525,
        margin=dict(autoexpand=True,
                b=0,
                t=20,
                ),
    )

    fig.update_xaxes(showline=True, linewidth=2, linecolor='black', gridcolor='Gray', zerolinecolor='Gray')
    fig.update_yaxes(showline=True, linewidth=2, linecolor='black', gridcolor='Gray', zerolinecolor='Gray')

    # write figure for later insertion into web page
    fig.write_html('/home/ucn/online/ucn-web-control/liquid_production/liquid_prod_rate_fig.html')

def rpc_handler(client, cmd, args, max_len):
    """
    This is the function that will be called when something/someone
    triggers the "JRPC" for this client (e.g. by using the javascript
    code above).

    Arguments:

    * client (midas.client.MidasClient)
    * cmd (str) - The command user wants to execute
    * args (str) - Other arguments the user supplied
    * max_len (int) - The maximum string length the user accepts in the return value

    Returns:

    2-tuple of (int, str) for status code, message.
    """
    ret_int = midas.status_codes["SUCCESS"]
    ret_str = ""

    if cmd == "draw_figure":

        # get arguments
        jargs = json.loads(args)
        t0 = jargs.get("start")
        t1 = jargs.get("end")
        window_size = jargs.get("width")
        window_fn = jargs.get("fn")

        # split out passed parameters to functions
        winlist = window_fn.split(';')
        window_fn = winlist[0]

        if len(winlist) < 2:
            window_kwargs = {}
        else:
            window_kwargs = demjson.decode(winlist[1])

        # convert gaussian widths into units of samples
        if window_fn == 'gaussian':
            window_kwargs['std'] = window_kwargs['std']*window_size*6

        # convert times to datetime objects
        t0 = datetime.datetime.strptime(t0, '%Y-%m-%dT%H:%M')
        t1 = datetime.datetime.strptime(t1, '%Y-%m-%dT%H:%M')
        window_size = float(window_size)*60

        # make new figure
        calc_production_rate(t0, t1, window_size, window_fn, **window_kwargs)

        # output
        ret_int = midas.status_codes["SUCCESS"]
        ret_str = json.dumps({"last": str(datetime.datetime.now())})
    else:
        ret_int = midas.status_codes["FE_ERR_DRIVER"]
        ret_str = "Unknown command '%s'" % cmd

    return (ret_int, ret_str)

if __name__ == "__main__":
    client = midas.client.MidasClient("liquidprod")

    # Register our function.
    client.register_jrpc_callback(rpc_handler, True)
    client.msg('Started liquidprod client')

    # Spin forever. Program can be killed by Ctrl+C or
    # "Stop Program" through mhttpd.
    while True:
        client.communicate(100) # ms