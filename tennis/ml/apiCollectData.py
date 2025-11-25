import csv
import datetime
from typing import Dict, Any, List, Set

from tennis.models import PlayerMatch
from tennis.ml.apiFeatures import get_match_features, get_odds_features


def collect_data(max_matches=20):
    print("Building match features for all matches...")

    MIN_STATS = 5
    output_path = "tennis/data/match_features.csv"

    matches_qs = (
        PlayerMatch.objects
        .filter(
            date__lt=datetime.date.today(),
            tournament__event_type_type="Atp Singles",
        )  # only completed ATP singles matches
        .order_by("-date", "time", "key")
    )

    rows: List[Dict[str, Any]] = []
    all_feature_keys: Set[str] = set()

    total = matches_qs.count()
    num_with_stats = 0
    num_with_enough_stats = 0
    num_with_odds = 0

    for i, match in enumerate(matches_qs.iterator(), start=1):
        if i % 500 == 0:
            print(f"Processed {i}/{total} matches...")

        # --- stats features ---
        stats_feats = get_match_features(match, max_matches=max_matches) or {}

        # --- odds features ---
        odds_feats = get_odds_features(match) or {}

        # If we truly have neither stats nor odds, skip this match entirely
        if not stats_feats and not odds_feats:
            continue

        # count only stats values (non-None) for MIN_STATS reference
        num_stats_values = len([v for v in stats_feats.values() if v is not None])
        has_stats = bool(stats_feats)
        has_enough_stats = num_stats_values >= MIN_STATS
        has_odds = bool(odds_feats)

        if has_stats:
            num_with_stats += 1
        if has_enough_stats:
            num_with_enough_stats += 1
        if has_odds:
            num_with_odds += 1

        # Label for training: 1 if first_player won, else 0
        # (assumes winner is set for completed matches)
        label = 1 if match.winner and match.winner.key == match.first_player.key else 0

        row: Dict[str, Any] = {
            "match_key": match.key,
            "date": match.date.isoformat(),
            "time": match.time.isoformat(),
            "tournament": str(match.tournament),
            "round": match.round,
            "first_player": match.first_player.name,
            "second_player": match.second_player.name,
            "winner_is_first": label,
            "has_stats": int(has_stats),
            "has_enough_stats": int(has_enough_stats),
            "has_odds": int(has_odds),
            "num_stats_values": num_stats_values,
        }

        # Combine stats + odds into one feature space
        combined_feats: Dict[str, Any] = {}
        combined_feats.update(stats_feats)
        combined_feats.update(odds_feats)

        for k, v in combined_feats.items():
            row[k] = v
            all_feature_keys.add(k)

        rows.append(row)

    print(
        f"Built features for {len(rows)} matches.\n"
        f"- With any stats:        {num_with_stats}\n"
        f"- With enough stats (≥{MIN_STATS}): {num_with_enough_stats}\n"
        f"- With odds:             {num_with_odds}"
    )

    # --- write unified CSV ---
    base_cols = [
        "match_key",
        "date",
        "time",
        "tournament",
        "round",
        "first_player",
        "second_player",
        "winner_is_first",
        "has_stats",
        "has_enough_stats",
        "has_odds",
        "num_stats_values",
    ]
    feature_cols = sorted(all_feature_keys)
    fieldnames = base_cols + feature_cols

    print(f"Writing unified features CSV to {output_path}...")

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            out = {col: row.get(col) for col in fieldnames}
            writer.writerow(out)

    print(
        f"Done.\n"
        f"- Rows:    {len(rows)}\n"
        f"- Features: {len(feature_cols)}"
    )
