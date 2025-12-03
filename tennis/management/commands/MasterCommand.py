# tennis/management/commands/MasterCommand.py
from django.core import management
from django.core.management import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Master command to start project."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=30,
        )

        parser.add_argument(
            "--maxranking",
            type=int,
            default=100000
        )

        parser.add_argument(
            "--minranking",
            type=int,
            default=1,
        )

    def handle(self, *args, **options):
        days = options["days"]
        maxranking = options["maxranking"]
        minranking = options["minranking"]

        management.call_command("sync_tennis_data", days=days, rankings=True, maxranking=maxranking, minranking=minranking)