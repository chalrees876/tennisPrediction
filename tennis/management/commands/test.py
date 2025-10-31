from collections import defaultdict
from datetime import date
from typing import Dict, Iterable, Tuple, List, Any

from django.core.management import BaseCommand
from django.db import transaction, connections
from django.db.models import F, Q
from django.db.models.functions import Least, Greatest

from tennis.models import (
    PlayerMatch,
    PlayerMatchServeStats,
    PlayerMatchReturnStats,
)

# ---------- Helpers ----------

def _canon_pair_ids(a_id: int, b_id: int) -> Tuple[int, int]:
    return (a_id, b_id) if a_id <= b_id else (b_id, a_id)

def _is_better_keeper(a: PlayerMatch, b: PlayerMatch) -> bool:
    """
    Heuristic: row with a score (completed info) or with any children wins.
    Otherwise earliest (lowest id) wins.
    """
    a_children = (
        PlayerMatchServeStats.objects.filter(match=a).exists() or
        PlayerMatchReturnStats.objects.filter(match=a).exists()
    )
    b_children = (
        PlayerMatchServeStats.objects.filter(match=b).exists() or
        PlayerMatchReturnStats.objects.filter(match=b).exists()
    )
    a_score = bool((a.score or "").strip())
    b_score = bool((b.score or "").strip())

    # Prefer child presence
    if a_children != b_children:
        return a_children
    # Prefer having a score
    if a_score != b_score:
        return a_score
    # Tie-breaker: oldest id
    return a.id < b.id

def _safe_assign_fields(dst, src, allowed_fields: Iterable[str]):
    """
    Copy non-null, type-compatible fields from src -> dst for the given field names.
    Avoids errors like "expected int got '1/4'".
    """
    for name in allowed_fields:
        if not hasattr(src, name) or not hasattr(dst, name):
            continue
        val = getattr(src, name)
        if val is None:
            continue
        # type guard: don't assign strings to numeric columns, etc.
        dst_field = type(getattr(dst, name, None))
        # If destination currently has value, keep it; else try to set if type compatible
        cur = getattr(dst, name, None)
        if cur is not None:
            continue
        # Very light type check: avoid accidental "1/4" into int/float
        if isinstance(cur, (int, float)) or isinstance(val, (int, float)):
            if not isinstance(val, (int, float)):
                continue
        setattr(dst, name, val)

def _merge_or_drop_child(child_model, dup_child, keeper_match):
    """
    Move child's data to keeper child if keeper lacks it; else drop duplicate.
    Assumes a 1-1 relationship per match table (which is typical here).
    """
    keeper_child, created = child_model.objects.get_or_create(match=keeper_match)
    # Merge a few representative numeric fields safely (extend as needed)
    # You can expand these to any numeric fields you keep in those models.
    numeric_like = []
    if child_model is PlayerMatchServeStats:
        numeric_like = [
            'dominance_ratio', 'ace_pctg', 'df_pctg', 'fs_pctg', 'fs_w_pctg',
            'ss_w_pctg', 'bp_saved', 'bp_faced'
        ]
    elif child_model is PlayerMatchReturnStats:
        numeric_like = [
            'dominance_ratio', 'total_p_w', 'return_p_w', 'v_ace_pctg',
            'v_fs_pctg', 'v_ss_pctg', 'bp_conv', 'bp_chances'
        ]
    _safe_assign_fields(keeper_child, dup_child, numeric_like + ['time'])
    keeper_child.save()
    dup_child.delete()

# ---------- Command ----------

class Command(BaseCommand):
    help = "De-duplicate PlayerMatch rows by unordered player/opponent within (tournament, date, round)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show what would happen without writing.")
        parser.add_argument("--since", type=str, default="", help="Only consider matches on/after YYYY-MM-DD.")
        parser.add_argument("--limit", type=int, default=0, help="Limit number of duplicate groups to process.")
        parser.add_argument("--verbose", action="store_true", help="Print per-group actions.")

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        verbose = opts["verbose"]
        since_str = opts["since"]
        limit = opts["limit"]

        base_qs = PlayerMatch.objects.all()
        if since_str:
            try:
                y, m, d = map(int, since_str.split("-"))
                base_qs = base_qs.filter(date__gte=date(y, m, d))
            except Exception:
                self.stdout.write(self.style.WARNING(f"Invalid --since '{since_str}', ignoring."))

        # Annotate canonical pair ids so we can group orientation-agnostically
        qs = (
            base_qs
            .annotate(player_lo=Least(F("player_id"), F("opponent_id")))
            .annotate(player_hi=Greatest(F("player_id"), F("opponent_id")))
            .values("tournament_id", "date", "round", "player_lo", "player_hi", "id")
            .order_by("tournament_id", "date", "round", "player_lo", "player_hi", "id")
        )

        # Gather groups
        groups: Dict[Tuple[int, date, Any, int, int], List[int]] = defaultdict(list)
        for row in qs:
            key = (row["tournament_id"], row["date"], row["round"], row["player_lo"], row["player_hi"])
            groups[key].append(row["id"])

        # Filter to groups that have duplicates
        dup_groups = [(k, ids) for k, ids in groups.items() if len(ids) > 1]
        total_groups = len(dup_groups)
        if limit and limit > 0:
            dup_groups = dup_groups[:limit]

        self.stdout.write(self.style.NOTICE(f"Found {total_groups} duplicate groups; processing {len(dup_groups)}."))

        processed = 0
        removed_rows = 0
        fixed_children = 0

        for key, ids in dup_groups:
            tournament_id, m_date, m_round, lo_id, hi_id = key
            matches = list(
                PlayerMatch.objects.filter(id__in=ids)
                .select_related("player", "opponent", "tournament")
                .order_by("id")
            )
            if len(matches) <= 1:
                continue

            # Pick keeper by heuristic
            keeper = matches[0]
            for m in matches[1:]:
                if _is_better_keeper(m, keeper):
                    keeper = m

            dups = [m for m in matches if m.id != keeper.id]

            if verbose:
                self.stdout.write(
                    f"Group {key}: keep #{keeper.id} ({keeper.player_id} vs {keeper.opponent_id}), remove {[m.id for m in dups]}"
                )

            if dry:
                processed += 1
                continue

            with transaction.atomic():
                # Reassign/merge children from each dup, then delete dup
                for dup in dups:
                    # Merge ServeStats
                    for ch in PlayerMatchServeStats.objects.filter(match=dup):
                        _merge_or_drop_child(PlayerMatchServeStats, ch, keeper)
                        fixed_children += 1
                    # Merge ReturnStats
                    for ch in PlayerMatchReturnStats.objects.filter(match=dup):
                        _merge_or_drop_child(PlayerMatchReturnStats, ch, keeper)
                        fixed_children += 1
                    dup.delete()
                    removed_rows += 1

            processed += 1

        self.stdout.write(self.style.SUCCESS(
            f"Done. Groups processed: {processed}; duplicate rows removed: {removed_rows}; child rows reconciled: {fixed_children}."
        ))