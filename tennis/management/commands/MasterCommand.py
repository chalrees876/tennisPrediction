import datetime

from django.core.management import BaseCommand, call_command


class Command(BaseCommand):
    def handle(self, *args, **options):
        commands = [
            "EloImport",
            "PlayerStats",
            "PlayerMatchData",
            "UpcomingMatchData",
            "TrainModel",
            ]
        start_time = datetime.datetime.now()
        for command in commands:
            call_command(command)
        end_time = datetime.datetime.now()
        print(end_time-start_time)
