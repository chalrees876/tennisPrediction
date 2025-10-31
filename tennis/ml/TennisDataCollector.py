import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, roc_auc_score
import joblib

from tennis.ml.feature_engineering import TennisFeatureEngineer
from tennis.models import PlayerMatch


class TennisDataCollector:
    def __init__(self, start_date, end_date):
        self.start_date = start_date
        self.end_date = end_date
        self.feature_engineer = TennisFeatureEngineer(window_days=60)

    def collect_training_data(self):
        """Collect matches with features and outcomes for training"""
        training_data = []

        # Get all matches in the date range
        matches = PlayerMatch.objects.filter(
            date__range=[self.start_date, self.end_date]
        ).select_related('player', 'opponent')

        for match in matches:
            try:
                # Create features for this match
                match_features = self.feature_engineer.create_match_features(match, include_adjusted=False)

                if match_features:
                    # Add target variable (1 if player1 won, 0 if lost)
                    match_features['target'] = 1 if match.won else 0

                    # Add match metadata for tracking
                    match_features['match_id'] = match.id
                    match_features['date'] = match.date
                    match_features['player_id'] = match.player.name
                    match_features['opponent_id'] = match.opponent.name

                    training_data.append(match_features)

            except Exception as e:
                print(f"Error processing match {match.id}: {e}")
                continue
        pd.set_option('display.max_rows', None)
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', 2000)
        pd.set_option('display.float_format', '{:20,.2f}'.format)
        pd.set_option('display.max_colwidth', None)
        pd.reset_option('display.max_rows')
        pd.reset_option('display.max_columns')
        pd.reset_option('display.width')
        pd.reset_option('display.float_format')
        pd.reset_option('display.max_colwidth')
        df = pd.DataFrame(training_data)
        df.to_csv("tennis/data/training_data.csv", index=False)
