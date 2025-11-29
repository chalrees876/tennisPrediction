# tennis/services/rankings.py

from tennis.models import PlayerRanking
from tennis.services.api_client import TennisAPIClient
from tennis.services.players import ensure_player_from_api


def sync_rankings(tour: str):
    """
    Sync ATP or WTA rankings without ever creating partial player names.
    """
    client = TennisAPIClient()
    data = client.get_rankings()

    # wipe old
    PlayerRanking.objects.filter(tour=tour).delete()

    for row in data:
        player_key = row["player_key"]

        # ⬇️ This ensures full name and bio are fetched before saving ranking
        player = ensure_player_from_api(player_key)

        PlayerRanking.objects.create(
            tour=tour,
            player=player,
            rank=row.get("rank"),
            points=row.get("points"),
        )
