from dataclasses import dataclass
from enum import Enum
from typing import Optional
import pandas as pd

from src.Player import Player


columns = ["Serve Direction", "Serve Num", "Is Fault", "Miss Type", "Is Ace", "SNV", "Match Id", "Point Id", "Set Score", "Game Score", "Point Score", "Server", "Returner", "Point Winner", "Player 1", "Player 2"]


class ServeDirection(Enum):
    WIDE = "4"
    BODY = "5"
    T = "6"

class MissType(Enum):
    NET = "n"
    WIDE = "w"
    DEEP = "d"
    WIDE_DEEP = "x"
    FOOT_FAULT = "g"
    UNKNOWN = "e"
    SHANK = "!"
    TIME_VIOLATION = "V"


@dataclass
class Context:
    match_id: str
    point_id: str
    set_score: str
    game_score: str
    point_score: str
    server: Player
    returner: Player
    point_winner: Player
    player1: Player
    player2: Player

@dataclass
class Serve:
    serve_direction: ServeDirection
    serve_num: int
    is_fault: bool = False
    miss_type: Optional[MissType] = None
    is_ace: bool = False
    snv: bool = False

class EventLogger:
    def __init__(self):
        self.serve_events = []
        self.df = pd.DataFrame()


    def log_serve(self, serve_row):
        self.serve_events.append(serve_row)

    def create_serve_df(self):
        return pd.DataFrame(self.serve_events, columns = columns)

    def get_players(self):
        row0 = self.serve_events[0]
        player1 = row0[14]
        player2 = row0[15]

        return player1, player2


