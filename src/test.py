import pandas as pd

df = pd.read_csv('~/WGU/tennisPrediction/data/matches.csv')

pd.set_option('display.max_columns', None)

print(df[(df['first_serve_pctg'] > 99) & (df['double_faults'] == 0)])