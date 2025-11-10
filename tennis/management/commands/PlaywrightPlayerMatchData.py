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
        browser = pw.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
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
    try:
        return datetime.strptime(clean, "%d-%b-%Y").date()
    except ValueError:
        # Try alternative format if the first one fails
        try:
            return datetime.strptime(clean, "%d-%B-%Y").date()
        except ValueError:
            return None


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

    def process_player(self, player):
        self.stdout.write(f"Importing recent matches for {player.name} (rank {player.ranking})")
        results = self.get_results(player)

        for row in results:
            row['Completed'] = not (row.get('Score') == 'Live Scores' or not (row.get('Score') or "").strip())
            try:
                with transaction.atomic():
                    # Tournament
                    m_date = parse_date_dd_mmm_yyyy(row.get('Date'))
                    year = m_date.year if m_date else None
                    tournament_name = row.get('Tournament') or ""

                    # Handle tournament names with links
                    if tournament_name.startswith('http') or '(' in tournament_name:
                        tournament_name = self.extract_tournament_name(tournament_name)

                    tournament, _ = Tournament.objects.get_or_create(
                        name=tournament_name,
                        defaults={'year': year}
                    )

                    # Opponent
                    opponent_name = row.get("Opponent")
                    for _try in range(2):
                        try:
                            opponent, _ = Player.objects.get_or_create(name=opponent_name)
                            break
                        except IntegrityError:
                            connections.close_all()
                            continue

                    # Round
                    m_round = row.get('Rd') or -1

                    # Process match record
                    self.process_match_record(player, opponent, tournament, m_date, m_round, row)

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error for {player.name}: {e}"))
                import traceback
                traceback.print_exc()

    def extract_tournament_name(self, tournament_text):
        """Extract clean tournament name from potentially messy text"""
        if not tournament_text:
            return ""

        # If it's a URL, extract the tournament name from the link text
        if tournament_text.startswith('http'):
            return "Unknown Tournament"

        # Remove any parenthetical years or other annotations
        clean_name = re.sub(r'\([^)]*\)', '', tournament_text).strip()
        return clean_name if clean_name else tournament_text

    def extract_opponent_name(self, opponent_text):
        """Extract clean opponent name from the opponent cell text"""
        if not opponent_text:
            return "Unknown Player"

        # The opponent name is usually in an <a> tag, but in our scraped text,
        # we need to extract just the name part
        lines = opponent_text.split('\n')
        for line in lines:
            line = line.strip()
            # Look for lines that might contain the player name
            if line and not line.startswith('(') and not line.endswith(']'):
                # Remove any bracketed country codes like [USA], [ITA], etc.
                clean_name = re.sub(r'\[[A-Z]+\]', '', line).strip()
                if clean_name and len(clean_name) > 1:
                    return clean_name

        # Fallback: try to extract from the entire text
        clean_name = re.sub(r'\([^)]*\)', '', opponent_text)  # Remove parentheses
        clean_name = re.sub(r'\[[A-Z]+\]', '', clean_name)  # Remove country codes
        clean_name = clean_name.replace('d.', '').replace('vs', '').strip()  # Remove match indicators

        return clean_name if clean_name else "Unknown Player"

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
            self.stdout.write(f"Deleting existing match: {existing_match}")
            PlayerMatch.objects.filter(pk=existing_match.pk).delete()

        match = PlayerMatch.objects.create(
            player=player,
            opponent=opponent,
            tournament=tournament,
            date=date,
            round=round_num,
            **self.player_match_defaults(row)
        )
        self.update_match_stats(match, row)
        self.stdout.write(self.style.SUCCESS(f"Created new match: {match}"))

    def update_match_stats(self, match, row):
        """Update serve and return stats for a match"""
        serve_defaults = self.serve_stats_defaults(row)
        if serve_defaults:
            PlayerMatchServeStats.objects.update_or_create(
                match=match, defaults=serve_defaults
            )

        return_defaults = self.return_stats_defaults(row)
        if return_defaults:
            PlayerMatchReturnStats.objects.update_or_create(
                match=match, defaults=return_defaults
            )

    # -------------
    # Scrapers - NOW USING PLAYWRIGHT ONLY
    # -------------
    def get_results(self, player):
        try:
            serve_results = self.get_recent_serve_results(player)
            return_results = self.get_recent_return_results(player)

            # Merge results by index (assuming same order)
            merged_results = []
            min_length = min(len(serve_results), len(return_results))

            for i in range(min_length):
                merged_row = {**serve_results[i], **return_results[i]}
                merged_results.append(merged_row)

            return merged_results
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error getting results for {player.name}: {e}"))
            import traceback
            traceback.print_exc()
            return []

    def get_recent_serve_results(self, player):
        """Get serve results using Playwright"""
        url = f"https://www.tennisabstract.com/cgi-bin/player-classic.cgi?p={player.name.replace(' ', '')}"

        def parse_serve_page(page):
            total_data = []
            try:
                # Wait for the table to load
                page.wait_for_selector("#matches", timeout=10000)

                # Get the table
                table = page.query_selector("#matches")

                # Get headers - these are fixed based on the HTML structure
                headers = [
                    "Date", "Tournament", "Surface", "Rd", "Rk", "vRk",
                    "Opponent", "Score", "More", "DR", "A%", "DF%", "1stIn",
                    "1st%", "2nd%", "BPSvd", "Time"
                ]

                # Get rows
                rows = table.query_selector("tbody").query_selector_all("tr")

                for row in rows:
                    cells = row.query_selector_all("td")
                    if len(cells) < 8:  # Skip rows that don't have enough data
                        continue

                    cell_data = {}
                    won = None
                    completed = True

                    for i, cell in enumerate(cells):
                        if i < len(headers):
                            cell_value = cell.inner_text().strip()

                            if i == 6:  # Opponent column - contains match result info
                                # Extract opponent name from the <a> tag
                                opponent_link = cell.query_selector("a")
                                if opponent_link:
                                    opponent_name = opponent_link.inner_text().strip()
                                    cell_data[headers[i]] = opponent_name
                                else:
                                    # Fallback: try to extract from text
                                    cell_data[headers[i]] = cell_value

                                # Determine if player won
                                full_text = cell_value
                                if " d. " in full_text:
                                    if full_text.find(opponent_name) < full_text.find(" d. "):
                                        # Current player is the winner
                                        won = False
                                    else:
                                        won = True
                                elif "vs" in full_text:
                                    # Match is ongoing or scheduled
                                    won = None
                                    completed = False
                                else:
                                    # Couldn't determine, assume completed but unknown result
                                    won = None

                            elif i == 7:  # Score column
                                cell_data[headers[i]] = cell_value
                                # Check if match is completed
                                if cell_value in ["", "Live Scores"]:
                                    completed = False

                            else:
                                cell_data[headers[i]] = cell_value

                    # Add derived fields
                    cell_data['Won'] = won
                    cell_data['Completed'] = completed
                    cell_data['Player'] = player.name

                    total_data.append(cell_data)

                return total_data

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error parsing serve page for {player.name}: {e}"))
                import traceback
                traceback.print_exc()
                return []

        return _with_page(url, parse_serve_page)

    def get_recent_return_results(self, player):
        """Get return results using Playwright"""
        url = f"https://www.tennisabstract.com/cgi-bin/player-classic.cgi?p={player.name.replace(' ', '')}&f=r1"

        def parse_return_page(page):
            total_data = []
            try:
                # Wait for the table to load
                page.wait_for_selector("#matches", timeout=10000)

                # Get the table
                table = page.query_selector("#matches")

                # Get headers - these are different for return stats
                headers = [
                    "Date", "Tournament", "Surface", "Rd", "Rk", "vRk",
                    "Opponent", "Score", "More", "DR", "TPW", "RPW", "vA%",
                    "v1st%", "v2nd%", "BPCnv", "Time"
                ]

                # Get rows
                rows = table.query_selector("tbody").query_selector_all("tr")

                for row in rows:
                    cells = row.query_selector_all("td")
                    if len(cells) < 8:  # Skip rows that don't have enough data
                        continue

                    cell_data = {}

                    for i, cell in enumerate(cells):
                        if i < len(headers):
                            cell_value = cell.inner_text().strip()

                            if i == 6:  # Opponent column
                                # Extract opponent name from the <a> tag
                                opponent_link = cell.query_selector("a")
                                if opponent_link:
                                    opponent_name = opponent_link.inner_text().strip()
                                    cell_data[headers[i]] = opponent_name
                                else:
                                    cell_data[headers[i]] = cell_value
                            else:
                                cell_data[headers[i]] = cell_value

                    cell_data['Player'] = player.name
                    total_data.append(cell_data)

                return total_data

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error parsing return page for {player.name}: {e}"))
                import traceback
                traceback.print_exc()
                return []

        return _with_page(url, parse_return_page)

    # -------------
    # Defaults mappers
    # -------------
    @staticmethod
    def player_match_defaults(row):
        return {
            'completed': bool(row.get('Completed')),
            'surface': row.get('Surface') or "",
            'rank': to_int(row.get('Rk')) if row.get('Rk') not in (None, "") else None,
            'opponent_rank': to_int(row.get('vRk')) if row.get('vRk') not in (None, "") else None,
            'score': row.get('Score') or "",
            'won': row.get('Won'),
        }

    @staticmethod
    def serve_stats_defaults(row):
        # Handle break points saved (format: "saved/faced")
        bp_saved, bp_faced = None, None
        if row.get('BPSvd'):
            bp_parts = (row.get('BPSvd') or '').split('/')
            if len(bp_parts) == 2:
                bp_saved = to_int(bp_parts[0])
                bp_faced = to_int(bp_parts[1])

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
        # Handle break points converted (format: "converted/chances")
        bp_conv, bp_chances = None, None
        if row.get('BPCnv'):
            bp_parts = (row.get('BPCnv') or '').split('/')
            if len(bp_parts) == 2:
                bp_conv = to_int(bp_parts[0])
                bp_chances = to_int(bp_parts[1])

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