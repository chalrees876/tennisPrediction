import datetime
from pprint import pprint
import joblib
from django.core.management import BaseCommand
from django.db import transaction
from django.db.models import Q
import pandas as pd

from tennis.ml.MachineLearning import MachineLearningModels
from tennis.ml.TennisDataCollector import TennisDataCollector
from tennis.ml.feature_engineering import TennisFeatureEngineer
from tennis.models import Player, PlayerMatch  # add other models with FK to Player if you prefer explicit updates


def pctg_to_dec(pctg):
    return float(pctg.replace("%", "")) / 100

features = ['win_rate', 'dominance_ratio', 'serve_rating', 'return_rating']
features_adjusted = ['win_rate_adjusted', 'dominance_ratio_adjusted', 'serve_rating_adjusted', 'return_rating_adjusted']


class Command(BaseCommand):
    def handle(self, *args, **options):

        matches = PlayerMatch.objects.all()[:100]
        for match in matches:
            model = joblib.load('adjusted_model.joblib')
            features = features_adjusted
            print(f"----------------------------Match: {match} --------------------------------")
            match_features = TennisFeatureEngineer().create_match_features(match)
            X_one = pd.DataFrame([match_features], columns=features)
            print(X_one)

            p1_prob = model.predict_proba(X_one)[0,1]
            odds = p1_prob / (1 - p1_prob)
            print(f"----------------------------Odds player 1 wins: {odds}-----------------------")
        return None
