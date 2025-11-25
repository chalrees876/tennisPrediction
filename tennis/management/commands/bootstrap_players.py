# tennis/management/commands/bootstrap_players.py

from django.core.management.base import BaseCommand

from tennis.services.api_client import TennisAPIClient
from tennis.services.players import ensure_player_from_api


class Command(BaseCommand):
    help = (
        "Initial bootstrap: use get_standings to collect player_keys and "
        "populate the Player table via the per-player API."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--tour",
            type=str,
            default="atp",
            help="Tour to pull standings for (e.g. 'atp', 'wta').",
        )
        parser.add_argument(
            "--season",
            type=str,
            default=None,
            help="Optional season/year if your get_standings API requires it.",
        )

    def handle(self, *args, **options):
        tour = options["tour"]
        season = options["season"]

        client = TennisAPIClient()

        # 🔹 Adapt this call name/params to your client implementation
        # e.g. client.get_standings(tour, season=season)
        if season:
            standings = client.get_rankings()
        else:
            standings = client.get_rankings()

        # Collect unique player_keys from the standings
        # (use dict to also keep the short display name if you want)
        player_keys = {}

        for row in standings:
            key = row.get("player_key")
            if not key:
                continue
            # Some APIs use 'player_name', some 'player'
            name = row.get("player")
            player_keys[key] = name

        total_keys = len(player_keys)
        self.stdout.write(f"Found {total_keys} unique players in {tour} standings")

        created = 0
        existing = 0

        for idx, (player_key, short_name) in enumerate(player_keys.items(), start=1):
            player, was_created = ensure_player_from_api(player_key)

            if was_created:
                created += 1
                self.stdout.write(
                    f"[{idx}/{total_keys}] Created {player.name} (key={player_key})"
                )
            else:
                existing += 1
                self.stdout.write(f"[{idx}/{total_keys}] Exists {player.name} (key={player_key})")

        self.stdout.write(
            self.style.SUCCESS(
                f"Bootstrap complete. {created} created, {existing} already existed."
            )
        )
