from dataclasses import dataclass
from enum import Enum
from typing import Optional
import pandas as pd

from src.Player import Player


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


    def log_serve(self, serve_row):
        self.serve_events.append([serve_row])

    def print(self):
        for row in self.serve_events:
            print(row)
