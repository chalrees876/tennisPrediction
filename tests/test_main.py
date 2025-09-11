import pytest
import pandas as pd
import src.main as main

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

columns = ['match_id', 'Pt', 'Set1', 'Set2', 'Gm1', 'Gm2', 'Pts', 'Gm#', 'TbSet', 'Svr', '1st', '2nd', 'Notes', 'PtWinner']

def test_create_df():

    #Test to make sure lets (serve hitting the net cord) are removed from the data
    df = main.create_df()
    df = df[df['1st'].str.contains('c') | df['2nd'].str.contains('c')]
    assert df.empty == True

def test_create_serve_df():

    data = [['20250610-M-ITF_Martos-Q2-Preston_Stearns-Alejandro_Lopez_Escribano','1','0','0','0','0','0-0','1',True,'1','6#',None,None,'1']]
    df = pd.DataFrame(data, columns=columns)
    serve_df = main.create_serve_df(df)
    fs = serve_df['1st Is Fault']
    ss = serve_df['2nd Is Fault']

    assert fs.bool() == False
    assert ss.bool() == False

    data = [['20250610-M-ITF_Martos-Q2-Preston_Stearns-Alejandro_Lopez_Escribano', '1', '0', '0', '0', '0', '0-0', '1',True, '1', '6#', '4#', None, '1']]

    serve_df = main.create_serve_df(pd.DataFrame(data, columns=columns))
    fs = serve_df['1st Is Fault']
    ss = serve_df['2nd Is Fault']

    assert fs.bool() == True
    assert ss.bool() == False

    data = [['20250610-M-ITF_Martos-Q2-Preston_Stearns-Alejandro_Lopez_Escribano', '1', '0', '0', '0', '0', '0-0', '1',True, '1', '6#', '4w', None, '2']]

    df = pd.DataFrame(data, columns=columns)

    serve_df = main.create_serve_df(df)
    fs = serve_df['1st Is Fault']
    ss = serve_df['2nd Is Fault']

    assert fs.bool() == True
    assert ss.bool() == True







