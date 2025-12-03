import os
from datetime import datetime, timedelta
from typing import Optional, Union, Tuple, List

from django.core.management import BaseCommand
from django.db import transaction
from dotenv import load_dotenv
import requests

from tennis.models import (
    Player,
    PlayerMatch,
    Tournament,
    MatchStatistic,
)


class Command(BaseCommand):
    help = "Import match data into PlayerMatch from api-tennis.com"

    def add_arguments(self, parser):
        parser.add_argument(
            "--date-start",
            default="1999-01-01",
            help="Start date for fixtures in YYYY-MM-DD",
        )
        parser.add_argument(
            "--date-stop",
            default=(datetime.today() + timedelta(days=90)).strftime("%Y-%m-%d"),
            help="End date for fixtures in YYYY-MM-DD",
        )
        parser.add_argument(
            "--start-rank",
            type=int,
            default=None,
            help="Starting rank for player filter (e.g., 1)",
        )
        parser.add_argument(
            "--end-rank",
            type=int,
            default=None,
            help="Ending rank for player filter (e.g., 100)",
        )
        parser.add_argument(
            "--league",
            default="ATP",
            choices=["ATP", "WTA"],
            help="League to filter rankings (ATP or WTA)",
        )

    def handle(self, *args, **options):
        load_dotenv()
        api_key = os.getenv("API_KEY")
        if not api_key:
            self.stderr.write(self.style.ERROR("API_KEY not set in environment"))
            return

        date_start = options["date_start"]
        date_stop = options["date_stop"]
        start_rank = options.get("start_rank")
        end_rank = options.get("end_rank")
        league = options["league"]

        if start_rank and end_rank:
            # Filter by ranking range
            players = Player.objects.filter(
                playerranking__league=league,
                playerranking__ranking__gte=start_rank,
                playerranking__ranking__lte=end_rank,
            ).distinct()
        else:

            all_players = Player.objects.all()

            for player in all_players:
                url = (
                    "https://api.api-tennis.com/tennis/"
                    f"?method=get_fixtures&APIkey={api_key}"
                    f"&date_start={date_start}&date_stop={date_stop}"
                    f"&player_key={player.key}"
                )

                self.stdout.write(f"Fetching fixtures for {player.name} ({player.key})")
                try:
                    resp = requests.get(url, timeout=30)
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f"Request error: {e}"))
                    continue

                events = data.get("result") or []
                for event in events:
                    try:
                        self._upsert_match_from_event(event)
                    except Exception as e:
                        self.stderr.write(
                            self.style.ERROR(
                                f"Failed to import event {event.get('event_key')}: {e}"
                            )
                        )

    @transaction.atomic
    def _upsert_match_from_event(self, event: dict):
        """
        Take one event from the API and create/update:
          - Tournament
          - PlayerMatch (with JSON stats, scores, point-by-point)
          - MatchStatistic rows (if statistics exist)
        """

        ALLOWED_TYPES = {"Atp Singles"}

        # --- basic IDs ---
        event_key = int(event["event_key"])

        # --- date & time ---
        date = datetime.strptime(event["event_date"], "%Y-%m-%d").date()
        time = datetime.strptime(event["event_time"], "%H:%M").time()

        # --- tournament ---
        event_type_raw = (event.get("event_type_type") or "").strip()
        event_type_key_raw = event.get("event_type_key")

        if event_type_raw not in ALLOWED_TYPES:
            return

        event_type_key = None
        if event_type_key_raw not in (None, ""):
            try:
                event_type_key = int(event_type_key_raw)
            except (TypeError, ValueError):
                event_type_key = None

        tournament, _ = Tournament.objects.update_or_create(
            tournament_key=int(event["tournament_key"]),
            defaults={
                "name": event["tournament_name"],
                "event_type_key": event_type_key,
                "event_type_type": event_type_raw,
            },
        )

        season = int(event.get("tournament_season") or event["event_date"][:4])

        # --- players ---
        first_player, _ = Player.objects.get_or_create(
            key=int(event["first_player_key"]),
            defaults={"name": event["event_first_player"]},
        )
        second_player, _ = Player.objects.get_or_create(
            key=int(event["second_player_key"]),
            defaults={"name": event["event_second_player"]},
        )

        # --- winner ---
        winner = None
        winner_field = event.get("event_winner")
        if winner_field == "First Player":
            winner = first_player
        elif winner_field == "Second Player":
            winner = second_player

        # --- scores & formatted score line (handles tiebreaks) ---
        scores = event.get("scores") or []
        score_line = self._build_score_line(scores)
        best_of = self._infer_best_of(event.get("tournament_name", ""), scores)

        # --- status & flags ---
        status = (event.get("event_status") or "").strip()
        is_live = str(event.get("event_live", "0")) == "1"

        qualification_raw = event.get("event_qualification")
        # can be "False", "True", null
        if qualification_raw is None:
            is_qualification = False
        else:
            is_qualification = str(qualification_raw).lower() == "true"

        pointbypoint = event.get("pointbypoint") or None
        statistics = event.get("statistics") or None

        final_result = (event.get("event_final_result") or "").strip()
        event_type = (event.get("event_type_type") or "").strip()
        event_serve = (event.get("event_serve") or "").strip()
        round_str = (event.get("tournament_round") or "").strip()

        match_defaults = {
            "date": date,
            "time": time,
            "tournament": tournament,
            "surface": "Not Specified",  # adjust if you add surface mapping
            "round": round_str,

            "best_of": best_of,

            "first_player": first_player,
            "second_player": second_player,
            "winner": winner,

            "final_result": final_result,
            "score_line": score_line,
            "event_type": event_type,
            "status": status,
            "event_serve": event_serve,
            "is_live": is_live,
            "is_qualification": is_qualification,

            "point_by_point": pointbypoint,
            "statistics_raw": statistics,
            "raw_scores": scores if scores else None,
        }

        match, created = PlayerMatch.objects.update_or_create(
            key=event_key,
            defaults=match_defaults,
        )

        # Refresh structured stats for this match (only if statistics exist)
        self._sync_match_stats(match, statistics or [])

        if created:
            self.stdout.write(self.style.SUCCESS(f"Created match {match.key}"))
        else:
            self.stdout.write(self.style.WARNING(f"Updated match {match.key}"))

    def _sync_match_stats(self, match: PlayerMatch, stats_list: List[dict]):
        """
        Turn the event['statistics'] JSON into MatchStatistic rows.
        Some matches won't have any statistics; then this is a no-op.
        """

        # Clear old stats first
        MatchStatistic.objects.filter(match=match).delete()
        if not stats_list:
            return

        to_create: List[MatchStatistic] = []

        # Map player_key from stats to Player object once
        player_map = {
            match.first_player.key: match.first_player,
            match.second_player.key: match.second_player,
        }

        for s in stats_list:
            player_key = s.get("player_key")
            player = player_map.get(player_key)
            if player is None:
                # Unexpected key; skip
                continue

            period = s.get("stat_period", "match")
            category = s.get("stat_type", "")
            name = s.get("stat_name", "")

            value_raw = s.get("stat_value", "") or ""

            # Parse value_raw
            value_percent = None
            value_number = None

            if value_raw.endswith("%"):
                # e.g. "63%" -> 63.0
                try:
                    value_percent = float(value_raw.rstrip("%"))
                except ValueError:
                    pass
            else:
                # Try to parse as number (int or float)
                try:
                    value_number = float(value_raw)
                except (TypeError, ValueError):
                    pass

            stat_won = s.get("stat_won")
            stat_total = s.get("stat_total")

            # Ensure int or None
            stat_won = int(stat_won) if stat_won is not None else None
            stat_total = int(stat_total) if stat_total is not None else None

            to_create.append(
                MatchStatistic(
                    match=match,
                    player=player,
                    period=period,
                    category=category,
                    name=name,
                    value_raw=value_raw,
                    value_percent=value_percent,
                    value_number=value_number,
                    stat_won=stat_won,
                    stat_total=stat_total,
                )
            )

        if to_create:
            MatchStatistic.objects.bulk_create(to_create)

    @staticmethod
    def _infer_best_of(tournament_name: str, scores: List[dict]) -> Optional[int]:
        """
        Rough heuristic for best-of-3 vs best-of-5.

        - If it's a known Slam tournament name -> assume best of 5 for ATP singles.
        - Else:
            - If 4 or 5 sets are reported -> best_of = 5
            - If 1–3 sets -> best_of = 3
        - If we have no scores, return None.
        """
        if not scores:
            return None

        num_sets = len(scores)
        if num_sets >= 4:
            return 5
        return 3

    @staticmethod
    def _build_score_line(scores: List[dict]) -> str:
        """
        Convert scores array into something like "6-1 6-7(5) 6-2".
        Skips placeholder sets like 0-0 0-0 0-0 that the API includes.
        """

        if not scores:
            return ""

        def split_score(raw) -> Tuple[int, Optional[int]]:
            """
            '6'   -> (6, None)
            '6.5' -> (6, 5)
            """
            if raw is None:
                return 0, None
            raw_str = str(raw)
            if "." in raw_str:
                g, tb = raw_str.split(".", 1)
                return int(g), int(tb)
            return int(raw_str), None

        set_strings: List[str] = []

        for s in scores:
            sf_raw = s.get("score_first")
            ss_raw = s.get("score_second")
            if sf_raw is None or ss_raw is None:
                continue

            g1, tb1 = split_score(sf_raw)
            g2, tb2 = split_score(ss_raw)

            # --- skip placeholder sets like 0-0 ---
            if g1 == 0 and g2 == 0 and tb1 is None and tb2 is None:
                continue

            # No tiebreak encoded -> simple set like 6-3
            if tb1 is None and tb2 is None:
                set_strings.append(f"{g1}-{g2}")
                continue

            # Tie-break set. We show the loser's tiebreak points in parentheses.
            if g1 > g2:
                loser_tb = tb2
            elif g2 > g1:
                loser_tb = tb1
            else:
                # fallback: same games? choose smaller non-null tb
                candidates = [tb for tb in (tb1, tb2) if tb is not None]
                loser_tb = min(candidates) if candidates else None

            if loser_tb is not None:
                set_strings.append(f"{g1}-{g2}({loser_tb})")
            else:
                set_strings.append(f"{g1}-{g2}")

        return " ".join(set_strings)

