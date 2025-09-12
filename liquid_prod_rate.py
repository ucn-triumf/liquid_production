#!/usr/bin/python3

# Read flow levels and calculate liquifier He production rate
# Derek Fujimoto
# Oct 2024

import pandas as pd
import datetime
import numpy as np
import json, demjson
import midas
import midas.client
import matplotlib.pyplot as plt, mpld3
from scipy.optimize import curve_fit
from ucnhistory import ucnhistory

from mpld3 import plugins

def md_fill_rate(t0, t1):

    # get data
    hist = ucnhistory()

    df = hist.get_data(table='ucn2epicsothers_measured',
                    columns=['ucn2_he4_fpv211_rddacp_measured',
                                'ucn2_he4_lvl204_rdlvl_measured'],
                    start = t0,
                    stop = t1)

    df.rename(columns={'ucn2_he4_fpv211_rddacp_measured':'fpv211',
                    'ucn2_he4_lvl204_rdlvl_measured':'lvl204'},
            inplace=True)

    # some data cleaning
    df = df.loc[df.lvl204 > 0]

    df.epoch_time -= 3600*8

    # get only when FPV211 is off
    df = df.loc[df.fpv211 == 0]
    dt_sep = df.epoch_time[df.epoch_time.diff() > 1000].values
    dt_sep = np.concatenate(([0], dt_sep, [int(2e9)]))

    # reset index
    df.set_index('epoch_time', inplace=True)

    # fit function
    fn = lambda x, a, b: a*x+b

    # save results
    rates = []
    drates = []
    times_start = []
    times_stop = []

    fig, (ax1, ax2) = plt.subplots(nrows=2, ncols=1, sharey=False, sharex=True,
                                figsize=(8,7),
                                gridspec_kw={'hspace':0.05,
                                             'height_ratios':(1,3)})

    # iterate times
    for begin, end in zip(dt_sep[:-1], dt_sep[1:]):
        df1 = df.loc[begin+300:end-300]

        if len(df1) == 0:
            continue

        t0 = min(df1.index)
        x = df1.index.values - t0

        # fit with linear line
        try:
            par, cov = curve_fit(fn, x, df1.lvl204, p0=(1e4, 20))
        except TypeError:
            continue
        std = np.diag(cov)**0.5

        date = pd.to_datetime(df1.index, unit='s')
        ax1.plot(date, df1.lvl204)
        ax1.plot(date, fn(x, *par), color='k')

        # convert rates to L/h
        par[0] *= 3600*12.6
        std[0] *= 3600*12.6

        rates.append(par[0])
        drates.append(std[0])
        times_start.append(pd.to_datetime(min(df1.index), unit='s'))
        times_stop.append(pd.to_datetime(max(df1.index), unit='s'))

    for starti, stopi, rate, drate in zip(times_start, times_stop, rates, drates):
        ax2.fill_between((starti, stopi), rate+drate, rate-drate, color='C0')

    # plot elements
    ax1.set_ylabel('MD Level (%)')
    ax2.set_ylabel('MD Fill Rate (L/hr)')
    ax2.tick_params(axis='x', which='major', labelsize='x-small')


    # setup figure with plugins
    plugins.clear(fig)  # clear all plugins from the figure
    plugins.connect(fig, plugins.Reset(), plugins.BoxZoom(), plugins.Zoom())

    # save to html
    mpld3.save_html(fig, 'liquid_prod_rate_fig.html', template_type='simple')

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

        # convert times to datetime objects
        t0 = datetime.datetime.strptime(t0, '%Y-%m-%dT%H:%M')
        t1 = datetime.datetime.strptime(t1, '%Y-%m-%dT%H:%M')

        md_fill_rate(t0, t1)

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
