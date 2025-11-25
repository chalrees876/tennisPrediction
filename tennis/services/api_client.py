# tennis/services/api_client.py
from datetime import datetime, timedelta
import os
from typing import Any, Dict, List, Optional

import requests


class TennisAPIClient:
    BASE_URL = "https://api.api-tennis.com/tennis/"

    def __init__(self, api_key: Optional[str] = None, session: Optional[requests.Session] = None):
        self.api_key = api_key or os.environ.get("API_KEY")
        if not self.api_key:
            raise RuntimeError("TENNIS_API_KEY not set in environment.")
        self.session = session or requests.Session()

    def _get(self, **params) -> List[Dict[str, Any]]:
        full_params = {
            "APIkey": self.api_key,
            **params,
        }
        resp = self.session.get(self.BASE_URL, params=full_params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(f"Tennis API error: {data}")
        result = data.get("result") or []
        if isinstance(result, dict):
            # some endpoints return dict keyed by id
            return list(result.values())
        return result

    # ---- Matches / fixtures by date range ----
    def get_events_by_date_range(self, date_start: str, date_stop: str) -> List[Dict[str, Any]]:
        """
        Adjust 'method' and params to the real endpoint you use.
        These names assume something like get_events / from_date / to_date.
        """
        return self._get(
            method="get_fixtures",  # or your actual method name
            date_start=date_start,
            date_stop=date_stop,
            event_type_key="265",
            timezone="Europe/Berlin",
        )

    # ---- Player info (full names, country, birthday, etc.) ----
    def get_player_info(self, player_key: int) -> Dict[str, Any]:
        results = self._get(
            method="get_players",
            player_key=player_key,
        )
        # most endpoints return a list; if not, you can tweak this
        if not results:
            raise RuntimeError(f"No player info found for key={player_key}")
        return results[0]

    # ---- Odds for a tournament (optional) ----
    def get_odds_for_tournament(self, tournament_key: int) -> List[Dict[str, Any]]:
        return self._get(
            method="get_odds",  # adjust to real odds endpoint
            tournament_key=tournament_key,
            date_start="1999-01-01",
            date_stop=datetime.today().date() + timedelta(days=30)
        )

    def get_fixtures_for_player(self, player_key: int, date_start: str, date_stop: str):
        """
        Wraps the fixtures endpoint filtered by player.
        Adjust 'method' / param names to match the real API docs.
        """
        return self._get(
            method="get_fixtures",        # or whatever the fixtures method is
            player_key=player_key,
            date_start=date_start,
            date_stop=date_stop,
        )

    def get_rankings(self) -> List[Dict[str, Any]]:
        return self._get(
            method="get_standings", event_type="ATP"
        )

    def get_tournaments(self, event_type_key: int = 265):
        params = {
            "method": "get_tournaments",
        }
        return self._get(method="get_tournaments", event_type_key=event_type_key)

