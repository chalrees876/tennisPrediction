import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pprint import pprint

from django.core.management import BaseCommand
from django.db import transaction, IntegrityError, connections
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

from tennis.models import Player, PlayerMatch, Tournament, PlayerMatchServeStats, PlayerMatchReturnStats

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


RANGES = [(1, 100), (101, 200), (201, 300), (301, 500)]

class Command(BaseCommand):
    help = "Imports players recent matches along with serve and return stats."

    def handle(self, *args, **options):
        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = [ex.submit(self.process_range, lo, hi) for lo, hi in RANGES]
            for f in as_completed(futures):
                # Surface any exceptions that occurred in threads
                f.result()

        self.stdout.write(self.style.SUCCESS("Finished importing for all ranges."))

    def process_range(self, lo, hi):
        """Run the existing import loop for one rank range."""
        # Make sure each thread owns a fresh DB connection
        connections.close_all()
        players = Player.objects.filter(ranking__gte=lo, ranking__lte=hi).only("id", "name", "ranking")
        self.stdout.write(self.style.NOTICE(f"Processing ranks {lo}-{hi} ({players.count()} players)"))

        for player in players.iterator(chunk_size=50):
            self.process_player(player)

        connections.close_all()

    def process_player(self, player):
        """Your current per-player logic goes here (slightly tidied)."""
        self.stdout.write(f"Importing recent matches for {player.name} (rank {player.ranking})")
        results = self.get_results(player)
        for row in results:
            row['Completed'] = not (row.get('Score') == 'Live Scores' or not row.get('Score', '').strip())
            with transaction.atomic():
                try:
                    tournament, _ = Tournament.objects.get_or_create(
                        name=row['Tournament'],
                        year=int(str(row['Date'])[-4:]) if row.get('Date') else None
                    )

                    # Opponent get_or_create can race across threads; retry once if needed.
                    for _try in range(2):
                        try:
                            opponent, _ = Player.objects.get_or_create(name=row['Opponent'])
                            break
                        except IntegrityError:
                            connections.close_all()
                            continue

                    match, created = PlayerMatch.objects.update_or_create(
                        player=player,
                        opponent=opponent,
                        tournament=tournament,
                        defaults=self.player_match_defaults(row)
                    )
                    self.stdout.write(self.style.SUCCESS(
                        f'{"created" if created else "updated"} {match.player.name} v {match.opponent.name} @ {match.tournament.name}'
                    ))

                    serve_stats, s_created = PlayerMatchServeStats.objects.update_or_create(
                        match=match,
                        defaults=self.serve_stats_defaults(row)
                    )
                    return_stats, r_created = PlayerMatchReturnStats.objects.update_or_create(
                        match=match,
                        defaults=self.return_stats_defaults(row)
                    )

                    # If you actually have point-by-point data:
                    # PlayerPointByPointStats.objects.update_or_create(
                    #     match=match,
                    #     defaults=self.point_by_point_stats_defaults(row)
                    # )

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error for {player.name}: {e}"))

    def get_results(self, player):
        try:
            serve_results = self.get_recent_serve_results(player)
            return_results = self.get_recent_return_results(player)

            results = [{**d1, **d2} for d1, d2 in zip(serve_results, return_results)]
            pprint(results)

            return results
        except Exception as e:
            print(f"{e}")
            return []

    @staticmethod
    def get_recent_serve_results(player):
        # Set up Chrome options
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run in background
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-images")  # Block images for faster loading
        chrome_options.add_experimental_option("prefs", {
            "profile.managed_default_content_settings.images": 2,  # Disable images
        })

        # Initialize driver
        driver = webdriver.Chrome(options=chrome_options)
        try:
            driver.get(f"https://www.tennisabstract.com/cgi-bin/player-classic.cgi?p={player.name.replace(' ', '')}")

            table = driver.find_element(By.ID, "matches")

            header_data = table.find_elements(By.TAG_NAME, "th")
            headers = []

            for header in header_data:
                if not header.text.strip():
                    headers.append("Opponent")
                else:
                    headers.append(header.text.strip())
            headers.append("Won")

            rows = table.find_element(By.TAG_NAME, "tbody").find_elements(By.TAG_NAME, "tr")
            total_data = []
            for row in rows:
                cell_data = row.find_elements(By.TAG_NAME, "td")
                cell_text = []
                for i, cell in enumerate(cell_data):
                    if i == 6:

                        # The opponent is in <a> tag
                        opponent_link = cell.find_element(By.TAG_NAME, "a")
                        opponent = opponent_link.text.strip()

                        # Get full text to determine who won
                        full_text = cell.text

                        # Check if current player is the winner (opponent appears after "d." in the text)
                        if full_text.find(opponent) < full_text.find(" d. "):
                            # Current player is the winner
                            won = False
                        else:
                            won = True
                        cell_text.append(opponent)
                    elif i == 16:
                        cell_text.append(cell.text)
                        cell_text.append(won)
                    else:
                        cell_text.append(cell.text)
                cell_dict = dict(zip(headers, cell_text))
                cell_dict['Player'] = player.name
                total_data.append(cell_dict)
            driver.close()
        except Exception as e:
            print(e)

        return total_data

    @staticmethod
    def get_recent_return_results(player):
        # Set up Chrome options
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run in background
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-images")  # Block images for faster loading
        chrome_options.add_experimental_option("prefs", {
            "profile.managed_default_content_settings.images": 2,  # Disable images
        })

        # Initialize driver
        driver = webdriver.Chrome(options=chrome_options)
        try:
            driver.get(f"https://www.tennisabstract.com/cgi-bin/player-classic.cgi?p={player.name.replace(' ', '')}&f=r1")

            table = driver.find_element(By.ID, "matches")

            header_data = table.find_elements(By.TAG_NAME, "th")
            headers = [header.text.strip() for header in header_data]
            rows = table.find_element(By.TAG_NAME, "tbody").find_elements(By.TAG_NAME, "tr")
            total_data = []
            for row in rows:
                cell_data = row.find_elements(By.TAG_NAME, "td")
                cell_text = []
                for i, cell in enumerate(cell_data):
                    cell_text.append(cell.text)
                cell_dict = dict(zip(headers, cell_text))
                cell_dict['Player'] = player.name
                total_data.append(cell_dict)
            driver.close()
        except Exception as e:
            print(e)

        return total_data

    @staticmethod
    def player_match_defaults(row):
        return {
            'completed': bool(row.get('Completed')),
            'date': parse_date_dd_mmm_yyyy(row.get('Date')),
            'surface': row.get('Surface') or None,
            'round': row.get('Rd') or None,
            'rank': to_int(row.get('Rk')),
            'opponent_rank': to_int(row.get('vRk')),
            'score': row.get('Score') or None,
            'won': bool(row.get('Won')),
        }

    @staticmethod
    def serve_stats_defaults(row):
        return {
            'dominance_ratio': to_float(row.get('DR')),
            'ace_pctg': pctg_to_dec_safe(row.get('A%')),
            'df_pctg': pctg_to_dec_safe(row.get('DF%')),
            'fs_pctg': pctg_to_dec_safe(row.get('1stIn')),
            'fs_w_pctg': pctg_to_dec_safe(row.get('1st%')),
            'ss_w_pctg': pctg_to_dec_safe(row.get('2nd%')),
            'bp_saved': to_int(row['BPSvd'].split('/')[0]) if row.get('BPSvd') else None,
            'bp_faced': to_int(row['BPSvd'].split('/')[1]) if row.get('BPSvd') else None,
            'time': parse_time_hms(row.get('Time')),
        }

    @staticmethod
    def return_stats_defaults(row):
        return {
            'dominance_ratio': to_float(row.get('DR')),
            'total_p_w': pctg_to_dec_safe(row.get('TPW')),
            'return_p_w': pctg_to_dec_safe(row.get('RPW')),
            'v_ace_pctg': pctg_to_dec_safe(row.get('vA%')),
            'v_fs_pctg': pctg_to_dec_safe(row.get('v1st%')),
            'v_ss_pctg': pctg_to_dec_safe(row.get('v2nd%')),
            'bp_conv': to_int(row['BPCnv'].split('/')[0]) if row.get('BPCnv') else None,
            'bp_chances': to_int(row['BPCnv'].split('/')[1]) if row.get('BPCnv') else None,
            'time': parse_time_hms(row.get('Time')),
        }