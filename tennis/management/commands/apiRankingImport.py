import math
from datetime import datetime, timedelta
import os
import sys
from pprint import pprint
from typing import Optional

from dotenv import load_dotenv
import requests

load_dotenv()

organization = "ATP"

url = f"https://api.api-tennis.com/tennis/?method=get_standings&event_type={organization}&APIkey={os.getenv('API_KEY')}"

response = requests.get(url)

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

players = []

for player in response.json()["result"]:
    players_dict = {
        "name": player["player"],
        "key": player["player_key"]
    }
    players.append(players_dict)

url2 = f"https://api.api-tennis.com/tennis/?method=get_fixtures&APIkey={os.getenv('API_KEY')}&date_start=1999-01-01&date_stop={str(datetime.today().date())}&player_key={players[3]['key']}"

response = requests.get(url2)

player_key = players[3]['key']

def get_statistics(row, key):
    stat_period = row.get("stat_period")
    if stat_period == "match" and row["player_key"] == player_key:
        print(f"{row['stat_name']} {row['stat_value']}")
        print(f"{row['stat_won']} out of {row['stat_total']}")


for event in response.json()["result"]:
    tournament = event["tournament_name"]
    tournament_key = event["tournament_key"]
    key = event["event_key"]
    date = event["event_date"]
    time = event["event_time"]
    print(tournament, date, time)
    event_winner = event["event_winner"]
    print(event_winner)
    statistics = event["statistics"]
    print(len(statistics))
    for row in statistics if statistics else []:
        get_statistics(row, player_key)
