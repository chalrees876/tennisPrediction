from pprint import pprint
from pyexpat import features

from django.db.models import Sum, Avg

from tennis.models import Player, PlayerElo, PlayerMatch, PlayerMatchServeStats, PlayerMatchReturnStats


class TennisFeatureEngineer:
    DEFAULT_ADJUSTMENT_FACTOR = 0.0025
    DEFAULT_BIAS_TERM = 0.2
    DEFAULT_RECENT_MATCH = 10
    def __init__(self):
        self.features=[]

    def create_player_features(self, player, date, num_matches=DEFAULT_RECENT_MATCH):
        try:
            player_elo_obj = PlayerElo.objects.get(player=player)
            player_elo = player_elo_obj.elo
        except Exception as e:
            print(e)
            player_elo = 1000
        try:
            recent_matches = PlayerMatch.objects.filter(player=player, date__lte=date, completed=True).order_by('-date')[:num_matches]
            features = {}

            fs_w_pctg, fs_pctg, df_pctg, ss_w_pctg, ace_pctg = self.aggregate_serve_stats(recent_matches)
            v_fs_pctg, v_ace_pctg, v_ss_pctg = self.aggregate_return_stats(recent_matches)
            features["avg_opp_rank"] = recent_matches.aggregate(Avg('opponent_rank'))['opponent_rank__avg']
            features["serve_rating"] = (
                    (fs_w_pctg * 0.4) +
                    (ss_w_pctg * 0.3) +
                    (fs_pctg * 0.2) -
                    (df_pctg * 0.1)
            )
            features["return_rating"] = (
            (v_fs_pctg*0.6) +
            (v_ss_pctg*0.4) -
            (v_ace_pctg*0.1)
            )
            features["dominance_ratio"] = PlayerMatchServeStats.objects.filter(match__in=recent_matches).aggregate(Avg('dominance_ratio'))['dominance_ratio__avg']
            if features["dominance_ratio"]:
                features["dominance_ratio_adjusted"] = features["dominance_ratio"] + 0.2 - (features["avg_opp_rank"]*self.DEFAULT_ADJUSTMENT_FACTOR)
            else:
                features["dominance_ratio_adjusted"] = 0.5
                features["dominance_ratio"] = 0.5
            if recent_matches:
                win_rate = sum(1 for w in recent_matches if w.won) / len(recent_matches)
            else:
                win_rate = 0.5

            features['current_elo'] = player_elo
            features['win_rate'] = win_rate
            for surface in ['Hard', 'Grass', 'Clay']:
                surface_matches = PlayerMatch.objects.filter(player=player, surface=surface, date__lte=date).order_by('-date')[:num_matches]
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
            player1_features = self.create_player_features(player1, match.date)
            player2_features = self.create_player_features(player2, match.date)

            match_features = {}

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
            Avg('ace_pctg')
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