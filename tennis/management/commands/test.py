from pprint import pprint

from django.core.management import BaseCommand
from django.db.models import Q

from tennis.models import PlayerMatch


class Command(BaseCommand):

    def handle(self, *args, **options):
        q1 = (Q(player__name="Jannik Sinner", opponent__name="Ben Shelton"))
        q2 =  Q(player__name="Ben Shelton", opponent__name="Jannik Sinner")

        matches = PlayerMatch.objects.filter(Q(q1) | Q(q2))
        for match in matches:
            print(match, match.id, match.player)