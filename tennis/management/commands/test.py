from pprint import pprint

from bs4 import BeautifulSoup
from django.core.management import BaseCommand
from django.db.models import Q
import requests

from tennis.models import PlayerMatch


class Command(BaseCommand):

    def handle(self, *args, **options):
        url = "https://tennisabstract.com/reports/atp_elo_ratings.html"
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        print(soup.prettify())