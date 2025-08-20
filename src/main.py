import pandas as pd

from src.EventLogger import Context, Serve, EventLogger
from src.Player import Player
from src.Players import Players
import src.codes as codes
from src.Point import Point
from src.dataHandler import create_df


def main():

    df = create_df()

    fo_final = df[df['match_id'].str.contains("20250608", case=False)]

    serve_events = EventLogger()

    parse_match(fo_final, serve_events)













def get_match_id_string(match: pd.DataFrame):
    return match.iat[0,0]

def parse_match(match, serve_events):
    if serve_events is None:
        serve_events = EventLogger()

    for index,row in match.iterrows():
        context = parse_context(row)
        if pd.isnull(row['2nd']):
            serve_number = 1
            serve = parse_serve(row['1st'], serve_number)
        else:
            serve_number = 2
            serve = parse_serve(row['2nd'], serve_number)
        serve_events.log_serve(serve, context)


def parse_serve(point, serve_number):
    if point is None:
        return None

    serve_code = codes.serve_code
    error_code = codes.error_code
    shot_code = codes.shot_code
    if "c" in point:
        point = point.replace("c", "")  # removing lets
    serve_direction = point[:1]  # serve direction
    serve_outcome = point[1:2]  # serve outcome

    snv = False  # serve and volley serve = false
    if serve_outcome == "+":
        serve_outcome = point[2:3]
        snv = True

    serve_direction = serve_code[serve_direction]  # set direction to first serve direction
    is_ace = False  # set ace to false
    is_fault = False
    miss_type = None

    if serve_outcome in error_code:  # if serve is out
        is_fault = True
        miss_type = error_code[serve_outcome]

    elif serve_outcome == "*":
        is_ace = True

    elif serve_outcome in shot_code:  # first serve made
        pass
    else:

        print("error, first serve not found in: ", serve_direction, serve_outcome)

    return Serve(serve_direction=serve_direction,serve_num=serve_number, is_fault=is_fault,miss_type=miss_type,is_ace=is_ace,snv=snv)

def parse_context(row):
    match_id = row['match_id']
    point_id = f'{match_id}-{row["Pt"]}'
    set1 = row['Set1']
    set2 = row['Set2']
    set_score = set1 + "-" + set2
    game_score = row['Gm1'] + "-" + row['Gm2']
    point_score = row['Pts']
    date, gender, tournament, round_, player1_first_name, player1_last_name, player2_first_name, player2_last_name = parse_match_id(match_id)
    player1 = Player(player1_first_name, player1_last_name)
    player2 = Player(player2_first_name, player2_last_name)
    if row['Svr'] == "1":
        server = player1
        returner = player2
    elif row['Svr'] == "2":
        server = player2
        returner = player1
    else:
        server = None
        returner = None
        print("no server found")
    if row['PtWinner'] == "1":
        point_winner = player1
    elif row['PtWinner'] == "2":
        point_winner = player2
    else:
        point_winner = None
        print("no winner found")

    return Context(match_id=match_id, point_id=point_id, set_score=set_score, game_score=game_score, point_score=point_score, server=server, returner=returner, point_winner=point_winner)

def parse_match_id(id_: str):
    s = id_.split("-")

    date, gender, tournament, round_, player1, player2 = s

    player1_name = player1.split("_")

    player1_first_name, player1_last_name = player1_name

    player2_name = player2.split("_")

    player2_first_name, player2_last_name = player2_name

    return [date, gender, tournament, round_, player1_first_name, player1_last_name, player2_first_name, player2_last_name]


if __name__ == '__main__':
    main()


