import datetime
from pprint import pprint

from django.core.management import BaseCommand
from django.db import transaction
from django.db.models import Q

from tennis.ml.TennisDataCollector import TennisDataCollector
from tennis.ml.feature_engineering import TennisFeatureEngineer
from tennis.models import Player, PlayerMatch  # add other models with FK to Player if you prefer explicit updates


def pctg_to_dec(pctg):
    return float(pctg.replace("%", "")) / 100

class Command(BaseCommand):
    def handle(self, *args, **options):
        collector = TennisDataCollector(start_date="2023-01-01", end_date=datetime.date.today()).collect_training_data()
        print(collector)
        return None
