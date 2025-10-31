import re
from datetime import datetime, timedelta
from pprint import pprint

from django.core.management import BaseCommand, call_command
from django.db import transaction, IntegrityError, connections
from django.db.models import Q

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

from tennis.management.commands import UpcomingMatches
from tennis.models import (
    Player,
    PlayerMatch,
    Tournament,
    PlayerMatchServeStats,
    PlayerMatchReturnStats,
)

# -----------------------
# Helpers
# -----------------------
from typing import Tuple

def _canon_pair_ids(a_id: int, b_id: int) -> Tuple[int, int]:
    """Return (lo, hi) ID order so we can dedupe independent of orientation."""
    return (a_id, b_id) if a_id <= b_id else (b_id, a_id)

def _merge_child(model, src, dst):
    """
    Move child row (src) into dst if needed, then delete src.
    For simple 1-1 children keyed by `match`, we usually just drop duplicates.
    Adjust if you want to *merge* field-by-field.
    """
    if src.id == dst.id:
        return
    # Example: keep dst, drop src
    src.delete()

def _with_page(url, fn):
    """
    Spin up Chromium, open one page, route to block images, run fn(page),
    return fn(page) result, and tear everything down — so no async context
    remains when we hit the ORM.
    """
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-dev-shm-usage","--no-sandbox"])
        context = browser.new_context(
            user_agent=("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
            viewport={"width": 1280, "height": 900},
            java_script_enabled=True,
        )
        context.set_default_timeout(30_000)
        page = context.new_page()
        # Block images for speed
        page.route("**/*", lambda route: route.abort() if route.request.resource_type == "image" else route.continue_())
        try:
            page.goto(url, wait_until="domcontentloaded")
            return fn(page)
        finally:
            try:
                page.close()
            except Exception:
                pass
            try:
                context.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass


def _is_blank(x):
    return x is None or str(x).strip() in {"", "—", "-", "NA", "N/A"}

def to_int(x):
    try:
        return int(x) if not _is_blank(x) else None
    except (TypeError, ValueError):
        return None

def to_float(x):
    try:
        return float(x) if not _is_blank(x) else None
    except (TypeError, ValueError):
        return None

def pctg_to_dec_safe(x):
    if _is_blank(x):
        return None
    try:
        return float(str(x).replace("%", "").strip()) / 100.0
    except ValueError:
        return None

def parse_date_dd_mmm_yyyy(s):
    if _is_blank(s):
        return None
    clean = re.sub(r"[\u2010-\u2015\u2212\uFE58\uFE63\uFF0D]", "-", str(s).strip())
    return datetime.strptime(clean, "%d-%b-%Y").date()

def parse_time_hms(s):
    """Return timedelta or None for strings like '1:35' or '2:05:12'."""
    if _is_blank(s):
        return None
    parts = [p for p in str(s).split(":") if p != ""]
    try:
        if len(parts) == 2:
            m, sec = map(int, parts)
            return timedelta(minutes=m, seconds=sec)
        elif len(parts) == 3:
            h, m, sec = map(int, parts)
            return timedelta(hours=h, minutes=m, seconds=sec)
    except ValueError:
        return None
    return None

# If you want to shard by rank ranges later.
RANGES = [(1, 100), (101, 200), (201, 300), (301, 500)]

# -----------------------
# Management Command
# -----------------------
class Command(BaseCommand):
    help = "Scrape TennisAbstract player recent matches via Playwright (serve + return tables) " \
           "with duplicate-prevention on insert."

    def handle(self, *args, **options):
        players = Player.objects.filter(name="Ben Shelton").only("id", "name", "ranking")
        for player in players:
            self.process_player(player)
        self.stdout.write(self.style.SUCCESS("Finished importing."))
        call_command("UpcomingMatches")

    def process_player(self, player):
        self.stdout.write(f"Importing recent matches for {player.name} (rank {player.ranking})")
        results = self.get_results(player)

        for row in results:
            row['Completed'] = not (row.get('Score') == 'Live Scores' or not (row.get('Score') or "").strip())
            if not row['Completed']:
                row['Won'] = None
            pprint(row)
            try:
                with transaction.atomic():
                    # Tournament
                    m_date = parse_date_dd_mmm_yyyy(row.get('Date'))
                    year = int(str(row['Date'])[-4:]) if row.get('Date') else None
                    tournament, _ = Tournament.objects.get_or_create(name=row.get('Tournament') or "", year=year)

                    # Opponent
                    for _try in range(2):
                        try:
                            opponent, _ = Player.objects.get_or_create(name=row.get('Opponent') or "")
                            break
                        except IntegrityError:
                            connections.close_all()
                            continue

                    # Round
                    m_round = row.get('Rd') or -1

                    # FIXED: Better duplicate detection and handling
                    self.process_match_record(player, opponent, tournament, m_date, m_round, row)

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error for {player.name}: {e}"))

    def process_match_record(self, player, opponent, tournament, date, round_num, row):
        """
        Process a match record, handling duplicates by checking both orientations
        and ensuring we only create one record per unique match.
        """
        # Check if match already exists in either orientation
        existing_match = PlayerMatch.objects.filter(
            tournament=tournament,
            date=date,
            round=round_num
        ).filter(
            Q(player=player, opponent=opponent) |
            Q(player=opponent, opponent=player)
        ).first()

        if existing_match:
            # Match already exists - update it if this player's perspective has newer/more complete data
            if existing_match.player == player:
                # This is the same perspective, update normally
                PlayerMatch.objects.filter(pk=existing_match.pk).update(**self.player_match_defaults(row))
                match = PlayerMatch.objects.get(pk=existing_match.pk)
                self.update_match_stats(match, row)
                self.stdout.write(
                    self.style.WARNING(f"Updated existing match: {match.player.name} v {match.opponent.name}"))
            else:
                # This is the reverse perspective - we might want to update some fields
                # but be careful not to overwrite the original perspective's data
                self.stdout.write(
                    self.style.WARNING(f"Match exists in reverse, skipping: {opponent.name} v {player.name}"))
        else:
            # Create new match record
            match = PlayerMatch.objects.create(
                player=player,
                opponent=opponent,
                tournament=tournament,
                date=date,
                round=round_num,
                **self.player_match_defaults(row)
            )
            self.update_match_stats(match, row)
            self.stdout.write(self.style.SUCCESS(f"Created new match: {match.player.name} v {match.opponent.name}"))

    def update_match_stats(self, match, row):
        """Update serve and return stats for a match"""
        PlayerMatchServeStats.objects.update_or_create(
            match=match, defaults=self.serve_stats_defaults(row)
        )
        PlayerMatchReturnStats.objects.update_or_create(
            match=match, defaults=self.return_stats_defaults(row)
        )

    # -------------
    # Scrapers (keep your existing scrapers)
    # -------------
    def get_results(self, player):
        try:
            serve_results = self.get_recent_serve_results(player)
            return_results = self.get_recent_return_results(player)
            n = min(len(serve_results), len(return_results))
            return [{**serve_results[i], **return_results[i]} for i in range(n)]
        except Exception as e:
            print(e)
            return []

    def get_recent_serve_results(self, player):
        # ... (keep your existing implementation)
        pass

    def get_recent_return_results(self, player):
        # ... (keep your existing implementation)
        pass

    # -------------
    # Defaults mappers (keep your existing mappers)
    # -------------
    @staticmethod
    def player_match_defaults(row):
        return {
            'completed': bool(row.get('Completed')),
            'date': parse_date_dd_mmm_yyyy(row.get('Date')),
            'surface': row.get('Surface') or "",
            'round': row.get('Rd') or -1,
            'rank': to_int(row.get('Rk')) if row.get('Rk') not in (None, "") else None,
            'opponent_rank': to_int(row.get('vRk')) if row.get('vRk') not in (None, "") else None,
            'score': row.get('Score') or "",
            'won': row.get('Won'),
        }

    @staticmethod
    def serve_stats_defaults(row):
        bp_saved = to_int((row.get('BPSvd') or '').split('/')[0]) if row.get('BPSvd') else None
        bp_faced = to_int((row.get('BPSvd') or '').split('/')[1]) if row.get('BPSvd') else None
        return {
            'dominance_ratio': to_float(row.get('DR')),
            'ace_pctg': pctg_to_dec_safe(row.get('A%')),
            'df_pctg': pctg_to_dec_safe(row.get('DF%')),
            'fs_pctg': pctg_to_dec_safe(row.get('1stIn')),
            'fs_w_pctg': pctg_to_dec_safe(row.get('1st%')),
            'ss_w_pctg': pctg_to_dec_safe(row.get('2nd%')),
            'bp_saved': bp_saved,
            'bp_faced': bp_faced,
            'time': parse_time_hms(row.get('Time')),
        }

    @staticmethod
    def return_stats_defaults(row):
        bp_conv = to_int((row.get('BPCnv') or '').split('/')[0]) if row.get('BPCnv') else None
        bp_chances = to_int((row.get('BPCnv') or '').split('/')[1]) if row.get('BPCnv') else None
        return {
            'dominance_ratio': to_float(row.get('DR')),
            'total_p_w': pctg_to_dec_safe(row.get('TPW')),
            'return_p_w': pctg_to_dec_safe(row.get('RPW')),
            'v_ace_pctg': pctg_to_dec_safe(row.get('vA%')),
            'v_fs_pctg': pctg_to_dec_safe(row.get('v1st%')),
            'v_ss_pctg': pctg_to_dec_safe(row.get('v2nd%')),
            'bp_conv': bp_conv,
            'bp_chances': bp_chances,
            'time': parse_time_hms(row.get('Time')),
        }