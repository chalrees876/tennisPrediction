from pyexpat import features

from tennis.models import Player, PlayerElo, PlayerMatch


class TennisFeatureEngineer:
    def __init__(self):
        self.features=[]

    def create_player_features(self, player, num_matches):
        try:
            player_ranking = player.ranking
            player_elo_obj = PlayerElo.objects.get(player=player)

            recent_matches = PlayerMatch.objects.filter(player=player).order_by('-date')[:10]
            for match in recent_matches:
                print(match.player.name, match.opponent.name, match.date, match.won)
            win_rate = sum(1 for w in recent_matches if w.won) / len(recent_matches)
            print(win_rate)

            features = {}

            features['current_elo'] = player_elo_obj.elo
            features['win_rate'] = win_rate

            print(features)

            for surface in ['Hard', 'Grass', 'Clay']:
                surface_matches = PlayerMatch.objects.filter(player=player, surface=surface).order_by('-date')[:10]
                if surface_matches:
                    features[f'win_rate_{surface.lower()}'] = sum(1 for w in surface_matches if w.won) / len(
                        surface_matches)
                else:
                    features[f'win_rate_{surface.lower()}'] = 0.5
            print(features)
            return features
        except Exception as e:
            print(f'Error creating player features: {e}')
            return {}

    def create_match_features(self, player1, player2, surface):
        try:
            player1_features = self.create_player_features(player1, 10)
            player2_features = self.create_player_features(player2, 10)

            match_features = {}

            match_features['elo_difference'] = player1_features['current_elo'] - player2_features['current_elo']
            match_features['win_rate'] = player1_features['win_rate'] - player2_features['win_rate']

            match_features[f'win_rate_{surface.lower()}'] = player1_features[f'win_rate_{surface.lower()}'] - player2_features[f'win_rate_{surface.lower()}']
            self.features.append(match_features)
            return match_features
        except Exception as e:
            print(f'Error creating match features: {e}')