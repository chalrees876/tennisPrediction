# tennis/services/rankings.py
from pprint import pprint

from tennis.models import PlayerRanking, Player
from tennis.services.api_client import TennisAPIClient
from tennis.services.players import ensure_player_from_api


def sync_rankings(tour: str):
    """
    Sync ATP or WTA rankings without ever creating partial player names.
    """
    client = TennisAPIClient()
    data = client.get_rankings()
    for row in data:
        player_key = row["player_key"]
        player = Player.objects.filter(key=player_key).first()
        if not player and player_key is not None:
            # ⬇️ This ensures full name and bio are fetched before saving ranking
            print(f"Player {player_key} not found")
            print("ROW:", row)
            player = ensure_player_from_api(player_key)
        if player_key is not None:
            PlayerRanking.objects.update_or_create(
                league=tour,
                player=player,
                ranking=row.get("place"),
                movement=row.get("movement"),
                points=row.get("points"),
            )
