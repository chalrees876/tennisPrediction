from datetime import datetime

import pandas as pd

import os, sys, django

# 1) Make sure Python can find your project root (the folder with manage.py)
sys.path.append('~/WGU/tennisPrediction')

# 2) Point to your settings module: "<project_package>.settings"
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')  # adjust if not "config"

# 3) Load Django apps/settings
django.setup()


import src.codes.codes as codes
from src.initializing.dataHandler import create_df
from natsort import natsort_keygen
import re
from tennis.models import Tournament, Match, Player


def main():

    df = create_df()
    print(df['match_id'].nunique())

    serve_df = create_serve_df(df)


    create_players(serve_df)

    matches = Match.objects.all()
    ps = []
    p_fs_pcts = []
    p_ss_pcts = []
    p_dfs = []
    m = []
    wl = []

    for match in matches:
        m.append(match.match_id)
        m.append(match.match_id)

        player1 = match.player1.name
        ps.append(player1)
        player2 = match.player2.name
        ps.append(player2)

        p1_fs_pct = match.p1_first_serve_pctg
        p_fs_pcts.append(p1_fs_pct)
        p2_fs_pct = match.p2_first_serve_pctg
        p_fs_pcts.append(p2_fs_pct)

        p1_ss_pct = match.p1_second_serve_pctg
        p_ss_pcts.append(p1_ss_pct)
        p2_ss_pct = match.p2_second_serve_pctg
        p_ss_pcts.append(p2_ss_pct)

        p1_df = match.p1_double_faults
        p_dfs.append(p1_df)
        p2_df = match.p2_double_faults
        p_dfs.append(p2_df)

        if match.winner == match.player1:
            wl.append(True)
            wl.append(False)
        else:
            wl.append(False)
            wl.append(True)

    data = {'Player': ps,
            'Match': m,
            'first_serve_pctg': p_fs_pcts,
            'second_serve_pctg': p_ss_pcts,
            'double_faults': p_dfs,
            'win': wl}

    new_df = pd.DataFrame(data)
    new_df.to_csv('~/WGU/tennisPrediction/data/matches.csv', index=False)



def create_players(df):
    for match_id, g in df.groupby('match_id'):
        match_id_string = g['match_id'].unique()[0]
        pattern = r'(?P<date>\d{8})-M-(?P<tournament>[^-]+)-(?P<round>[^-]+)-(?P<p1>[^-]+)-(?P<p2>[^-]+)$'
        m = re.search(pattern, match_id_string)
        g = g.sort_values(by=['Pt'], key=natsort_keygen())
        if m is None:
            print("Incorrect format", match_id_string)
        else:
            date = m.group("date")
            date_format = "%Y%m%d"
            date = datetime.strptime(date, date_format)
            year = date.year
            tournament = m.group("tournament").replace("_", " ")
            _round = m.group("round").replace("_", " ")
            p1 = m.group("p1").replace("_", " ")
            p2 = m.group("p2").replace("_", " ")

            p1_winner = bool(g['PtWinner'].tail(1).str.contains("1").any())
            p2_winner = bool(g['PtWinner'].tail(1).str.contains("2").any())

            t, _ = Tournament.objects.update_or_create(name=tournament, year=year)
            p1_object, _ = Player.objects.update_or_create(name=p1)
            p2_object, _ = Player.objects.update_or_create(name=p2)

            if p1_winner:
                winner = p1_object
                loser = p2_object
            if p2_winner:
                winner = p2_object
                loser = p1_object

            p1_first_serve_pctg, p1_second_serve_pctg, p1_double_faults = get_serve_percents(g, "1")
            p2_first_serve_pctg, p2_second_serve_pctg, p2_double_faults = get_serve_percents(g, "2")



            match, created = Match.objects.update_or_create(
                player1 = p1_object,
                player2 = p2_object,
                tournament = t,
                defaults={
                    "match_id": match_id_string,
                    "round": _round,
                    "winner":winner,
                "loser":loser,
                "p1_first_serve_pctg" : p1_first_serve_pctg,
                "p2_first_serve_pctg" : p2_first_serve_pctg,
                "p1_second_serve_pctg" : p1_second_serve_pctg,
                "p2_second_serve_pctg" : p2_second_serve_pctg,
                "p1_double_faults" : p1_double_faults,
                "p2_double_faults" : p2_double_faults
                }
            )

            match.full_clean()
            match.save()


def get_serve_percents(df: pd.DataFrame, player_number):
    df = df[df['Svr'] == player_number]
    total_first_serves = len(df)
    first_serves_in = len(df[~df['1st Is Fault']])
    first_serve_pctg = round(first_serves_in / total_first_serves * 100, 1)
    df_second_serves = df[df['1st Is Fault']]
    total_second_serves = len(df_second_serves)
    second_serves_in = len(df_second_serves[~df_second_serves['2nd Is Fault']])
    if total_second_serves != 0:
        second_serve_pctg = round(second_serves_in / total_second_serves * 100, 1)
    else:
        second_serve_pctg = 100
    double_faults = len(df_second_serves[df_second_serves['2nd Is Fault']])

    return first_serve_pctg, second_serve_pctg, double_faults


def create_serve_df(df: pd.DataFrame) -> pd.DataFrame:
    set_serve_direction(df)
    set_is_fault_and_snv(df)
    set_is_ace(df)
    return df

def set_is_ace(df):
    df['1st Is Ace'] = df['1st'].str[1] == '*'
    df['2nd Is Ace'] = df['2nd'].str[1] == '*'

def set_miss_type(df: pd.DataFrame) -> pd.DataFrame:
    df['1st Miss Type'] = df['1st'].str[1].map(codes.error_code)
    df['2nd Miss Type'] = df['2nd'].str[1].map(codes.error_code)
    return df

def set_is_fault_and_snv(df: pd.DataFrame) -> pd.DataFrame:
    #serve and volley
    first_snv = df['1st'].str[1].map(codes.optional_code)
    second_snv = df['2nd'].str[1].map(codes.optional_code)
    first_snv = pd.notnull(first_snv)
    second_snv = pd.notnull(second_snv)
    df['First SNV'] = first_snv
    df['Second SNV'] = second_snv

    #regular Fault
    copy = df.copy()
    copy['1st'] = copy['1st'].str.replace('+', '')
    copy['2nd'] = copy['2nd'].str.replace('+', '')
    df['1st Is Fault'] = pd.notnull(df['2nd'])

    #if the server won the point
    if (df['PtWinner'].str.contains("1").bool() == df['Svr'].str.contains("1").bool()) | (df['PtWinner'].str.contains("2").bool() == df['Svr'].str.contains("2").bool()):
        df['2nd Is Fault'] = False
    else:
        df['2nd Is Fault'] = pd.notnull(copy['2nd'].str[1].map(codes.error_code))
    return df

def set_serve_direction(df):
    serve_code = codes.serve_code
    first_serve_code = df['1st'].str[0]
    first_serve_code = first_serve_code.map(serve_code).fillna("Not Found")
    # Translate code → direction using the dictionary
    df['1st Serve Direction'] = first_serve_code

    second_serve_code = df['2nd'].str[0]
    df['2nd Serve Direction'] = second_serve_code

    return df


if __name__ == '__main__':
    main()


