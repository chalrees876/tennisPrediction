import pandas as pd

from src.Player import Player
from src.Players import Players
import src.codes as codes
from src.Point import Point


def main():

    pd.set_option("display.max_colwidth", None)
    pd.set_option("display.max_columns", None)   # show all columns
    pd.set_option("display.width", None)

    dtypes = {'match_id': "string",
                     'Pt': "Int16",
                     'Set1': "Int16",
                     'Set2': "Int16",
                     'Gm1': "Int16",
                     'Gm2': "Int16",
                     'Pts': "string",
                     'Gm#': "Int16",
                     'TbSet': "boolean",
                     'Svr': "Int16",
                     '1st': "string",
                     '2nd': "string",
                     'Notes': "string",
                     'PtWinner': "Int16"}

    df = pd.read_csv('../data/charting-m-points-2020s.csv', dtype=dtypes)

    df[['1st', '2nd']] = df[['1st', '2nd']].replace({'c':''}, regex=True)

    fo_final = df[df['match_id'].str.contains("20250608", case=False)]

    match_id_string = fo_final['match_id'].unique()

    date, gender, tournament, round_, player1_first_name, player1_last_name, player2_first_name, player2_last_name = parse_match_id(match_id_string)

    players = Players()

    player1 = Player(player1_first_name, player1_last_name)
    players.add(player1)
    player2 = Player(player2_first_name, player2_last_name)
    players.add(player2)

    point = Point(fo_final['Pt'])

    player1_serving = fo_final.loc[fo_final['Svr'] == 1]
    player2_serving = fo_final.loc[fo_final['Svr'] == 2]

    player1_serving_points = player1_serving[['1st', '2nd', 'PtWinner']]
    p1_first_serve = player1_serving_points['1st'].fillna("").astype(str)
    p1_second_serve = player1_serving_points['2nd'].fillna("").astype(str)

    player2_serving_points = player2_serving[['1st', '2nd', 'PtWinner']]
    p2_first_serve = player2_serving_points['1st'].fillna("").astype(str)
    p2_second_serve = player2_serving_points['2nd'].fillna("").astype(str)



    player1.handle_serve(p1_first_serve, p1_second_serve, codes.serve_code, codes.shot_code, codes.error_code)
    player2.handle_serve(p2_first_serve, p2_second_serve, codes.serve_code, codes.shot_code, codes.error_code)

    print(player1.first_name, player1.last_name, "first serve percentage:", player1.first_serve_percent)
    print(player1.first_name, player1.last_name, "second serve percentage:", player1.second_serve_percent)

    print(player2.first_name, player2.last_name, "first serve percentage:", player2.first_serve_percent)
    print(player2.first_name, player2.last_name, "second serve percentage:", player2.second_serve_percent)


    print(player1.full_name(), "aces:", player1.aces, "double faults:", player1.double_faults)
    print(player2.full_name(), "aces:", player2.aces, "double faults:", player2.double_faults)


def parse_match_id(match_id_string):
    s = match_id_string[0].split("-")

    date, gender, tournament, round_, player1, player2 = s

    player1_name = player1.split("_")

    player1_first_name, player1_last_name = player1_name

    player2_name = player2.split("_")

    player2_first_name, player2_last_name = player2_name

    return date, gender, tournament, round_, player1_first_name, player1_last_name, player2_first_name, player2_last_name


if __name__ == '__main__':
    main()


