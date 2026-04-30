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
from scipy.optimize import curve_fit
from ucnhistory import ucnhistory
import threading, time
import plotly.graph_objects as go
from plotly.subplots import make_subplots

class FigureDrawer(object):

    def start_draw(self, t0, t1):
        self.th = threading.Thread(target=md_fill_rate, args = (t0, t1))
        self.th.start()

    def is_alive(self):
        try:
            return self.th.is_alive()
        except AttributeError:
            return False

figure = FigureDrawer()

def round_times(df):
    """truncate timestamps to the nearest 10 s"""
    
    # truncate epoch times to the nearest 10 s then reset the axis
    df.epoch_time = df.epoch_time//10*10
    df.drop_duplicates('epoch_time', inplace=True)
    df['time'] = pd.to_datetime(df.epoch_time, unit='s')
    df.set_index('time', inplace=True)
    df = df.tz_localize('UTC').tz_convert('America/Vancouver')
    return df

def md_fill_rate(t0, t1):

    # get data
    hist = ucnhistory()

    df = hist.get_data(table='ucn2epicsothers_measured',
                    columns=['ucn2_he4_fpv211_rddacp_measured',
                             'ucn2_he4_lvl204_rdlvl_measured'],
                    start = t0,
                    stop = t1)
    df = round_times(df)
    
    # get flow data
    df2 = hist.get_data(table='ucn2pur_measured', 
                                 columns=['ucn2_he4_fm210_rdflow_measured'],
                                 start=t0,
                                 stop=t1)
    df2 = round_times(df2)
  
    df = pd.concat((df, df2['ucn2_he4_fm210_rdflow_measured']),
                    axis='columns')

    df.rename(columns={'ucn2_he4_fpv211_rddacp_measured':'fpv211',
                       'ucn2_he4_lvl204_rdlvl_measured':'lvl204',
                       'ucn2_he4_fm210_rdflow_measured':'fm210'},
              inplace=True)

    df_orig = df.copy()

    # some data cleaning
    df = df.loc[df.lvl204 > 10]

    # fix timestamps
    df.epoch_time -= 3600*8
    df_orig.epoch_time -= 3600*8

    # get only when slope is increasing
    df = df.loc[df.lvl204.diff(periods=100) > 0]

    # get times of transition
    dt_sep = df.epoch_time[df.epoch_time.diff() > 1000].values
    dt_sep = np.concatenate(([0], dt_sep, [int(2e9)]))

    # reset index
    df.set_index('epoch_time', inplace=True)
    df_orig.set_index('epoch_time', inplace=True)

    # fit function
    fn = lambda x, a, b: a*x+b

    # save results
    rates = []          # fill rate
    drates = []         # error in fill rate
    return_flows = []   # avg return flows FM210
    dreturn_flows = []  # error in avg return flows FM210
    times_center = []   # center time in datetime
    mins = []           # minimum values for each period
    epoch_min_times = []   # center time in epoch time

    fig = make_subplots(rows=4, cols=1,
                    shared_xaxes=True,
                    vertical_spacing=0.02)

    # draw background data
    fig.add_trace(go.Scatter(x=pd.to_datetime(df.index, unit='s'),
                         y=df.lvl204,
                         name='',
                         marker = {'color' : 'grey'},),
              row=1, col=1)

    # iterate times
    for begin, end in zip(dt_sep[:-1], dt_sep[1:]):

        # get data segment
        df1 = df.loc[begin:end]

        # trim first and last point to avoid off by one errors
        df1 = df1.iloc[1:-1]

        # trim start and end times
        idx = (df1.index > df1.index.min()+120) & (df1.index < df1.index.max()-300)
        df1 = df1.loc[idx]

        # needs a decently long set of data to fit
        if len(df1) < 100:
            continue

        t0 = min(df1.index)
        x = df1.index.values - t0

        # get average flows
        idx = df1.index > df1.index.min()+(13*60) # takes a while for the flow to drop
        return_flows.append(df1.loc[idx, 'fm210'].mean())
        dreturn_flows.append(df1.loc[idx, 'fm210'].std())

        # fit with linear line
        try:
            par, cov = curve_fit(fn, x, df1.lvl204, p0=(1e4, 20))
        except TypeError:
            continue
        std = np.diag(cov)**0.5

        # throw out slopes that are near zero
        if par[0]*3600*12.6 < 3:
            continue

        # draw
        date = pd.to_datetime(df1.index, unit='s')
        fig.add_trace(go.Scatter(x=date, y=df1.lvl204,
                                name='',
                                line = {'width' : 2},),
                    row=1, col=1, )
        fig.add_trace(go.Scatter(x=date, y=fn(x, *par),
                        marker = {'color' : 'black'},
                        name='',
                        hovertemplate=f"LVL204 [%] = {par[0]*3600:.1f} [%/h] t + {par[1]:.1f} [%]<br>LVL204 [L] = {par[0]*3600*12.6:.1f} [L/h] t + {par[1]*12.6:.1f} [L]"
                        ),
                    row=1, col=1)

        # convert rates to L/h
        par[0] *= 3600*12.6
        std[0] *= 3600*12.6

        # save fit results
        rates.append(par[0])
        drates.append(std[0])
        times_center.append(pd.to_datetime(np.mean(df1.index), unit='s'))
        epoch_min_times.append(min(df1.index))
        mins.append(fn(min(x), *par))


    # plotly drawing - rates
    fig.add_trace(go.Scatter(x=times_center,
                         y=rates,
                         error_y = {'type':'data', 'array':drates, 'visible':True, 'width':0},
                         name = '',
                         marker = {'color':'black',
                                   'size':10},
                         mode='markers',),
                row=2, col=1,)

    # plotly drawing - surplus rates
    epoch_min_times = np.array(epoch_min_times)
    xpts = (epoch_min_times[:-1] + epoch_min_times[1:])/2
    fig.add_trace(go.Scatter(x=pd.to_datetime(xpts, unit='s'),
                         y=np.diff(mins)/np.diff(epoch_min_times)*3600*12.6,
                         name = '',
                         marker = {'color':'red',
                                   'size':10},
                         mode='markers',),
              row=3, col=1,)
    
    # plotly drawing - flows
    fig.add_trace(go.Scatter(x=times_center,
                         y=return_flows,
                         error_y = {'type':'data', 'array':dreturn_flows, 'visible':True, 'width':0},
                         name = '',
                         marker = {'color':'black',
                                   'size':10},
                         mode='markers',),
                row=4, col=1,)

    fig.update_layout(showlegend=False, margin=dict(l=0,r=0,b=0,t=0))
    fig.update_yaxes(title_text="MD Level (%)", row=1)
    fig.update_yaxes(title_text="MD Fill Rate (L/h)", row=2)
    fig.update_yaxes(title_text="MD Surplus Fill Rate (L/h)", row=3)
    fig.update_yaxes(title_text="Average Return Flow (SLM)", row=4)

    fig.update_traces(xaxis="x4") # unite axes for spikes to be drawn across all. Needs to be the last axis

    fig.update_xaxes(showspikes=True, spikesnap='cursor', spikemode='across',
                spikecolor="grey", spikethickness=1, spikedash='solid')
    fig.update_yaxes(showspikes=True, spikedash='solid',spikemode='across',
                spikecolor="grey",spikesnap="cursor",spikethickness=1)

    # save to html
    fig.write_html('liquid_prod_rate_fig.html',
                    config={'modeBarButtonsToRemove': ['zoomIn',
                                                       'zoomOut',
                                                       'autoScale',
                                                       'select',
                                                       'lasso2d'],
                            'modeBarButtonsToAdd': ['drawopenpath'],
                            'displaylogo': False
                            })
    
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

        # generate figure
        figure.start_draw(t0, t1)

        # output
        ret_int = midas.status_codes["SUCCESS"]
        ret_str = json.dumps({"last": str(datetime.datetime.now())})

    elif cmd== "draw_finished?":
        ret_int = int(not figure.is_alive())
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
