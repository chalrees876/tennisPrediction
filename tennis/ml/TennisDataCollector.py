
import pandas as pd
import numpy as np
from django.db import transaction
import math
from tennis.ml.feature_engineering import TennisFeatureEngineer
from tennis.models import MatchFeatures, PlayerMatch


class TennisDataCollector:
    def __init__(self, start_date, end_date, rebuild):
        self.start_date = start_date
        self.end_date = end_date
        self.rebuild = rebuild
        self.feature_engineer = TennisFeatureEngineer()

    def collect_training_data(self):
        training_data = []
        qs = (PlayerMatch.objects
              .filter(date__range=[self.start_date, self.end_date])
              .select_related('player','opponent')
              .order_by('date'))

        # keep one perspective per real match if your table is per-player
        matches = [m for m in qs if m.player.id < m.opponent.id]
        total = len(matches)

        for i, match in enumerate(matches):
            if (i + 1) % 500 == 0:
                    print(f"Processed {i + 1}/{total} matches...")
            if MatchFeatures.objects.filter(match=match).exists() and not self.rebuild:
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

            except Exception as e:
                print(f"Error processing match {getattr(match,'id',None)}: {e}")
                continue
            
            
            try:
                with transaction.atomic():
                      MatchFeatures.objects.update_or_create(
                            match=match,
                            defaults={
                                'player_won': match.won,
                                'h2h_win_ratio_diff': feats.get('h2h_win_ratio_diff', 0.0),
                                'h2h_recent_momentum': feats.get('h2h_recent_momentum', 0.0),
                                'recent_form_diff': feats.get('recent_form_diff', 0.0),
                                'win_rate_diff': feats.get('win_rate_diff', 0.0),
                                'serve_rating_diff': feats.get('serve_rating_diff', 0.0),
                                'bp_conv_pctg_diff': feats.get('bp_conv_pctg_diff', 0.0),
                                'dom_ratio_diff': feats.get('dom_ratio_diff', 0.0),
                                'fatigue_diff': feats.get('fatigue_diff', 0.0),
                                'match_volume_14d_diff': feats.get('match_volume_14d_diff', 0.0),
                                'win_rate_hard_diff': feats.get('win_rate_hard_diff'),
                                'win_rate_clay_diff': feats.get('win_rate_clay_diff'),
                                'win_rate_grass_diff': feats.get('win_rate_grass_diff'),
                            }
                        )

            except Exception as e:
                print(f"Error on match {match.id}: {e}")

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