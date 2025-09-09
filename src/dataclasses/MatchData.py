
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MatchData:
    date: datetime
    year: int
    tournament: str
    round: str
    p1: str
    p2: str
    match_id: str