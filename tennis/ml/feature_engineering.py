from collections import OrderedDict
from datetime import timedelta
from django.db.models import Avg, Q, Sum, Case, When
from typing import Dict, Tuple, Optional

# Import your models. Adjust names/paths if needed.
from tennis.models import (
    PlayerMatch,
    PlayerMatchServeStats,
    PlayerMatchReturnStats,
)

# Optional/history models—if you have them. If not, the code falls back safely.
try:
    from tennis.models import PlayerEloHistory  # fields: player, elo, effective_date
except Exception:
    PlayerEloHistory = None

try:
    from tennis.models import PlayerElo  # fields: player, elo (current)
except Exception:
    PlayerElo = None

try:
    from tennis.models import PlayerRankHistory  # fields: player, rank, as_of_date (or week_start)
except Exception:
    PlayerRankHistory = None


class TennisFeatureEngineer:
    """
    Feature engineering that avoids look-ahead leakage:

    - All aggregates are computed from matches STRICTLY BEFORE the current match date.
    - The target match is explicitly excluded from any aggregates.
    - Historical Elo/Rank are fetched as-of the match date (with graceful fallbacks).

    Usage:
        fe = TennisFeatureEngineer(window_days=45)
        match_features = fe.create_match_features(match, include_adjusted=False)
    """

    def __init__(self, window_days: int = 150):
        self.window_days = window_days
        self.features = []  # optional collection of features over calls

        # If you decide to enable adjusted variants, these constants apply.
        self.DEFAULT_ADJUSTMENT_FACTOR = 0.0025
        self.DEFAULT_BIAS_TERM = 0.2

    # ---------- Public API ----------

    def create_match_features(self, match, include_adjusted: bool = False) -> Dict:
        """
        Build pre-match features for player1 (match.player) vs player2 (match.opponent).
        Ensures no leakage by:
          - using ONLY data with date < match.date
          - excluding the match itself from any aggregates
        """
        try:
            p1 = match.player
            p2 = match.opponent
            match_date = match.date
            exclude_id = match.id

            p1_feat = self.create_player_features(p1, match_date, exclude_match_id=exclude_id)
            p2_feat = self.create_player_features(p2, match_date, exclude_match_id=exclude_id)

            # Surface key (ensure it's a string like "Hard"/"Clay"/"Grass")
            surface = (getattr(match, 'surface', '') or '').strip().title()
            surface_key = surface.lower() if surface else None

            mf: Dict = {}
            h2h_data = self.head_to_head_features(p1, p2, match_date=match_date)
            mf['h2h_win_ratio'] = h2h_data['h2h_win_ratio']
            mf['h2h_recent_momentum'] = h2h_data['h2h_recent_momentum']
            mf['fatigue_diff'] = (p1_feat['fatigue_factor'] - p2_feat['fatigue_factor'])
            mf['serve_rating'] = (p1_feat['serve_rating'] - p2_feat['serve_rating'])
            mf['recent_form'] = p1_feat['recent_form'] - p2_feat['recent_form']
            mf['win_rate'] = p1_feat['win_rate'] - p2_feat['win_rate']
            mf['bp_conv_pctg'] = p1_feat['bp_conv_p'] - p2_feat['bp_conv_p']

            keep = ['h2h_win_ratio', 'h2h_recent_momentum', 'fatigue_diff', 'serve_rating', 'recent_form', 'win_rate', 'bp_conv_pctg']

            # Optional per-surface win rate (unadjusted) — only if surface exists
            if surface_key:
                p1_ws = p1_feat.get(f'win_rate_{surface_key}', 0.5)
                p2_ws = p2_feat.get(f'win_rate_{surface_key}', 0.5)
                mf[f'win_rate_{surface_key}'] = p1_ws - p2_ws

            result = OrderedDict((k, float(mf.get(k, 0))) for k in keep)

            self.features.append(result)
            print(f"created {match}")
            return result

        except Exception as e:
            print(f'\033[31mError creating match features: {e}\033[0m')
            return {}

    def create_player_features(
        self,
        player,
        date,
        exclude_match_id: Optional[int] = None,
        include_adjusted: bool = False
    ) -> Dict:
        """
        Build features for a single player using only matches BEFORE `date` and
        excluding `exclude_match_id` if provided.
        """
        try:

            results_qs = PlayerMatch.objects.filter(
                player=player,
                completed=True,
                date__lt=date,  # strictly before the match
                date__gte=(date - timedelta(days=self.window_days)),
            )
            if exclude_match_id:
                results_qs = results_qs.exclude(id=exclude_match_id)
            results_qs = results_qs.order_by('-date')

            match_results = list(results_qs)
            n_matches = len(match_results)

            feat: Dict = {}

            recent_results_qs = results_qs.filter(date__gte=date - timedelta(days=10))

            recent_results = list(recent_results_qs)
            n_recent_results = len(recent_results)
            if n_recent_results != 0:
                recent_wins = sum(1 for m in recent_results if getattr(m, 'won', False))
                feat['recent_form'] = recent_wins / n_recent_results
            else:
                feat['recent_form'] = 0.5

            # get number of matches player has played over the last two weeks.

            feat['fatigue_factor'] = self.fatigue_factor(player, date)

            # Win-rate (overall)
            if n_matches > 0:
                wins = sum(1 for m in match_results if getattr(m, 'won', False))
                feat['win_rate'] = wins / n_matches
            else:
                feat['win_rate'] = 0.5

            # Per-surface win rate (unadjusted)
            for surface in ['Hard', 'Grass', 'Clay']:
                surface_qs = results_qs.filter(surface=surface)
                s_count = surface_qs.count()
                if s_count > 0:
                    s_wins = surface_qs.filter(won=True).count()
                    feat[f'win_rate_{surface.lower()}'] = s_wins / s_count
                else:
                    feat[f'win_rate_{surface.lower()}'] = 0.5

            # Serve/Return aggregates (pre-match only; target excluded)
            fs_w, fs_p, df_p, ss_w, ace_p, bp_saved, bp_faced = self.aggregate_serve_stats(results_qs, exclude_match_id=exclude_match_id)
            v_fs, v_ace, v_ss, bp_conv, bp_chance = self.aggregate_return_stats(results_qs, exclude_match_id=exclude_match_id)

            feat['fs_w'] = fs_w
            feat['fs_p'] = fs_p
            feat['df_p'] = df_p
            feat['ss_w'] = ss_w
            feat['ace_p'] = ace_p
            if bp_faced == 0:
                feat['bp_saved_p'] = 0.5
            else:
                feat['bp_saved_p'] = bp_saved / bp_faced
            feat['v_fs'] = v_fs
            feat['v_ace'] = v_ace
            feat['v_ss'] = v_ss
            if bp_chance == 0:
                feat['bp_conv_p'] = 0.5
            else:
                feat['bp_conv_p'] = bp_conv / bp_chance

            feat['serve_rating'] = feat['fs_w'] * 0.7 + feat['ss_w'] * 0.3

            # Dominance ratio from serve stats table (pre-match only)
            dom = PlayerMatchServeStats.objects.filter(
                match__in=results_qs.values('id')
            )
            if exclude_match_id:
                dom = dom.exclude(match_id=exclude_match_id)

            dominance_ratio = dom.aggregate(Avg('dominance_ratio')).get('dominance_ratio__avg')
            feat['dominance_ratio'] = dominance_ratio if dominance_ratio is not None else 0.5

            return feat

        except Exception as e:
            print(f'\033[31mError creating player features: {e}\033[0m')
            return {}

    # ---------- Aggregations (pre-match only) ----------

    @staticmethod
    def aggregate_serve_stats(recent_matches_qs, exclude_match_id: Optional[int] = None) -> Tuple[float, float, float, float, float, float, float]:
        qs = PlayerMatchServeStats.objects.filter(match__in=recent_matches_qs.values('id'))
        if exclude_match_id:
            qs = qs.exclude(match_id=exclude_match_id)

        stats = qs.aggregate(
            fs_w_avg=Avg('fs_w_pctg'),
            fs_avg=Avg('fs_pctg'),
            df_avg=Avg('df_pctg'),
            ss_w_avg=Avg('ss_w_pctg'),
            ace_avg=Avg('ace_pctg'),
            bp_saved_avg=Avg('bp_saved'),
            bp_faced_avg=Avg('bp_faced'),
        )
        def _z(v): return float(v) if v is not None else 0.0
        return (
            _z(stats['fs_w_avg']),
            _z(stats['fs_avg']),
            _z(stats['df_avg']),
            _z(stats['ss_w_avg']),
            _z(stats['ace_avg']),
            _z(stats['bp_saved_avg']),
            _z(stats['bp_faced_avg']),

        )

    @staticmethod
    def aggregate_return_stats(recent_matches_qs, exclude_match_id: Optional[int] = None) -> Tuple[
        float, float, float, float, float]:
        qs = PlayerMatchReturnStats.objects.filter(match__in=recent_matches_qs.values('id'))
        if exclude_match_id:
            qs = qs.exclude(match_id=exclude_match_id)

        stats = qs.aggregate(
            v_fs_avg=Avg('v_fs_pctg'),
            v_ace_avg=Avg('v_ace_pctg'),
            v_ss_avg=Avg('v_ss_pctg'),
            bp_conv_avg=Avg('bp_conv'),
            bp_chances_avg=Avg('bp_chances'),
        )
        def _z(v): return float(v) if v is not None else 0.0
        return (
            _z(stats['v_fs_avg']),
            _z(stats['v_ace_avg']),
            _z(stats['v_ss_avg']),
            _z(stats['bp_conv_avg']),
            _z(stats['bp_chances_avg']),
        )

    # ---------- Utilities ----------

    @staticmethod
    def fatigue_factor(player, match_date, days_window=30) -> float:
        """Consider match density in recent period"""
        recent_matches = PlayerMatch.objects.filter(
            player=player,
            date__lt=match_date,
            date__gte=match_date - timedelta(days=days_window),
            completed=True
        ).count()

        return recent_matches / 10.0

    def head_to_head_features(self, p1, p2, match_date):
        """
        Returns two focused H2H features:
        1. Dominance-weighted win ratio (emphasizes differential like 9-1 vs 100-92)
        2. Recency-weighted performance
        """
        try:
            # Get all previous matches between these players
            h2h_matches = PlayerMatch.objects.filter(
                (Q(player=p1, opponent=p2) | Q(player=p2, opponent=p1)),
                date__lt=match_date,
                completed=True
            ).order_by('-date')

            total_matches = h2h_matches.count()

            if total_matches == 0:
                return {
                    'h2h_win_ratio': 0.5,  # Neutral
                    'h2h_recent_momentum': 0.0,  # No momentum
                }

            # Calculate win counts
            p1_wins = 0
            for match in h2h_matches:
                p1_won_match = (match.player == p1 and match.won) or (match.player == p2 and not match.won)
                if p1_won_match:
                    p1_wins += 1

            # Feature 1: Simple win ratio with confidence weighting
            win_ratio = p1_wins / total_matches

            # Apply confidence-based smoothing - more matches = more confidence
            # This naturally handles the 9-1 vs 100-92 case
            if total_matches < 5:
                # Low confidence: shrink toward neutral
                h2h_win_ratio = 0.5 + (win_ratio - 0.5) * (total_matches / 5)
            else:
                # High confidence: use actual ratio
                h2h_win_ratio = win_ratio

            # Feature 2: Recency-weighted momentum (same as before)
            recent_weighted_sum = 0
            total_recent_weight = 0

            recent_matches_to_consider = min(5, total_matches)

            for i in range(recent_matches_to_consider):
                match = h2h_matches[i]
                p1_won_match = (match.player == p1 and match.won) or (match.player == p2 and not match.won)

                weight = 0.8 ** i  # Exponential decay
                recent_weighted_sum += weight if p1_won_match else -weight
                total_recent_weight += weight

            if total_recent_weight > 0:
                h2h_recent_momentum = recent_weighted_sum / total_recent_weight
            else:
                h2h_recent_momentum = 0.0

            return {
                'h2h_win_ratio': round(h2h_win_ratio, 4),
                'h2h_recent_momentum': round(h2h_recent_momentum, 4),
            }

        except Exception as e:
            print(f'\033[31mError creating improved H2H features: {e}\033[0m')
            return {
                'h2h_win_ratio': 0.5,
                'h2h_recent_momentum': 0.0,
            }