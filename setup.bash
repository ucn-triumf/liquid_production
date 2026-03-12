#!/bin/bash
# setup virtual env for autostat

python3 -m venv env
source env/bin/activate
pip install numpy pandas scipy plotly ucnhistory