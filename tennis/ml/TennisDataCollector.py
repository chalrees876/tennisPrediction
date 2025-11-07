import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, roc_auc_score
import joblib
import math
from tennis.ml.feature_engineering import TennisFeatureEngineer
from tennis.models import PlayerMatch


class TennisDataCollector:
    def __init__(self, start_date, end_date):
        self.start_date = start_date
        self.end_date = end_date
        self.feature_engineer = TennisFeatureEngineer()

    def collect_training_data(self):
        training_data = []
        qs = (PlayerMatch.objects
              .filter(date__range=[self.start_date, self.end_date], completed=True)
              .select_related('player','opponent')
              .order_by('date'))

        # keep one perspective per real match if your table is per-player
        matches = [m for m in qs if m.player.id < m.opponent.id]

        for match in matches:
            try:
                feats = self.feature_engineer.create_match_features(match, include_adjusted=False)
                if not feats:  # skipped due to sparse history, errors, etc.
                    continue
                if match.won is None:
                    continue

                feats['target'] = 1 if match.won else 0
                feats['match_id'] = match.id
                feats['date'] = match.date
                feats['player_id'] = match.player.id  # stable id
                feats['opponent_id'] = match.opponent.id

                if self._all_zero_features(feats):
                    continue

                training_data.append(feats)

            except Exception as e:
                print(f"Error processing match {getattr(match,'id',None)}: {e}")
                continue

        df = pd.DataFrame(training_data)
        df.to_csv("tennis/data/training_data.csv", index=False)
        return df

    @staticmethod
    def _all_zero_features(d: dict, non_feature_keys=None) -> bool:
        non_feature_keys = non_feature_keys or {"target", "match_id", "date", "player_id", "opponent_id"}
        vals = []
        for k, v in d.items():
            if k in non_feature_keys:
                continue
            if v is None or (isinstance(v, float) and math.isnan(v)):
                v = 0.0
            vals.append(abs(float(v)) <= 1e-12)
        return all(vals)