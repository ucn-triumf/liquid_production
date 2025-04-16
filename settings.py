# settings for paths and labels for liquid and flow
# Derek Fujimoto
# Oct 2024

import pandas as pd

# drawing labels
labels = {'ucn2_he4_lvl204_rdlvl_measured': 'MD Level (lvl204)',
          'ucn2_he4_lvl203_rdlvl_measured': '4K Pot Level (lvl203)',
          'ucn2_he4_lvl201_rdlvl_measured': '1K Pot Level (lvl201)',
          'ucn2_he4_lvl202_rdlvl_measured': '1K Pot Level (lvl202)',
          'ucn2_he4_fm207_rdflow_measured': 'Return Flow (fm207) - corrected',
          'ucn2_he4_fm206_rdflow_measured': 'TL Return Flow (fm206)',
          }

# tables to load: level readings
levels = [{'table': 'ucn2epicsothers_measured',
           'columns':['ucn2_he4_lvl204_rdlvl_measured',     # MD
                      'ucn2_he4_lvl203_rdlvl_measured']},   # 4K pot
          {'table': 'ucn2epicsphase2b_measured',
           'columns':['ucn2_he4_lvl201_rdlvl_measured']}    # 1K pot
         ]

flows = [{'table': 'ucn2epicsothers_measured',
          'columns': ['ucn2_he4_fm207_rdflow_measured',
                      'ucn2_he4_fm206_rdflow_measured'],
         }]

# conversions to liquid L
conv = {'ucn2_he4_lvl204_rdlvl_measured': 12.6,
        'ucn2_he4_lvl203_rdlvl_measured': 2.5834,
        'ucn2_he4_lvl201_rdlvl_measured': 0.4519,       
        'ucn2_he4_lvl202_rdlvl_measured': 0.4519,        
        }
conv = pd.Series(conv)


# corrections
corr = {'ucn2_he4_fm207_rdflow_measured': lambda x: x/0.75532 + 3.57196}
