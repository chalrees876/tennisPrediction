"""from datetime import timedelta
from pprint import pprint
from pyexpat import features

from django.db.models import Sum, Avg

from tennis.models import Player, PlayerElo, PlayerMatch, PlayerMatchServeStats, PlayerMatchReturnStats, \
    PlayerPointByPointStats


class TennisFeatureEngineer:
    DEFAULT_ADJUSTMENT_FACTOR = 0.0025
    DEFAULT_BIAS_TERM = 0.2
    def __init__(self):
        self.features=[]

    def create_player_features(self, player, date, exclude_match=None):
        try:
            player_elo_obj = PlayerElo.objects.get(player=player)
            player_elo = player_elo_obj.elo
        except Exception as e:
            print(e)
            player_elo = 1000
        try:
            features = {}
            recent_matches = PlayerMatch.objects.filter(player=player, date__lt=date, date__gte=(date-timedelta(days=45)), completed=True)
            if exclude_match:
                recent_matches = recent_matches.exclude(id=exclude_match.id)
            recent_matches = recent_matches.order_by('date')

            print(f"length of recent matches{len(recent_matches)} for {player}")
            if not recent_matches:
                features['avg_opp_rank'] = 100
                features['serve_rating'] = 0.5
                features['serve_rating_adjusted'] = 0.5
                features['return_rating'] = 0.5
                features['return_rating_adjusted'] = 0.5
                features['dominance_ratio'] = 0.5
                features['dominance_ratio_adjusted'] = 0.5
                features['fatigue_factor'] = 0.5


            elif len(recent_matches) <= 5:
                features['fatigue_factor'] = 0.1
            elif 5 < len(recent_matches) < 8:
                features['fatigue_factor'] = 0.3
            elif 8 < len(recent_matches) < 12:
                features['fatigue_factor'] = 0.6
            elif 12 < len(recent_matches) < 16:
                features['fatigue_factor'] = 0.8
            else:
                features['fatigue_factor'] = 1.0

            features["avg_opp_rank"] = recent_matches.aggregate(Avg('opponent_rank'))['opponent_rank__avg']

            fs_w_pctg, fs_pctg, df_pctg, ss_w_pctg, ace_pctg = self.aggregate_serve_stats(recent_matches)
            v_fs_pctg, v_ace_pctg, v_ss_pctg = self.aggregate_return_stats(recent_matches)

            features["serve_rating"] = (
                    (fs_w_pctg * 0.5) +
                    (ss_w_pctg * 0.5) +
                    (fs_pctg * 0.5) -
                    (df_pctg * 0.1)
            )
            features["return_rating"] = (
            (v_fs_pctg*0.5) +
            (v_ss_pctg*0.7) -
            (v_ace_pctg*0.1)
            )

            features["dominance_ratio"] = PlayerMatchServeStats.objects.filter(match__in=recent_matches).aggregate(Avg('dominance_ratio'))['dominance_ratio__avg']
            if recent_matches:
                win_rate = sum(1 for w in recent_matches if w.won) / len(recent_matches)
            else:
                win_rate = 0.5

            features['current_elo'] = player_elo
            features['win_rate'] = win_rate
            for surface in ['Hard', 'Grass', 'Clay']:
                surface_matches = PlayerMatch.objects.filter(player=player, surface=surface, date__lt=date, date__gte=(date-timedelta(days=45))).order_by('-date')
                if surface_matches:
                    features[f'win_rate_{surface.lower()}'] = (sum(1 for w in surface_matches if w.won) / len(
                        surface_matches))
                else:
                    features[f'win_rate_{surface.lower()}'] = 0.5
                if features["avg_opp_rank"]:
                    features[f'win_rate_{surface.lower()}_adjusted'] = features[f"win_rate_{surface.lower()}"] + self.DEFAULT_BIAS_TERM - (
                        features["avg_opp_rank"]*self.DEFAULT_ADJUSTMENT_FACTOR
                    )
                else:
                    features[f'win_rate_{surface.lower()}_adjusted'] = 0.5
            if features["avg_opp_rank"]:
                opp_strength = 1/features["avg_opp_rank"]
                features["dominance_ratio_adjusted"] = features["dominance_ratio"] + self.DEFAULT_BIAS_TERM + (
                            opp_strength * self.DEFAULT_ADJUSTMENT_FACTOR)
                features["return_rating_adjusted"] = features["return_rating"] + self.DEFAULT_BIAS_TERM + (
                            opp_strength * self.DEFAULT_ADJUSTMENT_FACTOR)
                features["serve_rating_adjusted"] = features["serve_rating"] + self.DEFAULT_BIAS_TERM + (
                            opp_strength * self.DEFAULT_ADJUSTMENT_FACTOR)
                features['win_rate_adjusted'] = win_rate + self.DEFAULT_BIAS_TERM + opp_strength * self.DEFAULT_ADJUSTMENT_FACTOR
            else:
                features["dominance_ratio_adjusted"] = features["dominance_ratio"]
                features["return_rating_adjusted"] = features["return_rating"]
                features["serve_rating_adjusted"] = features["serve_rating"]
                features["win_rate_adjusted"] = win_rate

            return features
        except Exception as e:
            print(f'\033[31mError creating player features: {e}\033[0m')
            return {}

    def create_match_features(self, match):
        try:
            player1 = match.player
            player2 = match.opponent
            player1_features = self.create_player_features(player1, match.date, exclude_match=match)
            player2_features = self.create_player_features(player2, match.date, exclude_match=match)

            match_features = {}

            match_features['fatigue_diff'] = player1_features['fatigue_factor'] - player2_features['fatigue_factor']
            match_features['rank_diff'] = match.opponent_rank - match.rank
            match_features['elo_difference'] = player1_features['current_elo'] - player2_features['current_elo']
            match_features['win_rate'] = player1_features['win_rate'] - player2_features['win_rate']
            match_features['win_rate_adjusted'] = player1_features['win_rate_adjusted'] - player2_features['win_rate_adjusted']
            match_features['dominance_ratio'] = player1_features['dominance_ratio'] - player2_features['dominance_ratio']
            match_features['dominance_ratio_adjusted'] = player1_features['dominance_ratio_adjusted'] - player2_features['dominance_ratio_adjusted']
            match_features['serve_rating'] = player1_features['serve_rating'] - player2_features['serve_rating']
            match_features['return_rating'] = player1_features['return_rating'] - player2_features['return_rating']
            match_features['return_rating_adjusted'] = player1_features['return_rating_adjusted'] - player2_features['return_rating_adjusted']
            match_features['serve_rating_adjusted'] = player1_features['serve_rating_adjusted'] - player2_features['serve_rating_adjusted']
            match_features[f'win_rate_{match.surface.lower()}'] = player1_features[f'win_rate_{match.surface.lower()}'] - player2_features[f'win_rate_{match.surface.lower()}']
            match_features[f'win_rate_{match.surface.lower()}_adjusted'] = player1_features[f'win_rate_{match.surface.lower()}_adjusted'] - player2_features[f'win_rate_{match.surface.lower()}_adjusted']


            add in these once they are added to the player match data

            match_features["avg_balanced_leverage_ratio"] = player1_features["avg_balanced_leverage_ratio"] - player2_features["avg_balanced_leverage_ratio"]
            match_features["avg_dominance_ratio_plus"] = player1_features["avg_dominance_ratio_plus"] - player2_features["avg_dominance_ratio_plus"]
            match_features["avg_excitement_index"] = player1_features["avg_excitement_index"] - player2_features["avg_excitement_index"]
            match_features["avg_comeback_factor"] = player1_features["avg_comeback_factor"] - player2_features["avg_comeback_factor"]
            match_features["avg_deuce_ace_pctg"] = player1_features["avg_deuce_ace_pctg"] - player2_features["avg_deuce_ace_pctg"]
            match_features["avg_deuce_s_w_pctg"] = player1_features["avg_deuce_ace_pctg"] - player2_features["avg_deuce_s_w_pctg"]
            match_features["avg_ad_ace_pctg"] = player1_features["avg_ad_ace_pctg"] - player2_features["avg_ad_ace_pctg"]
            match_features["avg_ad_s_w_pctg"] = player1_features["avg_ad_s_w_pctg"] - player2_features["avg_ad_s_w_pctg"]
            match_features["avg_deuce_r_w_pctg"] = player1_features["avg_deuce_r_w_pctg"] - player2_features["avg_deuce_r_w_pctg"]
            match_features["avg_ad_r_w_pctg"] = player1_features["avg_ad_r_w_pctg"] - player2_features["avg_ad_r_w_pctg"]

            self.features.append(match_features)
            return match_features
        except Exception as e:
            print(f'Error creating match features: {e}')

    @staticmethod
    def aggregate_serve_stats(recent_matches):

        stats = PlayerMatchServeStats.objects.filter(
            match__in=recent_matches
        ).aggregate(
            Avg('fs_w_pctg'),
            Avg('fs_pctg'),
            Avg('df_pctg'),
            Avg('ss_w_pctg'),
            Avg('ace_pctg'),
        )
        return (
            stats['fs_w_pctg__avg'] or 0,
            stats['fs_pctg__avg'] or 0,
            stats['df_pctg__avg'] or 0,
            stats['ss_w_pctg__avg'] or 0,
            stats['ace_pctg__avg'] or 0
        )
    @staticmethod
    def aggregate_return_stats(recent_matches):

        stats = PlayerMatchReturnStats.objects.filter(
            match__in=recent_matches
        ).aggregate(
            avg_v_fs_pctg=Avg('v_fs_pctg'),
            avg_v_ace_pctg=Avg('v_ace_pctg'),
            avg_v_ss_pctg=Avg('v_ss_pctg'),
        )
        return (
            stats['avg_v_fs_pctg'] or 0,
            stats['avg_v_ace_pctg'] or 0,
            stats['avg_v_ss_pctg'] or 0
        )

    @staticmethod
    def aggregate_point_by_point_stats(recent_matches):
        stats = PlayerPointByPointStats.objects.filter(
            match__in=recent_matches
        ).aggregate(
            avg_balanced_leverage_ration=Avg('balanced_leverage_ration'),
            avg_dominance_ratio_plus=Avg('dominance_ratio_plus'),
            avg_excitement_index=Avg('excitement_index'),
            avg_comeback_factor=Avg('comeback_factor'),
            avg_deuce_ace_pctg=Avg('deuce_ace_pctg'),
            avg_deuce_s_w_pctg=Avg('deuce_s_w_pctg'),
            avg_ad_ace_pctg=Avg('ad_ace_pctg'),
            avg_ad_s_w_pctg=Avg('ad_s_w_pctg'),
            avg_deuce_r_w_pctg=Avg('deuce_r_w_pctg'),
            avg_ad_r_w_pctg=Avg('ad_r_w_pctg'),
        )

        return (
            stats['avg_balanced_leverage_ration'] or 0,
            stats['avg_dominance_ratio_plus'] or 0,
            stats['avg_excitement_index'] or 0,
            stats['avg_comeback_factor'] or 0,
            stats['avg_deuce_ace_pctg'] or 0,
            stats['avg_deuce_s_w_pctg'] or 0,
            stats['avg_ad_ace_pctg'] or 0,
            stats['avg_ad_s_w_pctg'] or 0,
            stats['avg_deuce_r_w_pctg'] or 0,
            stats['avg_ad_r_w_pctg'] or 0,
        )"""
