# tennis/services/matches.py

from datetime import datetime
from typing import Dict, Tuple

from django.db import transaction

from tennis.models import PlayerMatch, Tournament
from tennis.services.players import ensure_player_from_api
from tennis.utils.scoring import normalize_api_score_line


@transaction.atomic
def upsert_match_from_api_event(event: Dict) -> Tuple[PlayerMatch, bool]:
    """
    Take a single api-tennis event dict and upsert Tournament, two Players, and a PlayerMatch.
    """
    # --- Tournament ---
    tournament, _ = Tournament.objects.update_or_create(
        tournament_key=event["tournament_key"],
        defaults={
            "name": event.get("tournament_name"),
            "event_type_type": event.get("event_type_type"),
        },
    )

    # NOTE: pass the short names as fallbacks so we never create nameless players
    p1, _ = ensure_player_from_api(
        event["first_player_key"],
        fallback_name=event.get("event_first_player"),
    )
    p2, _ = ensure_player_from_api(
        event["second_player_key"],
        fallback_name=event.get("event_second_player"),
    )

    # --- Date & time ---
    date_str = event.get("event_date")  # "2025-10-23"
    time_str = event.get("event_time") or "00:00"

    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        d = None
    try:
        t = datetime.strptime(time_str, "%H:%M").time()
    except Exception:
        t = None

    # --- Winner ---
    winner = None
    if event.get("event_winner") == "First Player":
        winner = p1
    elif event.get("event_winner") == "Second Player":
        winner = p2

    # --- Score line ---
    score_line = normalize_api_score_line(event.get("scores") or [])

    # --- Upsert match ---
    match, created = PlayerMatch.objects.update_or_create(
        key=event["event_key"],
        defaults={
            "tournament": tournament,
            "first_player": p1,
            "second_player": p2,
            "winner": winner,
            "event_type": event.get("event_type_type"),
            "round": event.get("tournament_round"),
            "date": d,
            "time": t,
            "score_line": score_line,
            "status": event.get("event_status"),
        },
    )

    return match, created
