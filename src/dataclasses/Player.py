from dataclasses import dataclass, field
from typing import Dict

from src.dataclasses.PlayerMatch import PlayerMatch


@dataclass(frozen=True)
class Player:
    name: str
    matches: Dict[str, PlayerMatch] = field(default_factory=dict)

    def get_all_matches(self):
        for match in self.matches.values():
            yield match