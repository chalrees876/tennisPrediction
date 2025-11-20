import datetime
import os

from django.core.management import BaseCommand
from django.db import transaction
from dotenv import load_dotenv
import requests

from tennis.models import Tournament, PlayerMatch


class Command(BaseCommand):
    """
    Import odds from api-tennis.com per tournament and store them on PlayerMatch.odds_raw.

    Usage examples:
      - Import odds for tournaments that have matches but no odds yet:
            python manage.py apiImportTournamentOdds

      - Only for a specific tournament key:
            python manage.py apiImportTournamentOdds --tournament-key 1217
    """

    help = "Import odds per tournament and attach them to PlayerMatch.odds_raw"

    def add_arguments(self, parser):
        parser.add_argument(
            "--tournament-key",
            type=int,
            help="If provided, only import odds for this tournament_key",
        )

    def handle(self, *args, **options):
        load_dotenv()
        api_key = os.getenv("API_KEY")
        if not api_key:
            self.stderr.write(self.style.ERROR("API_KEY not set in environment"))
            return

        tournament_key_filter = options.get("tournament_key")

        # Step 1: figure out which tournaments we actually need odds for
        qs = PlayerMatch.objects.filter(odds_raw__isnull=True)

        if tournament_key_filter:
            qs = qs.filter(tournament__tournament_key=tournament_key_filter)

        # filter by event type *before* values_list
        qs = qs.filter(tournament__event_type_type='Atp Singles')

        raw_keys = list(
            qs.values_list("tournament__tournament_key", flat=True)
        )

        # Deduplicate them in Python to be 100% sure
        unique_keys = sorted(set(raw_keys))

        self.stdout.write(f"Raw tournament_key count (from matches): {len(raw_keys)}")
        self.stdout.write(f"Unique tournament_key count: {len(unique_keys)}")
        self.stdout.write(f"Tournament keys to process: {unique_keys[:50]}{'...' if len(unique_keys) > 50 else ''}")

        if not unique_keys:
            self.stdout.write(self.style.WARNING("No tournaments found that need odds."))
            return

        self.stdout.write(f"Found {len(unique_keys)} tournaments needing odds.")

        total_updated = 0
        total_skipped = 0

        for t_key in unique_keys:
            try:
                updated, skipped = self._import_odds_for_tournament(api_key, t_key)
                total_updated += updated
                total_skipped += skipped
            except Exception as e:
                self.stderr.write(
                    self.style.ERROR(f"Error importing odds for tournament {t_key}: {e}")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Matches updated with odds: {total_updated}, "
                f"matches skipped (no odds / no match): {total_skipped}"
            )
        )

    @transaction.atomic
    def _import_odds_for_tournament(self, api_key: str, tournament_key: int):
        """
        Call get_odds for a single tournament and attach odds to PlayerMatch rows.
        Returns: (updated_count, skipped_count)
        """

        base_qs = Tournament.objects.filter(tournament_key=tournament_key)

        if not base_qs.exists():
            self.stderr.write(
                self.style.ERROR(
                    f"Tournament {tournament_key} not found in DB; skipping."
                )
            )
            return 0, 0

        # Prefer ATP singles if present
        atp_qs = base_qs.filter(event_type_type="Atp Singles")
        tournaments_qs = atp_qs if atp_qs.exists() else base_qs

        tournament = tournaments_qs.order_by("-name").first()

        if tournaments_qs.count() > 1:
            self.stdout.write(
                self.style.WARNING(
                    f"Tournament key {tournament_key} has {tournaments_qs.count()} rows "
                    f"(event types). Using {tournament.name} "
                    f"[{tournament.event_type_type}] for logging."
                )
            )

        self.stdout.write(
            f"Fetching odds for tournament {tournament_key} "
            f"({tournament.name} - {tournament.event_type_type})"
        )

        url = (
            "https://api.api-tennis.com/tennis/"
            f"?method=get_odds&APIkey={api_key}&tournament_key={tournament_key}&date_start=1800-01-01&date_stop={datetime.date.today()}"
        )

        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            self.stderr.write(
                self.style.ERROR(f"Request error for tournament {tournament_key}: {e}")
            )
            return 0, 0

        if not data or data.get("success") != 1:
            self.stderr.write(
                self.style.WARNING(
                    f"No success result for tournament {tournament_key} "
                    f"(success={data.get('success')})"
                )
            )
            return 0, 0

        result = data.get("result") or {}
        if not isinstance(result, dict):
            self.stderr.write(
                self.style.ERROR(
                    f"Unexpected result type ({type(result)}) for tournament {tournament_key}"
                )
            )
            return 0, 0

        updated = 0
        skipped = 0

        for match_key_str, odds_payload in result.items():
            try:
                match_key = int(match_key_str)
            except (TypeError, ValueError):
                skipped += 1
                continue

            try:
                match = PlayerMatch.objects.get(key=match_key)
            except PlayerMatch.DoesNotExist:
                skipped += 1
                continue

            if match.odds_raw is not None:
                skipped += 1
                continue

            match.odds_raw = odds_payload
            match.save(update_fields=["odds_raw"])
            updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Tournament {tournament_key}: updated odds for {updated} matches, "
                f"skipped {skipped}."
            )
        )

        return updated, skipped
