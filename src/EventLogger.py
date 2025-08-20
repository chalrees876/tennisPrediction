from dataclasses import dataclass
from enum import Enum
from typing import Optional
import pandas as pd

from src.Player import Player


columns = ["Serve Direction", "Serve Num", "Is Fault", "Miss Type", "Is Ace", "SNV", "Match Id", "Point Id", "Set Score", "Game Score", "Point Score", "Server", "Returner", "Point Winner"]


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

    def print(self):
        print(self.serve_events)
        for row in self.serve_events:
            if len(row) != 14:
                print(len(row))

    def create_el_df(self):
        return pd.DataFrame(self.serve_events, columns = columns)