from collections import OrderedDict
from datetime import timedelta
from django.db.models import Avg
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

    def __init__(self, window_days: int = 45):
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

            p1_feat = self.create_player_features(p1, match_date, exclude_match_id=exclude_id,
                                                 include_adjusted=include_adjusted)
            p2_feat = self.create_player_features(p2, match_date, exclude_match_id=exclude_id,
                                                 include_adjusted=include_adjusted)



            p1_rank = match.rank if match.rank > 0 and match.rank is not None else 200
            p2_rank = match.opponent_rank if match.opponent_rank > 0 and match.opponent_rank is not None else 200

            p1_strength = self._rank_strength(p1_rank, r0=20.0, gamma=2.0)
            p2_strength = self._rank_strength(p2_rank, r0=20.0, gamma=2.0)



            # Surface key (ensure it's a string like "Hard"/"Clay"/"Grass")
            surface = (getattr(match, 'surface', '') or '').strip().title()
            surface_key = surface.lower() if surface else None

            mf: Dict = {}
            mf['fatigue_diff'] = (p1_feat['fatigue_factor'] - p2_feat['fatigue_factor'])
            mf['rank_diff'] = p1_rank - p2_rank
            mf['rank_strength_diff'] = p1_strength - p2_strength
            mf['recent_form'] = p1_feat['recent_form'] - p2_feat['recent_form']
            mf['win_rate'] = p1_feat['win_rate'] - p2_feat['win_rate']
            mf['dominance_ratio'] = p1_feat['dominance_ratio'] - p2_feat['dominance_ratio']
            mf['fs_w'] = p1_feat['fs_w'] - p2_feat['fs_w']
            mf['fs_p'] = p1_feat['fs_p'] - p2_feat['fs_p']
            mf['df_p'] = p1_feat['df_p'] - p2_feat['df_p']
            mf['ss_w'] = p1_feat['ss_w'] - p2_feat['ss_w']
            mf['ace_p'] = p1_feat['ace_p'] - p2_feat['ace_p']
            mf['bp_saved'] = p1_feat['bp_saved'] - p2_feat['bp_saved']
            mf['bp_faced'] = p1_feat['bp_faced'] - p2_feat['bp_faced']
            mf['v_fs'] = p1_feat['v_fs'] - p2_feat['v_fs']
            mf['v_ace'] =p1_feat['v_ace'] - p2_feat['v_ace']
            mf['v_ss'] = p1_feat['v_ss'] - p2_feat['v_ss']
            mf['bp_conv'] = p1_feat['bp_conv'] - p2_feat['bp_conv']
            mf['bp_chance'] = p1_feat['bp_chance'] - p2_feat['bp_chance']

            keep = ['bp_chance', 'bp_conv', 'rank_diff', 'rank_strength_diff', 'win_rate', 'dominance_ratio', 'df_p', 'fatigue_diff', 'recent_form']

            # Optional per-surface win rate (unadjusted) — only if surface exists
            if surface_key:
                p1_ws = p1_feat.get(f'win_rate_{surface_key}', 0.5)
                p2_ws = p2_feat.get(f'win_rate_{surface_key}', 0.5)
                mf[f'win_rate_{surface_key}'] = p1_ws - p2_ws

            # Optional adjusted variants (off by default to reduce redundancy/collinearity)
            if include_adjusted:
                mf['win_rate_adjusted'] = p1_feat['win_rate_adjusted'] - p2_feat['win_rate_adjusted']
                mf['dominance_ratio_adjusted'] = p1_feat['dominance_ratio_adjusted'] - p2_feat['dominance_ratio_adjusted']
                mf['serve_rating_adjusted'] = p1_feat['serve_rating_adjusted'] - p2_feat['serve_rating_adjusted']
                mf['return_rating_adjusted'] = p1_feat['return_rating_adjusted'] - p2_feat['return_rating_adjusted']
                if surface_key:
                    p1_wsa = p1_feat.get(f'win_rate_{surface_key}_adjusted', p1_ws if surface_key else 0.5)
                    p2_wsa = p2_feat.get(f'win_rate_{surface_key}_adjusted', p2_ws if surface_key else 0.5)
                    mf[f'win_rate_{surface_key}_adjusted'] = p1_wsa - p2_wsa

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
            recent_qs = PlayerMatch.objects.filter(
                player=player,
                completed=True,
                date__lt=date,  # strictly before the match
                date__gte=(date - timedelta(days=self.window_days)),
            )
            if exclude_match_id:
                recent_qs = recent_qs.exclude(id=exclude_match_id)
            recent_qs = recent_qs.order_by('-date')

            recent_matches = list(recent_qs)
            n_matches = len(recent_matches)
            feat: Dict = {}
            if n_matches >= 7:
                recent_form_matches = recent_matches[:7]
                wins = sum(1 for m in recent_form_matches if getattr(m, 'won', False))
                feat['recent_form'] = wins / len(recent_form_matches)
            elif n_matches >= 1:
                recent_form_matches = recent_matches[:1]
                wins = sum(1 for m in recent_form_matches if getattr(m, 'won', False))
                feat['recent_form'] = wins / len(recent_form_matches)
            else:
                feat['recent_form'] = 0.5
            # print(f"Recent matches (pre-match only) for {player}: {n_matches}")

            # Fatigue factor (simple bins; you can tune)
            feat['fatigue_factor'] = self._fatigue_bucket(n_matches)

            # Opponent rank average (as stored on PlayerMatch as-of match time)
            # If your schema uses a different field, adjust below.
            avg_opp_rank = recent_qs.aggregate(Avg('opponent_rank')).get('opponent_rank__avg')
            feat['avg_opp_rank'] = avg_opp_rank if avg_opp_rank is not None else 100.0

            # Win-rate (overall)
            if n_matches > 0:
                wins = sum(1 for m in recent_matches if getattr(m, 'won', False))
                feat['win_rate'] = wins / n_matches
            else:
                feat['win_rate'] = 0.5

            # Per-surface win rate (unadjusted)
            for surface in ['Hard', 'Grass', 'Clay']:
                surface_qs = recent_qs.filter(surface=surface)
                s_count = surface_qs.count()
                if s_count > 0:
                    s_wins = surface_qs.filter(won=True).count()
                    feat[f'win_rate_{surface.lower()}'] = s_wins / s_count
                else:
                    feat[f'win_rate_{surface.lower()}'] = 0.5

            # Serve/Return aggregates (pre-match only; target excluded)
            fs_w, fs_p, df_p, ss_w, ace_p, bp_saved, bp_faced = self.aggregate_serve_stats(recent_qs, exclude_match_id=exclude_match_id)
            v_fs, v_ace, v_ss, bp_conv, bp_chance = self.aggregate_return_stats(recent_qs, exclude_match_id=exclude_match_id)

            feat['fs_w'] = fs_w
            feat['fs_p'] = fs_p
            feat['df_p'] = df_p
            feat['ss_w'] = ss_w
            feat['ace_p'] = ace_p
            feat['bp_saved'] = bp_saved
            feat['bp_faced'] = bp_faced
            feat['v_fs'] = v_fs
            feat['v_ace'] = v_ace
            feat['v_ss'] = v_ss
            feat['bp_conv'] = bp_conv
            feat['bp_chance'] = bp_chance

            # Dominance ratio from serve stats table (pre-match only)
            dom = PlayerMatchServeStats.objects.filter(
                match__in=recent_qs.values('id')
            )
            if exclude_match_id:
                dom = dom.exclude(match_id=exclude_match_id)

            dominance_ratio = dom.aggregate(Avg('dominance_ratio')).get('dominance_ratio__avg')
            feat['dominance_ratio'] = dominance_ratio if dominance_ratio is not None else 0.5

            # Optional adjusted variants (off by default)
            if include_adjusted:
                opp_strength = 1.0 / max(feat['avg_opp_rank'] + 1e-6, 1e-6)  # guard against tiny/zero
                bias = self.DEFAULT_BIAS_TERM
                adj = self.DEFAULT_ADJUSTMENT_FACTOR

                feat['win_rate_adjusted'] = feat['win_rate'] + bias + opp_strength * adj
                feat['serve_rating_adjusted'] = feat['serve_rating'] + bias + opp_strength * adj
                feat['return_rating_adjusted'] = feat['return_rating'] + bias + opp_strength * adj
                feat['dominance_ratio_adjusted'] = feat['dominance_ratio'] + bias + opp_strength * adj

                for surface in ['hard', 'grass', 'clay']:
                    wr = feat.get(f'win_rate_{surface}', 0.5)
                    feat[f'win_rate_{surface}_adjusted'] = wr + bias - (feat['avg_opp_rank'] * adj)

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
    def _fatigue_bucket(n_matches: int) -> float:
        if n_matches == 0:
            return 0.5
        elif n_matches <= 5:
            return 0.1
        elif 5 < n_matches < 8:
            return 0.3
        elif 8 < n_matches < 12:
            return 0.6
        elif 12 < n_matches < 16:
            return 0.8
        else:
            return 1.0

    @staticmethod
    def _rank_strength(rank: Optional[int], r0: float = 20.0, gamma: float = 2.0) -> float:
        if rank is None or rank <= 0:
            return 0.0  # neutral/weak if unknown
        return 1.0 / (1.0 + (rank / r0) ** gamma)
