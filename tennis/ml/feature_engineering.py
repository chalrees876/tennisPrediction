from collections import OrderedDict
from datetime import timedelta
import datetime
from django.db.models import Avg, Q, Max
from typing import Dict, Tuple, Optional, List

from tennis.models import (
    PlayerMatch,
    PlayerMatchServeStats,
    PlayerMatchReturnStats,
)

try:
    from tennis.models import PlayerEloHistory
except Exception:
    PlayerEloHistory = None

try:
    from tennis.models import PlayerRankHistory
except Exception:
    PlayerRankHistory = None


class TennisFeatureEngineer:
    """
    Strictly pre-match features (no leakage):
      - Only rows with date < match.date
      - Exclude the target match from aggregates
    """

    def __init__(self, window_days: int = 250):
        self.window_days = window_days
        self._recent_ids_cache = {}  # (player_id, date) -> list(match_ids)

    # ---------- Public ----------

    def create_match_features(self, match, include_adjusted: bool = False) -> Dict:
        try:
            p1, p2 = match.player, match.opponent
            match_date = match.date
            if match_date is None:
                match_date = datetime.date.today()
            exclude_id = match.id

            # per-player feature dicts
            p1_feat = self._player_feats(p1, match_date, exclude_id)
            p2_feat = self._player_feats(p2, match_date, exclude_id)

            # basic diffs
            f = OrderedDict()
            f["h2h_win_ratio_diff"]     = self._h2h_win_ratio(p1, p2, match_date)
            f["h2h_recent_momentum"]    = self._h2h_recent_momentum(p1, p2, match_date)
            f["recent_form_diff"]       = p1_feat["recent_form"] - p2_feat["recent_form"]
            f["win_rate_diff"]          = p1_feat["win_rate"]    - p2_feat["win_rate"]
            f["serve_rating_diff"]      = p1_feat["serve_rating"]- p2_feat["serve_rating"]
            f["bp_conv_pctg_diff"]      = p1_feat["bp_conv_p"]   - p2_feat["bp_conv_p"]
            f["dom_ratio_diff"]         = p1_feat["dominance_ratio"] - p2_feat["dominance_ratio"]
            f["fatigue_diff"]           = p1_feat["fatigue_factor"]  - p2_feat["fatigue_factor"]
            f["match_volume_14d_diff"]  = p1_feat["matches_14d"]     - p2_feat["matches_14d"]

            # surface-aware diff (only if surface is present)
            surface = (getattr(match, "surface", "") or "").strip().title()
            key = surface.lower() if surface else None
            if key in ("hard", "clay", "grass"):
                f[f"win_rate_{key}_diff"] = (
                    p1_feat.get(f"win_rate_{key}", 0.5) - p2_feat.get(f"win_rate_{key}", 0.5)
                )
            # clamp & fill
            for k, v in list(f.items()):
                if v is None:
                    f[k] = 0.0
                elif isinstance(v, (int, float)):
                    # keep rates in [0,1], diffs in [-1,1] if applicable
                    if "win_rate" in k or "pctg" in k or "form" in k or "serve_rating" in k:
                        # do not clamp diffs aggressively; just keep sane bounds
                        f[k] = float(max(min(v, 1.0), -1.0))
                    else:
                        f[k] = float(v)

            return f
        except Exception as e:
            print(f"\033[31mFeature build error for match {getattr(match,'id',None)}: {e}\033[0m")
            return {}

    # ---------- Per-player core ----------

    def _player_feats(self, player, as_of, exclude_match_id: Optional[int]) -> Dict:
        ids = self._recent_match_ids(player, as_of, exclude_match_id)
        feat: Dict = {}

        # Recent form (last 10 days)
        recent_10 = PlayerMatch.objects.filter(
            player=player, completed=True,
            date__lt=as_of, date__gte=as_of - timedelta(days=20)
        ).exclude(id=exclude_match_id)
        n_recent = recent_10.count()
        if n_recent:
            wins = recent_10.filter(won=True).count()
            feat["recent_form"] = wins / n_recent
        else:
            feat["recent_form"] = 0.5

        # Fatigue & volume
        feat["matches_14d"] = PlayerMatch.objects.filter(
            player=player, completed=True,
            date__lt=as_of, date__gte=as_of - timedelta(days=14)
        ).exclude(id=exclude_match_id).count()
        feat["fatigue_factor"] = feat["matches_14d"] / 10.0

        # Overall win rate (window)
        total = len(ids)
        if total:
            wins = PlayerMatch.objects.filter(id__in=ids, player=player, won=True).count()
            feat["win_rate"] = wins / total
        else:
            feat["win_rate"] = 0.5

        # Surface win rates (window)
        for s in ("Hard", "Clay", "Grass"):
            sc = PlayerMatch.objects.filter(id__in=ids, surface=s, player=player).count()
            if sc:
                sw = PlayerMatch.objects.filter(
                    id__in=ids, surface=s, player=player, won=True
                ).count()
                feat[f"win_rate_{s.lower()}"] = sw / sc
            else:
                feat[f"win_rate_{s.lower()}"] = 0.5

        # Serve aggregates
        fs_w, fs_p, df_p, ss_w, ace_p, bp_saved, bp_faced = self._serve_aggs(ids, exclude_match_id)
        feat.update({
            "fs_w": fs_w, "fs_p": fs_p, "df_p": df_p, "ss_w": ss_w, "ace_p": ace_p,
            "bp_saved_p": (bp_saved / bp_faced) if bp_faced else 0.5,
        })

        # Return aggregates
        v_fs, v_ace, v_ss, bp_conv, bp_ch = self._return_aggs(ids, exclude_match_id)
        feat.update({
            "v_fs": v_fs, "v_ace": v_ace, "v_ss": v_ss,
            "bp_conv_p": (bp_conv / bp_ch) if bp_ch else 0.5,
        })

        # Serve rating (simple composite)
        feat["serve_rating"] = feat["fs_w"] * 0.7 + feat["ss_w"] * 0.3

        # Dominance ratio average
        dom = PlayerMatchServeStats.objects.filter(match_id__in=ids)
        dominance_ratio = dom.aggregate(Avg("dominance_ratio"))["dominance_ratio__avg"]
        feat["dominance_ratio"] = float(dominance_ratio) if dominance_ratio is not None else 0.5

        # Clean NaNs
        for k, v in list(feat.items()):
            feat[k] = 0.0 if v is None else float(v)

        return feat

    # ---------- Aggregations ----------

    def _recent_match_ids(self, player, as_of, exclude_match_id):
        key = (player.id, as_of)
        if key in self._recent_ids_cache:
            ids = self._recent_ids_cache[key]
        else:
            qs = (PlayerMatch.objects
                  .filter(player=player, completed=True,
                          date__lt=as_of,
                          date__gte=as_of - timedelta(days=self.window_days))
                  .order_by("-date")
                  .values_list("id", flat=True))
            ids = list(qs)
            self._recent_ids_cache[key] = ids
        if exclude_match_id:
            ids = [i for i in ids if i != exclude_match_id]
        return ids

    @staticmethod
    def _serve_aggs(match_ids, exclude_match_id):
        if not match_ids:
            return (0.0,)*7
        qs = PlayerMatchServeStats.objects.filter(match_id__in=match_ids)
        if exclude_match_id:
            qs = qs.exclude(match_id=exclude_match_id)
        a = qs.aggregate(
            fs_w_avg=Avg("fs_w_pctg"), fs_avg=Avg("fs_pctg"), df_avg=Avg("df_pctg"),
            ss_w_avg=Avg("ss_w_pctg"), ace_avg=Avg("ace_pctg"),
            bp_saved_avg=Avg("bp_saved"), bp_faced_avg=Avg("bp_faced"),
        )
        z = lambda v: float(v) if v is not None else 0.0
        return (z(a["fs_w_avg"]), z(a["fs_avg"]), z(a["df_avg"]),
                z(a["ss_w_avg"]), z(a["ace_avg"]), z(a["bp_saved_avg"]), z(a["bp_faced_avg"]))

    @staticmethod
    def _return_aggs(match_ids, exclude_match_id):
        if not match_ids:
            return (0.0, 0.0, 0.0, 0.0, 0.0)
        qs = PlayerMatchReturnStats.objects.filter(match_id__in=match_ids)
        if exclude_match_id:
            qs = qs.exclude(match_id=exclude_match_id)
        a = qs.aggregate(
            v_fs_avg=Avg("v_fs_pctg"), v_ace_avg=Avg("v_ace_pctg"), v_ss_avg=Avg("v_ss_pctg"),
            bp_conv_avg=Avg("bp_conv"), bp_chances_avg=Avg("bp_chances"),
        )
        z = lambda v: float(v) if v is not None else 0.0
        return (z(a["v_fs_avg"]), z(a["v_ace_avg"]), z(a["v_ss_avg"]),
                z(a["bp_conv_avg"]), z(a["bp_chances_avg"]))

    # ---------- H2H ----------

    def _h2h_win_ratio(self, p1, p2, as_of):
        qs = PlayerMatch.objects.filter(
            (Q(player=p1, opponent=p2) | Q(player=p2, opponent=p1)),
            date__lt=as_of, completed=True
        ).order_by("-date")
        n = qs.count()
        if n == 0:
            return 0.0  # center the diff later via subtraction
        p1_wins = 0
        for m in qs:
            p1_wins += 1 if ((m.player == p1 and m.won) or (m.player == p2 and not m.won)) else 0
        wr = p1_wins / n
        if n < 5:  # shrink low-sample toward neutral 0.5
            wr = 0.5 + (wr - 0.5) * (n / 5.0)
        return round(wr - 0.5, 4)  # center at 0 (diff-like)

    def _h2h_recent_momentum(self, p1, p2, as_of):
        qs = PlayerMatch.objects.filter(
            (Q(player=p1, opponent=p2) | Q(player=p2, opponent=p1)),
            date__lt=as_of, completed=True
        ).order_by("-date")
        n = qs.count()
        if n == 0:
            return 0.0
        take = min(5, n)
        num, den = 0.0, 0.0
        for i, m in enumerate(qs[:take]):
            w = 0.8 ** i
            p1_w = ((m.player == p1 and m.won) or (m.player == p2 and not m.won))
            num += (w if p1_w else -w)
            den += w
        return round(num / den if den else 0.0, 4)

    # ---------- Optional as-of helpers ----------

    @staticmethod
    def _elo_as_of(player, as_of):
        if not PlayerEloHistory:
            return 0.0
        row = (PlayerEloHistory.objects
               .filter(player=player, effective_date__lte=as_of)
               .order_by("-effective_date")
               .values_list("elo", flat=True)
               .first())
        return float(row) if row is not None else 0.0

    @staticmethod
    def _rank_as_of(player, as_of):
        if not PlayerRankHistory:
            return None
        row = (PlayerRankHistory.objects
               .filter(player=player, as_of_date__lte=as_of)
               .order_by("-as_of_date")
               .values_list("rank", flat=True)
               .first())
        return int(row) if row is not None else None

    @staticmethod
    def _rank_score(rank):
        # higher better score; None ~ average
        if rank is None:
            return 0.0
        return 1.0 / (rank + 5.0)
