import math
from datetime import datetime, timedelta
import os
import sys
from pprint import pprint
from typing import Optional

from django.core.management import BaseCommand
from dotenv import load_dotenv
import requests

from tennis.models import Player


class Command(BaseCommand):
    help = """
    Import player ranking data. Going into django model 'Player'
    columns needed: 
        name (string)
        age (int)
        ranking (int)
    """

    def handle(self, *args, **options):
        load_dotenv()

        organization = "ATP" #just focus on ATP for now
        url = f"https://api.api-tennis.com/tennis/?method=get_standings&event_type={organization}&APIkey={os.getenv('API_KEY')}"
        response = requests.get(url)

        players = []

        #add player dict for all players [{"name": "Novak Djokovic", "key": 1905}, {next}, ....]
        for player in response.json()["result"]:
            players_dict = {
                "name": player["player"],
                "key": player["player_key"]
            }
            players.append(players_dict)
        for i, player in enumerate(players):
            try:
                player_url = f"https://api.api-tennis.com/tennis/?method=get_players&player_key={players[i]['key']}&APIkey={os.getenv('API_KEY')}"
                response = requests.get(player_url)
                result = response.json()['result'][0]
                age = self.convert_bday(result['player_bday'])
                name = result['player_full_name']
                country = result['player_country']
                key = result['player_key']
                player, created = Player.objects.update_or_create(name=name, age=age, country=country, key=key)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully created player {name}, {age}, {country}, {key}" if created else f"Successfully updated player {name}, {age}, {country}, {key}"
                    )
                )
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"{e}"))
            print(i)

    @staticmethod
    def convert_bday(bday: str) -> int:
        try:
            bday = datetime.strptime(bday, "%d.%m.%Y")
            today = datetime.today()
            bday_passed = True if today.month >= bday.month and today.day >= bday.day else False
            age = (today.year - bday.year + 1) if bday_passed else today.year - bday.year
            return int(age)
        except ValueError:
            print("Invalid date")
            return 0
