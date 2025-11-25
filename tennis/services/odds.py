# tennis/services/odds.py

from datetime import datetime, timedelta
import os
from typing import Iterable, Optional, Tuple, List

import requests
from django.conf import settings
from django.db import transaction

from tennis.models import Tournament, PlayerMatch, MatchStatistic
from tennis.services.api_client import TennisAPIClient


def get_tennis_api_key() -> str:
    """
    Resolve the tennis API key from settings or environment.
    Raise RuntimeError if missing.
    """
    # Prefer Django settings if you want
    key = getattr(settings, "API_KEY", None) or os.getenv("API_KEY")
    if not key:
        raise RuntimeError("Tennis API key not configured (TENNIS_API_KEY or API_KEY).")
    return key


def get_tournaments_needing_odds(
    *,
    tournament_key: Optional[int] = None,
    event_type: str = "Atp Singles",
) -> Iterable[int]:
    """
    Return a sorted list of tournament_key values for which
    at least one PlayerMatch has odds_raw is NULL, filtered by event type.
    """
    qs = PlayerMatch.objects.filter(odds_raw__isnull=True)

    if tournament_key is not None:
        qs = qs.filter(tournament__tournament_key=tournament_key)

    if event_type:
        qs = qs.filter(tournament__event_type_type=event_type)

    raw_keys = list(qs.values_list("tournament__tournament_key", flat=True))
    return sorted(set(raw_keys))


@transaction.atomic
def sync_odds_for_single_tournament(
    tournament_key: int,
    *,
    api_key: Optional[str] = None,
    date_start: str = "1800-01-01",
    date_stop: Optional[str] = None,
) -> Tuple[int, int]:
    """
    Call get_odds for a single tournament and attach odds to PlayerMatch rows.

    Returns:
        (updated_count, skipped_count)
    """
    if api_key is None:
        api_key = get_tennis_api_key()

    if date_stop is None:
        date_stop = datetime.today() + timedelta(days=30)

    base_qs = Tournament.objects.filter(tournament_key=tournament_key)
    if not base_qs.exists():
        # Nothing to do if we don't have this tournament locally
        return 0, 0

    # Prefer ATP singles if present
    atp_qs = base_qs.filter(event_type_type="Atp Singles")
    tournaments_qs = atp_qs if atp_qs.exists() else base_qs

    tournament = tournaments_qs.order_by("-name").first()

    url = (
        "https://api.api-tennis.com/tennis/"
        f"?method=get_odds&APIkey={api_key}"
        f"&tournament_key={tournament_key}"
        f"&date_start={date_start}"
        f"&date_stop={date_stop}"
    )

    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        # On request failure, do nothing but report zero updates
        return 0, 0

    if not data or data.get("success") != 1:
        return 0, 0

    result = data.get("result") or {}
    if not isinstance(result, dict):
        return 0, 0

    updated = 0
    skipped = 0

    for match_key_str, odds_payload in result.items():
        try:
            match_key = int(match_key_str)
        except (TypeError, ValueError):
            skipped += 1
            continue

        try:
            match = PlayerMatch.objects.get(key=match_key)
        except PlayerMatch.DoesNotExist:
            skipped += 1
            continue

        if match.statistics_raw is not None:
            sync_match_stats(match)
            skipped += 1
            continue

        match.odds_raw = odds_payload
        match.save(update_fields=["odds_raw"])
        updated += 1

    return updated, skipped


def sync_odds_for_missing_matches(
    *,
    tournament_key: Optional[int] = None,
    event_type: str = "Atp Singles",
    api_key: Optional[str] = None,
) -> Tuple[int, int, int]:
    """
    High-level service method.

    - Finds tournaments that have matches with odds_raw IS NULL.
    - For each tournament, calls the odds API and updates PlayerMatch.odds_raw.

    Returns:
        (num_tournaments, total_updated_matches, total_skipped_matches)
    """
    if api_key is None:
        api_key = get_tennis_api_key()

    tournament_keys = get_tournaments_needing_odds(
        tournament_key=tournament_key,
        event_type=event_type,
    )

    total_updated = 0
    total_skipped = 0

    for t_key in tournament_keys:
        updated, skipped = sync_odds_for_single_tournament(
            t_key,
            api_key=api_key,
        )
        total_updated += updated
        total_skipped += skipped

    return len(tournament_keys), total_updated, total_skipped

def sync_odds_for_api_tournaments(
    *,
    event_type_key: Optional[int] = None,
    api_key: Optional[str] = None,
) -> Tuple[int, int, int]:
    """
    Fetch all tournaments from the API (optionally filtered by event_type_key)
    and run sync_odds_for_single_tournament for each.

    Returns:
        (num_tournaments, total_updated_matches, total_skipped_matches)
    """
    if api_key is None:
        api_key = get_tennis_api_key()

    client = TennisAPIClient(api_key=api_key)
    tournaments = client.get_tournaments(event_type_key=265)

    total_updated = 0
    total_skipped = 0

    for t in tournaments:
        # API gives keys as strings; cast to int
        try:
            t_key = int(t["tournament_key"])
        except (KeyError, TypeError, ValueError):
            continue

        updated, skipped = sync_odds_for_single_tournament(
            t_key,
            api_key=api_key,
        )
        total_updated += updated
        total_skipped += skipped

    return len(tournaments), total_updated, total_skipped

def sync_match_stats(match: PlayerMatch):
    """
    Turn the event['statistics'] JSON into MatchStatistic rows.
    Some matches won't have any statistics; then this is a no-op.
    """

    # Clear old stats first
    MatchStatistic.objects.filter(match=match).delete()
    if not match.statistics_raw:
        return

    to_create: List[MatchStatistic] = []

    # Map player_key from stats to Player object once
    player_map = {
        match.first_player.key: match.first_player,
        match.second_player.key: match.second_player,
    }

    for s in match.statistics_raw:
        player_key = s.get("player_key")
        player = player_map.get(player_key)
        if player is None:
            # Unexpected key; skip
            continue

        period = s.get("stat_period", "match")
        category = s.get("stat_type", "")
        name = s.get("stat_name", "")

        value_raw = s.get("stat_value", "") or ""

        # Parse value_raw
        value_percent = None
        value_number = None

        if value_raw.endswith("%"):
            # e.g. "63%" -> 63.0
            try:
                value_percent = float(value_raw.rstrip("%"))
            except ValueError:
                pass
        else:
            # Try to parse as number (int or float)
            try:
                value_number = float(value_raw)
            except (TypeError, ValueError):
                pass

        stat_won = s.get("stat_won")
        stat_total = s.get("stat_total")

        # Ensure int or None
        stat_won = int(stat_won) if stat_won is not None else None
        stat_total = int(stat_total) if stat_total is not None else None

        to_create.append(
            MatchStatistic(
                match=match,
                player=player,
                period=period,
                category=category,
                name=name,
                value_raw=value_raw,
                value_percent=value_percent,
                value_number=value_number,
                stat_won=stat_won,
                stat_total=stat_total,
            )
        )

    if to_create:
        MatchStatistic.objects.bulk_create(to_create)