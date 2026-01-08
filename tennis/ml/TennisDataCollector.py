
import pandas as pd
import numpy as np
from django.db import transaction
import math
from tennis.ml.feature_engineering import TennisFeatureEngineer
from tennis.models import MatchFeatures, PlayerMatch
from tennis.ml.MachineLearning import feature_fields

class TennisDataCollector:
    
    FEATURE_FIELDS = feature_fields
    
    
    def __init__(self, start_date, end_date, rebuild):
        self.start_date = start_date
        self.end_date = end_date
        self.rebuild = rebuild
        self.feature_engineer = TennisFeatureEngineer()

    def collect_training_data(self):
        training_data = []
        qs = (PlayerMatch.objects
              .select_related('player','opponent')
              .order_by('date'))

        # keep one perspective per real match if your table is per-player
        matches = [m for m in qs if m.player.id < m.opponent.id]
        total = len(matches)
        to_create = []
        to_update = []
        existing_ids = set(MatchFeatures.objects.filter(match_id__in=[m.id for m in matches]).values_list('match_id', flat=True))

        for i, match in enumerate(matches):
            if (i + 1) % 500 == 0:
                    print(f"Processed {i + 1}/{total} matches...")
            if match.id in existing_ids and not self.rebuild:
                continue
            try:
                feats = self.feature_engineer.create_match_features(match, include_adjusted=False)
                if not feats:  # skipped due to sparse history, errors, etc.
                    continue
                if match.won is None:
                    feats['target'] = None
                else:
                    feats['target'] = 1 if match.won else 0
                feats['match_id'] = match.id
                feats['date'] = match.date
                feats['player_id'] = match.player.id  # stable id
                feats['opponent_id'] = match.opponent.id

                if self._all_zero_features(feats):
                    continue

                training_data.append(feats)
                
                mf = MatchFeatures(
                    match=match,
                    player_won=match.won,
                    **{k: feats.get(k) for k in self.FEATURE_FIELDS}
                )
                
                if match.id in existing_ids:
                    mf.id = MatchFeatures.objects.get(match=match).id
                    to_update.append(mf)
                else:
                    to_create.append(mf)
                    
                if len(to_create) >= 500:
                    MatchFeatures.objects.bulk_create(to_create)
                    to_create = []
                if len(to_update) >= 500:
                    MatchFeatures.objects.bulk_update(to_update, fields=self.FEATURE_FIELDS)
                    to_update = []
                
            except Exception as e:
                print(f"Error processing match {getattr(match,'id',None)}: {e}")
                continue
            
        if to_create:
            MatchFeatures.objects.bulk_create(to_create)
        if to_update:
            MatchFeatures.objects.bulk_update(to_update, fields=self.FEATURE_FIELDS)

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