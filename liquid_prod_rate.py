#!/usr/bin/python3

# Read flow levels and calculate liquifier He production rate
# Derek Fujimoto
# Oct 2024

import pandas as pd
import datetime
import numpy as np
from scipy.optimize import curve_fit
import json, demjson
import midas
import midas.client
from ucnhistory import ucnhistory

def md_fill_rate(t0, t1):

    # clean input
    t0 = int(t0.timestamp())
    t1 = int(min(t1.timestamp(), datetime.datetime.now().timestamp()))

    # get data from sql database
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

    # timezone correction
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

    # iterate times
    for begin, end in zip(dt_sep[:-1], dt_sep[1:]):
        df1 = df.loc[begin+300:end-300]
        x = df1.index.values - min(df1.index)

        # fit with linear line
        par, cov = curve_fit(fn, x, df1.lvl204, p0=(1e4, 20))
        std = np.diag(cov)**0.5

        # convert rates to L/h
        par[0] *= 3600*12.6
        std[0] *= 3600*12.6

        rates.append(par[0])
        drates.append(std[0])
        times_start.append(min(df1.index))
        times_stop.append(max(df1.index))

    # return
    return pd.DataFrame({'rate':rates, 'drate':drates, 'start':times_start, 'stop':times_stop})

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

        # get rates for production
        df = md_fill_rate(t0, t1)
        ret_str = df.T.to_json(orient='values')

        # output
        ret_int = midas.status_codes["SUCCESS"]
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
