# tennis/management/commands/sync_tennis_data.py

from django.core.management import BaseCommand
from django.utils import timezone
from datetime import timedelta

from tennis.services.api_sync import sync_matches_for_players
from tennis.services.odds import sync_odds_for_single_tournament
from tennis.services.players import ensure_player_from_api
from tennis.services.rankings import sync_rankings
from tennis.models import Tournament, Player


class Command(BaseCommand):
    help = "Sync all tennis data (fixtures, stats, odds, players, rankings)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="How many past/future days of matches to sync.",
        )
        parser.add_argument(
            "--rankings",
            action="store_true",
            help="Also sync ATP/WTA rankings.",
        )
        parser.add_argument(
            "--players",
            action="store_true",
            help="Update player bio information.",
        )

    def handle(self, *args, **opt):
        days = opt["days"]
        today = timezone.localdate()

        date_start = (today - timedelta(days=days)).strftime("%Y-%m-%d")
        date_stop = (today + timedelta(days=days)).strftime("%Y-%m-%d")


        # ---- Optional: Update player details ----
        if opt["players"]:
            self.stdout.write("Updating player biographical info…")
            for p in Player.objects.all():
                ensure_player_from_api(p.key)

        # ---- Optional: Sync rankings ----
        if opt["rankings"]:
            self.stdout.write("Updating ATP rankings…")
            sync_rankings("ATP")

        self.stdout.write(f"Syncing matches between {date_start} and {date_stop}…")

        # ---- NEW: per-player fixtures sync ----
        #created, updated = sync_matches_for_players(date_start, date_stop)
        #self.stdout.write(f"Matches: {created} created, {updated} updated")

        # ---- Sync odds for tournaments ----
        self.stdout.write("Syncing odds…")

        for t in Tournament.objects.all():
            count = sync_odds_for_single_tournament(t.tournament_key)
            self.stdout.write(f"  {t.name}: updated odds for {count} matches")

        self.stdout.write(self.style.SUCCESS("Done."))
