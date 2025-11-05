import re
from datetime import datetime
from pprint import pprint

from django.core.management import BaseCommand
from django.db import transaction
from django.db.models import Q
from playwright.sync_api import sync_playwright

from tennis.models import Player, PlayerMatch, Tournament, PlayerMatchServeStats, PlayerMatchReturnStats


class Command(BaseCommand):
    help = "Import players recent matches"
    """
    Splits stats into 3 django models.
    PlayerMatches (holds basic match data like who where and when),
    PlayerMatchServeStats (holds service stats for specified player),
    and PlayerMatchReturnStats (holds return stats for specified player).
    """

    def handle(self, *args, **options):
        try:
            players = Player.objects.filter(ranking__lte=10, ranking__gt=0)
        except Player.DoesNotExist:
            self.stdout.write("Player 'Ben Shelton' not found.")
        player_count = 0
        for player in players:
            try:
                self.stdout.write(f"Importing recent matches for {player.name}")
                self.stdout.write(f"Ranking: {player.ranking}")
                results = self.get_results(player)
                for row in results:
                    if row['Score'] == 'Live Scores' or not row['Score'].strip():
                        row['Completed'] = False
                        row['Won'] = None
                    else:
                        row['Completed'] = True
                    with transaction.atomic():
                        try:
                            tournament, tournament_created = Tournament.objects.get_or_create(name=row['Tournament'], year=row['Date'][-4:])
                            tournament_action = 'created' if tournament_created else 'got'

                            self.stdout.write(
                                self.style.SUCCESS(f'{tournament_action} {tournament.name}')
                            )

                            opponent, opponent_created = Player.objects.get_or_create(name=row['Opponent'])
                            opponent_action = 'created' if opponent_created else 'got'

                            self.stdout.write(
                                self.style.SUCCESS(f'{opponent_action} {opponent.name}')
                            )

                            match, match_created = PlayerMatch.objects.update_or_create(
                                player=player,
                                opponent=opponent,
                                tournament=tournament,
                                date= self.parse_date(row['Date']),
                                round=row['Rd'],
                                defaults=self.player_match_defaults(row, opponent))

                            match_action = 'created' if match_created else 'update'

                            self.stdout.write(
                                self.style.SUCCESS(f'{match_action} {match.player.name} v {match.opponent.name} at {match.tournament.name}')
                            )

                            serve_stats, serve_stats_created = PlayerMatchServeStats.objects.update_or_create(match=match,
                            defaults=self.serve_stats_defaults(row)
                            )

                            match_stats_action = 'created' if serve_stats_created else 'update'

                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'{match_stats_action} stats for {match.player.name} v {match.opponent.name} at {match.tournament.name}')
                            )

                            return_stats, return_stats_created = PlayerMatchReturnStats.objects.update_or_create(match=match,
                            defaults=self.return_stats_defaults(row)
                            )

                            return_stats_action = 'created' if return_stats_created else 'update'

                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'created {match}')
                            )
                            player_count += 1
                        except Exception as e:
                            self.stdout.write(
                                self.style.ERROR(f'Error {e}')
                            )
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error processing player {player.name}: {e}'))

    def get_results(self, player):
        try:
            serve_results = self.get_recent_serve_results(player)
            return_results = self.get_recent_return_results(player)

            results = [{**d1, **d2} for d1, d2 in zip(serve_results, return_results)]
            return results
        except Exception as e:
            print(f"{e}")
            return []

    def get_recent_serve_results(self, player):
        url = f"https://www.tennisabstract.com/cgi-bin/player-classic.cgi?p={player.name.replace(' ', '')}"

        def parse_serve_page(page):
            try:
                page.goto(url, wait_until="domcontentloaded")
                page.wait_for_selector("#matches", timeout=10000)

                table = page.query_selector("#matches")

                header_elements = table.query_selector_all("th")
                headers = []

                for header in header_elements:
                    text = header.inner_text().strip()
                    if not text:
                        headers.append("Opponent")
                    else:
                        headers.append(text)
                headers.append("Won")

                rows = table.query_selector("tbody").query_selector_all("tr")
                total_data = []
                for row in rows:
                    cell_data = row.query_selector_all("td")
                    cell_text = []
                    for i, cell in enumerate(cell_data):
                        if i == 6:
                            # The opponent is in <a> tag
                            opponent_link = cell.query_selector("a")
                            opponent = opponent_link.inner_text().strip()

                            # Get full text to determine who won
                            full_text = cell.inner_text()
                            # Check if current player is the winner (opponent appears after "d." in the text)
                            if full_text.find(opponent) < full_text.find(" d. "):
                                # Current player is the winner
                                won = False
                            else:
                                won = True
                            cell_text.append(opponent)
                        elif i == 16:
                            cell_text.append(cell.inner_text())
                            cell_text.append(won)
                        else:
                            cell_text.append(cell.inner_text())
                    cell_dict = dict(zip(headers, cell_text))
                    cell_dict['Player'] = player.name
                    total_data.append(cell_dict)
                return total_data
            except Exception as e:
                print(f"Error in serve results: {e}")
                return []

        return self._with_page(url, parse_serve_page)

    def get_recent_return_results(self, player):
        url = f"https://www.tennisabstract.com/cgi-bin/player-classic.cgi?p={player.name.replace(' ', '')}&f=r1"

        def parse_return_page(page):
            try:
                page.goto(url, wait_until="domcontentloaded")
                page.wait_for_selector("#matches", timeout=10000)

                table = page.query_selector("#matches")

                header_elements = table.query_selector_all("th")
                headers = []

                for header in header_elements:
                    text = header.inner_text().strip()
                    if not text:
                        headers.append("Opponent")
                    else:
                        headers.append(text)

                headers = [header.inner_text().strip() for header in header_elements]
                rows = table.query_selector("tbody").query_selector_all("tr")
                total_data = []
                for row in rows:
                    cell_data = row.query_selector_all("td")
                    cell_text = []
                    for i, cell in enumerate(cell_data):
                        cell_text.append(cell.inner_text())
                    cell_dict = dict(zip(headers, cell_text))
                    cell_dict['Player'] = player.name
                    total_data.append(cell_dict)
                return total_data
            except Exception as e:
                print(f"Error in return results: {e}")
                return []

        return self._with_page(url, parse_return_page)

    def _with_page(self, url, fn):
        """Helper function to manage Playwright browser context"""
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

    @staticmethod
    def pctg_to_dec(pctg):
        return float(pctg.replace("%", "")) / 100

    @staticmethod
    def parse_date(date_str):
        clean_date = re.sub(r"[\u2010-\u2015\u2212\uFE58\uFE63\uFF0D]", "-", date_str.strip())
        parsed_date = datetime.strptime(clean_date, "%d-%b-%Y").date()
        return parsed_date

    @staticmethod
    def player_match_defaults(row, opponent):
        return {
            'completed': row['Completed'],
            'surface': row['Surface'],
            'rank': row['Rk'],
            'opponent_rank': row['vRk'],
            'opponent': opponent,
            'score': row['Score'],
            'won': row['Won']
        }

    def serve_stats_defaults(self, row):
        # Handle break points saved (format: "saved/faced")
        bp_saved, bp_faced = None, None
        if row.get('BPSvd'):
            bp_parts = (row.get('BPSvd') or '').split('/')
            if len(bp_parts) == 2:
                bp_saved = int(bp_parts[0])
                bp_faced = int(bp_parts[1])

        return {
            'dominance_ratio': row['DR'],
            'ace_pctg': self.pctg_to_dec(row['A%']),
            'df_pctg': self.pctg_to_dec(row['DF%']),
            'fs_pctg': self.pctg_to_dec(row['1stIn']),
            'fs_w_pctg': self.pctg_to_dec(row['1st%']),
            'ss_w_pctg': self.pctg_to_dec(row['2nd%']),
            'bp_saved': bp_saved,
            'bp_faced': bp_faced,
            'time': row['Time']
        }

    def return_stats_defaults(self, row):
        bp_conv, bp_chances = None, None
        if row.get('BPCnv'):
            bp_parts = (row.get('BPCnv') or '').split('/')
            if len(bp_parts) == 2:
                bp_conv = int(bp_parts[0])
                bp_chances = int(bp_parts[1])
        return {
            'dominance_ratio': row['DR'],
            'total_p_w': self.pctg_to_dec(row['TPW']),
            'return_p_w': self.pctg_to_dec(row['RPW']),
            'v_ace_pctg': self.pctg_to_dec(row['vA%']),
            'v_fs_pctg': self.pctg_to_dec(row['v1st%']),
            'v_ss_pctg': self.pctg_to_dec(row['v2nd%']),
            'bp_conv': bp_conv,
            'bp_chances': bp_chances,
            'time': row['Time']
        }