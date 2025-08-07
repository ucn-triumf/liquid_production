export MIDASSYS=/home/ucn/packages/midas
export PYTHONPATH=$PYTHONPATH:$MIDASSYS/python
export PYTHONPATH=$PYTHONPATH:$HOME/.local/lib/python3.6/site-packages/
export PATH=.:$HOME/online/bin:$PATH
export PATH=$PATH:$MIDASSYS/bin
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib


# export VIRTUAL_ENV_DISABLE_PROMPT=1
source ~/python3_env/bin/activate

cd /home/ucn/dfujimoto/liquid_production

python3 liquid_prod_rate.py
