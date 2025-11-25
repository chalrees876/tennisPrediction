from pprint import pprint

import pytz
from django.core.management import BaseCommand
from django.db.models import Q, Avg, Count
from datetime import datetime, timedelta
from typing import Dict, Any

from tennis.models import PlayerMatch, Player, MatchStatistic


def get_match_features(match, max_matches=20):
    tz = pytz.timezone("Europe/Berlin")

    return build_match_features(match, max_matches=max_matches)

def build_match_features(
    match: PlayerMatch,
    max_matches: int = 10,
) -> Dict[str, Any]:
    """
    Build comparative features for a single match:
      - p1_*   : player1 aggregated stats
      - p2_*   : player2 aggregated stats
      - diff_* : p1 - p2   (ONLY for avg_* fields)
      - ratio_*: p1 / p2   (ONLY for avg_* fields)
    """

    p1 = match.first_player
    p2 = match.second_player

    # use last `max_matches` for each player, prior to this match
    p1_stats = get_recent_stats_for_player(p1, match, n=max_matches)
    p2_stats = get_recent_stats_for_player(p2, match, n=max_matches)

    features: Dict[str, Any] = {}

    # Union of all stat keys for both players
    all_keys = set(p1_stats.keys()) | set(p2_stats.keys())

    for key in all_keys:
        p1_val = p1_stats.get(key)
        p2_val = p2_stats.get(key)

        # Always store raw player features
        features[f"p1_{key}"] = p1_val
        features[f"p2_{key}"] = p2_val

        # --- Only do diff/ratio for avg_* fields, not counts ---
        is_avg_field = key.endswith("__avg_percent") or key.endswith("__avg_number")
        if not is_avg_field:
            continue

        if p1_val is None or p2_val is None:
            continue

        # Difference (p1 - p2)
        features[f"diff_{key}"] = p1_val - p2_val

        # Ratio (p1 / p2), where possible
        if p2_val != 0:
            features[f"ratio_{key}"] = p1_val / p2_val

    return features

def get_recent_stats_for_player(
    player: Player,
    as_of_match: PlayerMatch,
    n: int = 10,
) -> Dict[str, float]:
    """
    Aggregate last N matches for a player BEFORE a given match.
    Returns keys like:
      Service__Aces__avg_number
      Service__Aces__count
      Service__1st_Serve_Points_Won__avg_percent
      ...
    """

    # 1) recent matches BEFORE this match (date + time)
    recent_matches = (
        PlayerMatch.objects
        .filter(
            Q(first_player=player) | Q(second_player=player),
            Q(date__lt=as_of_match.date),
        )
        .order_by("-date", "-time")[:n]
    )

    if not recent_matches:
        return {}

    # 2) match-period stats for this player over those matches
    stats_qs = (
        MatchStatistic.objects
        .filter(
            match__in=recent_matches,
            player=player,
        )
        .values("category", "name")
        .annotate(
            avg_percent=Avg("value_percent"),
            avg_number=Avg("value_number"),
            count=Count("id"),
        )
    )

    features: Dict[str, float] = {}

    for row in stats_qs:
        cat = row["category"]          # e.g. "Service"
        name = row["name"]             # e.g. "1st Serve Points Won"
        avg_pct = row["avg_percent"]
        avg_num = row["avg_number"]
        cnt = row["count"]

        base = f"{cat}__{name}".replace(" ", "_")

        if avg_pct is not None:
            features[f"{base}__avg_percent"] = avg_pct
        if avg_num is not None:
            features[f"{base}__avg_number"] = avg_num

        # sample size info
        features[f"{base}__count"] = float(cnt)

    return features

def get_odds_features(match):
    """
        Extract simple pre-match odds features from match.odds_raw.

        Assumes odds_raw is either:
          - the full API response you pasted (with "success" and "result"), or
          - just the inner event dict (i.e., result[event_key]).

        We map "Home" -> first_player, "Away" -> second_player.
        """

    raw = match.odds_raw
    if not raw:
        return {}

    data = raw

    # Case 1: full API response (with "result" and event key)
    if isinstance(data, dict) and "result" in data:
        result = data.get("result") or {}
        if not result:
            return {}
        # Just grab the first (and in practice only) event entry
        # e.g. result["159923"]
        data = next(iter(result.values()))

    if not isinstance(data, dict):
        return {}

    # We care only about the main "Home/Away" market for now
    home_away = data.get("Home/Away")
    if not home_away:
        return {}

    home_dict = home_away.get("Home") or {}
    away_dict = home_away.get("Away") or {}

    if not home_dict or not away_dict:
        return {}

    def parse_price_map(price_map: dict) -> float:
        """
        Given a dict like {"bwin": "2.40", "bet365": "2.50", ...},
        pick a representative decimal odd.
        Preference: bet365, else average of all.
        """
        if not price_map:
            return None

        # Prefer bet365 if present
        if "bet365" in price_map:
            try:
                return float(price_map["bet365"])
            except (TypeError, ValueError):
                pass

        # Otherwise average all numeric values
        vals = []
        for v in price_map.values():
            try:
                vals.append(float(v))
            except (TypeError, ValueError):
                continue
        if not vals:
            return None
        return sum(vals) / len(vals)

    p1_odds = parse_price_map(home_dict)
    p2_odds = parse_price_map(away_dict)

    if p1_odds is None or p2_odds is None:
        return {}

    def implied_prob(dec_odds: float) -> float:
        if dec_odds <= 0:
            return None
        return 1.0 / dec_odds

    p1_prob = implied_prob(p1_odds)
    p2_prob = implied_prob(p2_odds)

    feats: Dict[str, Any] = {
        "odds_p1_moneyline": p1_odds,
        "odds_p2_moneyline": p2_odds,
        "odds_p1_implied_prob": p1_prob,
        "odds_p2_implied_prob": p2_prob,
    }

    if p1_prob is not None and p2_prob is not None:
        feats["odds_implied_prob_diff"] = p1_prob - p2_prob

    return feats

if __name__ == "__main__":
    get_match_features()