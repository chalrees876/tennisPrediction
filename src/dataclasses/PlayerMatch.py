from dataclasses import dataclass

from src.dataclasses.MatchData import MatchData


@dataclass(frozen=True)
class PlayerMatch:
    name: str
    first_serve_pctg: float
    second_serve_pctg: float
    double_faults: int
    win: bool
    match_data: MatchData