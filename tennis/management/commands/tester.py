from django.core.management import BaseCommand

from tennis.ml.apiCollectData import collect_data
from tennis.ml.train_model import main as train_model

class Command(BaseCommand):
    def handle(self, *args, **options):
        collect_data(20)
        train_model(feature_variant="no_odds")
        train_model(feature_variant="odds_only")