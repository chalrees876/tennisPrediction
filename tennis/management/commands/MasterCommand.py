# tennis/management/commands/MasterCommand.py
from django.core import management
from django.core.management import BaseCommand
from django.db import transaction

from tennis.models import PlayerMatch, MatchPrediction
from tennis.ml.predictor import predict_for_match


class Command(BaseCommand):
    help = "Master command to start project."

    def add_arguments(self, parser):
        parser.add_argument(
            "--only-missing",
            action="store_true",
            help="Only compute predictions for matches without predictions.",
        )

    def handle(self, *args, **options):
        management.call_command("sync_tennis_data", )