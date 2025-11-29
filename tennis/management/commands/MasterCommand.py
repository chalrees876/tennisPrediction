# tennis/management/commands/MasterCommand.py
from django.core import management
from django.core.management import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Master command to start project."

    def handle(self, *args, **options):
        management.call_command("sync_tennis_data", days=5000, rankings=True)