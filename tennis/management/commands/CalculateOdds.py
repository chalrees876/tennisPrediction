import datetime
from datetime import timedelta
from pprint import pprint
import joblib
from django.core.management import BaseCommand
import pandas as pd
from tennis.ml.feature_engineering import TennisFeatureEngineer
from tennis.models import PlayerMatch, PlayerMatchOdds

def pctg_to_dec(pctg):
    return float(pctg.replace("%", "")) / 100


def prob_to_american(p: float, round_to: int = 1) -> int:
    """
    Convert a fair (no-vig) win probability p to American moneyline.
    p in (0,1). Returns an integer line (e.g., -145, +220).
    """
    # clamp to avoid infinities
    p = min(max(p, 1e-6), 1 - 1e-6)
    if p >= 0.5:
        line = -int(round((p / (1 - p)) * 100.0 / round_to) * round_to)
    else:
        line = int(round(((1 - p) / p) * 100.0 / round_to) * round_to)
    return line


def prob_to_decimal(p: float) -> float:
    """Fair decimal odds (stake-inclusive)."""
    p = min(max(p, 1e-6), 1 - 1e-6)
    return round(1.0 / p, 4)


def american_to_implied_prob(ml: int) -> float:
    """Implied probability from an American moneyline."""
    if ml < 0:
        return (-ml) / ((-ml) + 100.0)
    else:
        return 100.0 / (ml + 100.0)

features = ['win_rate', 'dominance_ratio', 'serve_rating', 'return_rating']
features_adjusted = ['win_rate_adjusted', 'dominance_ratio_adjusted', 'serve_rating_adjusted', 'return_rating_adjusted']


class Command(BaseCommand):
    def handle(self, *args, **options):
        match_odds_list = []
        match_list = []
        bundle = joblib.load('tennis/models/machine_learning.pkl')
        log_reg = bundle["log_reg"]  # (ideally calibrated)
        rf = bundle["rf"]
        ens_w = bundle["ens_w"]
        feats = bundle["features"]

        try:
            upcoming = PlayerMatch.objects.all().order_by('rank')
            for match in upcoming:
                if PlayerMatchOdds.objects.filter(match=match).exists():
                    self.stdout.write(self.style.WARNING(f"Odds already exist for match {match}, skipping"))
                    continue
                self.stdout.write(f"Calculating odds for match {match}")
                reverse_exists = any(
                    m['player']==match.opponent and m['opponent']==match.player for m in match_list
                )
                if reverse_exists:
                    continue
                feats_row = TennisFeatureEngineer().create_match_features(match, include_adjusted=False)
                match_dict = {'player': match.player, 'opponent': match.opponent}
                match_list.append(match_dict)
                # align columns exactly like training
                X_one = pd.DataFrame([feats_row], columns=feats).fillna({
                    'win_rate_hard': 0.5, 'win_rate_clay': 0.5, 'win_rate_grass': 0.5, 'win_rate_carpet': 0.5
                }).fillna(0)

                p_lr = float(log_reg.predict_proba(X_one)[0][1])  # P(player1 wins)
                p_rf = float(rf.predict_proba(X_one)[0][1])
                p_ens = 0.1 * p_lr + 0.9 * p_rf  # optional soft-vote

                # Convert to lines for both sides
                lines = {
                    "log_reg_ml_p1": prob_to_american(p_lr),
                    "log_reg_ml_p2": prob_to_american(1 - p_lr),
                    "rf_ml_p1": prob_to_american(p_rf),
                    "rf_ml_p2": prob_to_american(1 - p_rf),
                    "ens_ml_p1": prob_to_american(p_ens),
                    "ens_ml_p2": prob_to_american(1 - p_ens),

                    "log_reg_dec_p1": prob_to_decimal(p_lr),
                    "log_reg_dec_p2": prob_to_decimal(1 - p_lr),
                    "rf_dec_p1": prob_to_decimal(p_rf),
                    "rf_dec_p2": prob_to_decimal(1 - p_rf),
                    "ens_dec_p1": prob_to_decimal(p_ens),
                    "ens_dec_p2": prob_to_decimal(1 - p_ens),
                }

                match_odds_list.append({
                    "match": match.id,
                    "tournament": match.tournament,
                    "round": match.round,
                    "date": match.date,
                    "completed": match.completed,
                    "log_reg_prob": p_lr,
                    "rf_prob": p_rf,
                    "ens_prob": p_ens,
                    **lines
                })
                
                pmo_obj1, created = PlayerMatchOdds.objects.update_or_create(
                    match=match,
                    defaults={
                        "log_reg_prob": p_lr,
                        "log_reg_amer": lines["log_reg_ml_p1"],
                        "log_reg_dec": lines["log_reg_dec_p1"],
                        "rf_prob": p_rf,
                        "rf_amer": lines["rf_ml_p1"],
                        "rf_dec": lines["rf_dec_p1"],
                        "ens_prob": p_ens,
                        "ens_amer": lines["ens_ml_p1"],
                        "ens_dec": lines["ens_dec_p1"],
                    }
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f"Created odds for match {match}"))
                else:
                    self.stdout.write(self.style.WARNING(f"Updated odds for match {match}"))
                    
                pmo_obj2, created = PlayerMatchOdds.objects.update_or_create(
                    match=match,
                    defaults={
                        "log_reg_prob": 1 - p_lr,
                        "log_reg_amer": lines["log_reg_ml_p2"],
                        "log_reg_dec": lines["log_reg_dec_p2"],
                        "rf_prob": 1 - p_rf,
                        "rf_amer": lines["rf_ml_p2"],
                        "rf_dec": lines["rf_dec_p2"],
                        "ens_prob": 1 - p_ens,
                        "ens_amer": lines["ens_ml_p2"],
                        "ens_dec": lines["ens_dec_p2"],
                    }
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f"Created odds for match {match} (opponent)"))
                else:
                    self.stdout.write(self.style.WARNING(f"Updated odds for match {match} (opponent)"))
                    
        except Exception as e:
            print(e)
        df = pd.DataFrame(match_odds_list)
        pprint(df)
        df.to_csv('tennis/models/probabilities.csv', index=False)