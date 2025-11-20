import math
from datetime import datetime, timedelta
import os
import sys
from pprint import pprint
from typing import Optional

from django.core.management import BaseCommand
from dotenv import load_dotenv
import requests

from tennis.models import Player, PlayerRanking


class Command(BaseCommand):
    help = """
    Import player ranking data. Going into django model 'PlayerRanking'
    columns needed: 
        player (player object)
        ranking (int)
        league (Enum)
        movement (Enum)
        points (int)
    """

    def handle(self, *args, **options):
        load_dotenv()
        organization = "ATP" #just focus on ATP for now
        url = f"https://api.api-tennis.com/tennis/?method=get_standings&event_type=ATP&APIkey={os.getenv('API_KEY')}"
        response = requests.get(url)
        for player in response.json()["result"]:
            try:
                key = player["player_key"]
                ranking = player["place"]
                league=player["league"]
                movement = player["movement"]
                points = player["points"]
                player, created = PlayerRanking.objects.update_or_create(player=Player.objects.get(key=key), ranking=ranking, league=league, movement=movement, points=points)
                if created:
                    self.stdout.write(self.style.SUCCESS(f"Player {key} created successfully!"))
                else:
                    self.stdout.write(self.style.ERROR(f"Player {key} updated successfully!"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"{e}"))
