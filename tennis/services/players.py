# tennis/services/players.py

from datetime import datetime
from typing import Tuple, Optional

from tennis.models import Player
from tennis.services.api_client import TennisAPIClient


def calculate_age(birthdate: str):
    if not birthdate:
        return None
    try:
        d = datetime.strptime(birthdate, "%Y-%m-%d")
        today = datetime.today()
        return today.year - d.year - ((today.month, today.day) < (d.month, d.day))
    except Exception:
        return None


def _extract_player_name(data: dict) -> Optional[str]:
    """
    Try to build a full name from whatever the API sends back.
    Adjust the key names to match your actual API response.
    """
    # Common patterns – tweak to match your API:
    name = (
        data.get("player_full_name")
    )

    # Single-field fallbacks
    return (
        name
    )


def ensure_player_from_api(
    player_key: int,
    fallback_name: Optional[str] = None,
) -> Tuple[Player, bool]:
    """
    Ensure a Player exists with this key.
    - Try the players API for full info (name, country, birthday).
    - Fall back to the short name from fixtures/standings if needed.
    - **Never** save a Player without a name (avoids NOT NULL errors).
    """
    client = TennisAPIClient()
    data = client.get_player_info(player_key) or {}

    age = calculate_age(data.get("birthday"))
    country = data.get("country")

    name = _extract_player_name(data)

    # If API doesn't give us a name, fall back to short name (e.g. "L. Musetti")
    if not name:
        name = fallback_name

    # As a last resort, invent a placeholder so we never violate NOT NULL
    if not name:
        name = f"Player {player_key}"

    player, created = Player.objects.update_or_create(
        key=player_key,
        defaults={
            "name": name,
            "age": age,
            "country": country,
        },
    )
    return player, created