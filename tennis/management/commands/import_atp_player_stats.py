import csv
import glob
import os
from datetime import datetime
import re

from django.core.management import BaseCommand
from django.db import transaction
from django.db.models import Q

from tennis.models import Match, Tournament, Player

def add_player_stats(name, row):
    player = Player.objects.filter(name__iexact=name).order_by('id').first()
    player.ranking = row["rank"]
    player.fsr_p_w_pctg = row["% 1st Serve Return Points Won"].replace("%", "")  # % 1st Serve Return Points Won
    player.ssr_p_w_pctg = row["% 2nd Serve Return Points Won"].replace("%", "")  # % 2nd Serve Return Points Won
    player.break_p_w_pctg = row["% Break Points Converted"].replace("%", "")  # % Break Points Converted
    player.return_g_w_pctg = row["% Return Games Won"].replace("%", "")  # % Return Games Won
    player.return_rating = row["Return Rating"]  # Return Rating
    player.break_p_saved_pctg = row["% Break Points Saved"].replace("%", "")  # % Break Points Saved
    player.deciding_s_w_pctg = row["% Deciding Sets Won"].replace("%", "")  # % Deciding Sets Won
    player.tb_w_pctg = row["% Tie Breaks Won"].replace("%", "")  # % Tie Breaks Won
    player.under_pressure_rating = row["Under Pressure Rating"]  # Under Pressure Rating
    player.fsp = row["% 1st Serve"].replace("%", "")  # % 1st Serve
    player.fs_p_w_pctg = row["% 1st Serve Points Won"].replace("%", "") # % 1st Serve Points Won
    player.ss_p_w_pctg = row["% 2st Serve Points Won"].replace("%", "")  # % 2nd Serve Points Won
    player.s_g_w_pctg = row["% Service Games Won"].replace("%", "")  # % Service Games Won
    player.a_m =row["Avg. Aces/ Match"]  # Avg. Aces/ Match
    player.df_m = row["Avg. Double Faults/Match"]
    player.sr = row["Serve Rating"]
    print("added", player.name, "stats")
    print("rank", player.name, player.ranking)
    print("return game w pctg", player.return_g_w_pctg)
    player.save()
class Command(BaseCommand):
    help = 'Import matches from csv file'

    def handle(self, *args, **options):
        data_path = glob.glob("/Users/chrismckenzie/Downloads/tennisprediction/tennis/management/commands/atp_scraping/data/combined_data/*.csv")
        for file in data_path:
            print(file)
            if file.endswith(".csv"):
                with open(file) as csvfile:
                    reader = csv.DictReader(csvfile)
                    for row in reader:
                        try:
                            with transaction.atomic():
                                full_name = ""
                                name = row['Player'].replace("'", "").split(' ')
                                if len(name) == 2:
                                    first_name = name[0]
                                    last_name = name[1]
                                    full_name = first_name + " " + last_name
                                    backwards_name = last_name + " " + first_name
                                elif len(name) == 3:
                                    first_name = name[0]
                                    middle_name = name[1]
                                    last_name = name[2]
                                    full_name = first_name + " " + middle_name + " " + last_name
                                    backwards_name = last_name + " " + middle_name + " " + first_name
                                elif len(name) == 4:
                                    first_name = name[0]
                                    second_name = name[1]
                                    third_name = name[2]
                                    fourth_name = name[3]
                                    full_name = first_name + " " + second_name + " " + third_name + " " + fourth_name
                                    backwards_name = fourth_name + " " + third_name + " " + second_name + " " + first_name
                                qs = Player.objects.filter(
                                    Q(name__iexact=full_name) | (
                                        Q(name__iexact=backwards_name) if backwards_name else Q(pk__isnull=True))
                                ).order_by("id")

                                player = qs.first()  # avoid MultipleObjectsReturned
                                player_name = player.name if player else full_name

                                add_player_stats(player_name, row)

                        except Exception as b:
                            print(b)

