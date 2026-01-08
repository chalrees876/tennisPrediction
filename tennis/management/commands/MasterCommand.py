import datetime

from django.core.management import BaseCommand, call_command


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--full-run',
            type=bool,
            default=False
        )
        parser.add_argument(
            '--reload_predictions',
            type=bool,
            default=False
        )
        parser.add_argument(
            '--import_matches',
            type=bool,
            default=False
        )
        parser.add_argument(
            '--import_stats',
            type=bool,
            default=False
        )
        
    def handle(self, *args, **options):
        commands = [
            "EloImport",
            "PlayerStats",
            "PlayerMatchData",
            "UpcomingMatchData",
            "TrainModel",
            ]
        start_time = datetime.datetime.now()
        if options['full_run']:
            for command in commands:
                call_command(command)
        else:
            if options['import_matches']:
                call_command("PlayerMatchData")
                call_command("UpcomingMatchData")
                call_command("TrainModel", build_features=True, rebuild=True)
            if options['import_stats']:
                call_command("EloImport")
                call_command("PlayerStats")
            if options['reload_predictions']:
                call_command("TrainModel", build_features=True, rebuild=True)
        end_time = datetime.datetime.now()
        print(end_time-start_time)
