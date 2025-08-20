import pandas as pd

from src.EventLogger import Context, Serve, EventLogger, MissType, ServeDirection
from src.Player import Player
import src.codes as codes
from src.dataHandler import create_df

def main():

    df = create_df()

    fo_final = df[df['match_id'].str.contains("20250608", case=False)]

    serve_events = parse_match(fo_final)

    return serve_events






def get_players(match):
    get_match_id_string(match)
    info = parse_match_id(get_match_id_string(match))
    player1 = Player(info[4], info[5])
    player2 = Player(info[6], info[7])
    return player1, player2


def get_match_id_string(match: pd.DataFrame):
    return match.iat[0,0]

def parse_match(match):
    serve_events = EventLogger()
    player1, player2 = get_players(match)

    for index,row in match.iterrows():
        context = parse_context(row, player1, player2)
        if pd.isnull(row['2nd']) or row['2nd'] == '':
            serve = parse_serve(row['1st'], 1)
            serve_row = serve + context
            serve_events.log_serve(serve_row)
        else:
            serve = parse_serve(row['1st'], 1)
            serve_row = serve + context
            serve_events.log_serve(serve_row)
            serve = parse_serve(row['2nd'], 2)
            serve_row = serve + context
            serve_events.log_serve(serve_row)
    return serve_events

#gathers serve info and returns a Serve object
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

    serve_direction = ServeDirection(serve_direction).name # set direction to first serve direction
    is_ace = False  # set ace to false
    is_fault = False
    miss_type = None

    if serve_outcome in error_code:  # if serve is out
        is_fault = True
        miss_type = MissType(serve_outcome).name

    elif serve_outcome == "*":
        is_ace = True

    elif serve_outcome in shot_code:  # first serve made
        pass
    else:

        print("error, first serve not found in: ", serve_direction, serve_outcome)
    return [serve_direction, serve_number, is_fault, miss_type,is_ace,snv]


#gathers context of the point and creates a Context element
def parse_context(row, player1, player2):
    match_id = row['match_id']
    point_id = f'{match_id}-{row["Pt"]}'
    set1 = row['Set1']
    set2 = row['Set2']
    set_score = set1 + "-" + set2
    game_score = row['Gm1'] + "-" + row['Gm2']
    point_score = row['Pts']

    if row['Svr'] == "1":
        server = player1.full_name()
        returner = player2.full_name()
    elif row['Svr'] == "2":
        server = player2.full_name()
        returner = player1.full_name()
    else:
        server = None
        returner = None
        print("no server found")
    if row['PtWinner'] == "1":
        point_winner = player1.full_name()
    elif row['PtWinner'] == "2":
        point_winner = player2.full_name()
    else:
        point_winner = None
        print("no winner found")

    return [match_id, point_id, set_score,game_score, point_score,server,returner,point_winner]


#gets info from match id string
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


