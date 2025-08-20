import pandas as pd

def create_df():
    pd.set_option("display.max_colwidth", None)
    pd.set_option("display.max_columns", None)  # show all columns
    pd.set_option("display.width", None)

    dtypes = {'match_id': "string",
              'Pt': "string",
              'Set1': "string",
              'Set2': "string",
              'Gm1': "string",
              'Gm2': "string",
              'Pts': "string",
              'Gm#': "string",
              'TbSet': "boolean",
              'Svr': "string",
              '1st': "string",
              '2nd': "string",
              'Notes': "string",
              'PtWinner': "string"}

    df = pd.read_csv('../data/charting-m-points-2020s.csv', dtype=dtypes)

    df[['1st', '2nd']] = df[['1st', '2nd']].replace({'c': ''}, regex=True)

    return df