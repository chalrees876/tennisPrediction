import csv
import glob
import os
from datetime import datetime
import re

from django.core.management import BaseCommand
from django.db import transaction
from tennis.models import Match, Tournament, Player

class Command(BaseCommand):
    help = 'Import matches from csv file'

    def handle(self, *args, **options):
        skipped = 0
        created = 0
        data_path = glob.glob("/Users/chrismckenzie/Downloads/tennisprediction/tennis/management/commands/atp_scraping/data/combined_data/*.csv")
        for file in data_path:
            print(file)
            if file.endswith(".csv"):
                with open(file) as csvfile:
                    reader = csv.DictReader(csvfile)
                    with transaction.atomic():
                        for row in reader:
                            print(row['Player'])
                            try:
                                print(row['Player'])
                                player = Player.objects.get(name=row['Player'])
                                print("trying")
                                if not player:
                                    print(f'Player {row["Player"]} not found in django model')
                                if player:
                                    print(f'Player {row["Player"]} found in django model')
                            except Exception as e:
                                print(f'Exception: {e}')
                                skipped += 1