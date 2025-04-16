# Get calibration of FM207. 
# Logic: if transferline is off and 1K pot empty then FM207 = rate of change in 4K pot
# Derek Fujimoto
# Oct 2024

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import datetime
from scipy.optimize import curve_fit
from toolkit import get_data, get_prod_rate
from settings import *

# time range
t0 = '01:50 Oct 11, 2024'
t1 = '07:00 Oct 11, 2024'
window_size = 30 # min

# read levels data    
df_lvl = get_data(levels, t0, t1)
df_lvl *= conv

# read the flows in liquid L/min
df_flw = get_data(flows, t0, t1)
df_flw /= 745

# get production rates -------------------------------

# figure out the rate of change within each time window
idx_start = df_lvl.index[0]
idx_stop = idx_start + window_size*60
rates = []
while idx_stop <= df_lvl.index[-1]:
    rates.append(get_prod_rate(df_lvl.loc[idx_start:idx_stop], 
                               df_flw.loc[idx_start:idx_stop],
                               do_correction = False))
    idx_start = idx_stop
    idx_stop = idx_start + window_size*60

rates = pd.concat(rates, axis='columns').transpose()
rates.rename(columns=labels, inplace=True)
rates.rename(columns={f'd{key}':f'd{label}' for key, label in labels.items()}, inplace=True)

#rates = get_prod_rate(df_lvl, df_flw)

df = rates[[col for col in rates if 'd' != col[0]]]
ddf = rates[[col for col in rates if 'd' == col[0]]]

rate_level = df['4K Pot Level (lvl203)']+df['1K Pot Level (lvl201)']
rate_flow = df['Return Flow (fm207)']

# fit with linear line
fn = lambda x, a, b: a*x + b
par, cov = curve_fit(fn, -rate_level, rate_flow)
std = np.diag(cov)**0.5

plt.plot(-rate_level, rate_flow, '.')
plt.plot(-rate_level, fn(-rate_level, *par))
plt.xlabel('-1 $\\times$ 4K Pot Level (LVL203) (L/h)')
plt.ylabel('Return Flow (FM207) (liquid L/h)')
plt.title('Comparison during transferline off period')

print(f'Slope = {par[0]:.5f} +/- {std[0]:.5f}\nIntercept = {par[1]:.5f} +/- {std[1]:.5f}')

plt.savefig('test.pdf')


