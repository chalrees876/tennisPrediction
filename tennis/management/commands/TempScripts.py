from django.core.management import BaseCommand
from django.db import transaction
from django.db.models import Q
from tennis.models import Player  # add other models with FK to Player if you prefer explicit updates


def pctg_to_dec(pctg):
    return float(pctg.replace("%", "")) / 100

class Command(BaseCommand):
    def handle(self, *args, **options):
        return None
