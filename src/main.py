import pandas as pd

from src.Player import Player
from src.Players import Players


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

    serve = {"4": "wide",
             "5": "body",
             "6": "down the t"}

    serve_return_depth = {
        "7": "inside service line",
        "8": "behind service line",
        "9": "deep",
        "0": "unknown"
    }

    shot = {"f": "forehand",
            "b": "backhand",
            "s": "backhand slice",
            "r": "forehand slice",
            "v": "forehand volley",
            "z": "backhand volley",
            "o": "overhead",
            "p": "backhand overhead smash",
            "u": "forehand drop shot",
            "y": "backhand drop shot",
            "l": "forehand lob",
            "m": "backhand lob",
            "h": "forehand half-volley",
            "i": "backhand half-volley",
            "j": "forehand swinging volley",
            "k": "backhand swinging volley",
            "t": "trick shot",
            "q": "unknown"}

    shot_direction = {"1": "deuce side",
                      "2": "down middle",
                      "3": "ad side"}

    point_end = {"@": "unforced error",
                 "#": "forced error",
                 "*": "winner"}

    error = {"n": "net",
             "w": "wide",
             "d": "deep",
             "x": "wide and deep",
             "!": "shank",
             "e": "unknown"}

    optional = {"+": "approach shot",
                   "-": "net",
                   "=": "baseline",
                "^": "drop volley"}

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

    player1_serving = fo_final.loc[fo_final['Svr'] == 1]
    player2_serving = fo_final.loc[fo_final['Svr'] == 2]

    player1_serving_points = player1_serving[['1st', '2nd', 'PtWinner']]
    s1 = player1_serving_points['1st'].fillna("").astype(str)
    s2 = player1_serving_points['2nd'].fillna("").astype(str)

    player1.handle_serve(s1, s2, serve, shot, error)

    for serve in player1.serves:
        print(serve)






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


