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
from tennis.models import Player, PlayerMatch, \
    Tournament  # add other models with FK to Player if you prefer explicit updates


def pctg_to_dec(pctg):
    return float(pctg.replace("%", "")) / 100

features = ['win_rate', 'dominance_ratio', 'serve_rating', 'return_rating']
features_adjusted = ['win_rate_adjusted', 'dominance_ratio_adjusted', 'serve_rating_adjusted', 'return_rating_adjusted']


class Command(BaseCommand):
    def handle(self, *args, **options):
        collector = TennisDataCollector(start_date="2023-01-01", end_date=datetime.date.today()).collect_training_data()
        return None
