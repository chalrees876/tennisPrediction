# tennis/services/api_sync.py
from pprint import pprint
from typing import Tuple

from tennis.models import Player, Tournament, PlayerMatch
from tennis.services.api_client import TennisAPIClient
from tennis.services.matches import upsert_match_from_api_event


def sync_matches_for_players(date_start: str, date_stop: str) -> Tuple[int, int]:
    """
    Loop over *all players* in our DB, call fixtures API for each player,
    and upsert matches.

    date_start / date_stop: "YYYY-MM-DD"
    """
    client = TennisAPIClient()
    total_created = 0
    total_updated = 0

    for player in Player.objects.filter(playerranking__league="ATP").order_by('-playerranking__ranking'):
        print(f"Syncing {player.name}...")
        events = client.get_fixtures_for_player(
            player_key=player.key,
            date_start=date_start,
            date_stop=date_stop,
        )
        player_created = 0
        player_updated = 0
        for event in events:
            match, created = upsert_match_from_api_event(event)
            if created:
                total_created += 1
                player_created += 1
                print(f"created {match}")
            else:
                total_updated += 1
                player_updated += 1
                print(f"updated {match}")
        print(f"Matches: {player_created} created, {player_updated} updated")

    return total_created, total_updated
