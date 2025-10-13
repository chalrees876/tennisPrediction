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
        current_path = os.path.abspath(__file__)
        tennis_app_path = os.path.dirname(os.path.dirname(os.path.dirname(current_path)))
        data_path = glob.glob(tennis_app_path + "/data/cleaned_data/*.csv")
        for file in data_path:
            with open(file) as csvfile:
                reader = csv.DictReader(csvfile)
                with transaction.atomic():
                    for row in reader:
                        try:

                            p1, _ = Player.objects.update_or_create(name=row['player_1'].strip())
                            p2, _ = Player.objects.update_or_create(name=row['player_2'].strip())

                            if row['player_1'] == row['winner']:
                                winner = p1
                                loser = p2
                            else:
                                winner = p2
                                loser = p1

                            match_id = row['match_id']
                            _round = row['round']
                            p1_fsp = float(row['p1_fsp'])
                            p2_fsp = float(row['p2_fsp'])
                            p1_ssp = float(row['p1_ssp'])
                            p2_ssp = float(row['p2_ssp'])
                            p1_df =  int(row['p1_df'])
                            p2_df = int(row['p2_df'])

                            pattern = r'(?P<date>\d{8})-(?P<gender>[^-]+)-(?P<tournament>[^-]+)-(?P<round>[^-]+)-(?P<p1>[^-]+)-(?P<p2>[^-]+)$'
                            m = re.search(pattern, match_id)
                            if m is None:
                                print("Incorrect format", match_id)
                            date = m.group("date")
                            date_format = "%Y%m%d"
                            date = datetime.strptime(date, date_format)
                            year = date.year
                            tournament, _ = Tournament.objects.update_or_create(name=row['tournament'], year=year)
                            score = row['match_score']
                            match, _ = Match.objects.update_or_create(
                                match_id=match_id,
                                player1=p1,
                                player2=p2,
                                winner=winner,
                                loser=loser,
                                tournament=tournament,
                                round=_round,
                                score=score,
                                p1_first_serve_pctg=p1_fsp,
                                p2_first_serve_pctg=p2_fsp,
                                p1_second_serve_pctg=p1_ssp,
                                p2_second_serve_pctg=p2_ssp,
                                p1_double_faults=p1_df,
                                p2_double_faults=p2_df,
                            )

                            created += 1
                        except Exception as e:
                            skipped += 1



