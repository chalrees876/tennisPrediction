from datetime import datetime
from pprint import pprint

from django.core.management import BaseCommand
from django.db import transaction
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

from tennis.management.commands.TempScripts import pctg_to_dec
from tennis.models import Player, PlayerMatch, Tournament, PlayerServeStats


class Command(BaseCommand):
    help = "Import player stats from tennisabstract.com"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Dry run, print what would be updated without saving to db.'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        self.stdout.write("Starting serve stats data scraping...")
        serve_stats = self.player_serve_stats()
        self.stdout.write(f"Scraped {len(serve_stats)} players' stats...")


    def update_serve_stats(self, serve_stats):
        success_count = 0
        error_count = 0

        for row in serve_stats:
            try:
                player = Player.objects.get(name=row['Player'].strip().title())
                with transaction.atomic():
                    try:

                        player_serve, created = PlayerServeStats.objects.update_or_create(
                            player = player,
                            defaults={
                                'matches': int(row['M']),
                                'matches_w_pctg': pctg_to_dec(['M W%']),
                                'service_p_w_pctg': pctg_to_dec(row['hElo']),
                                'aces': int(row['Aces']),
                                'aces_pctg': pctg_to_dec(row['Ace%']),
                                'dfs': int(row['DFs']),
                                'df_pctg': pctg_to_dec(row['DF%']),
                                'df_per_2nd': pctg_to_dec(row['DF/2s']),
                                'fs_pctg': pctg_to_dec(row['1stIn']),
                                'fs_w_pctg': pctg_to_dec(row['1st%']),
                                'ss_w_pctg': pctg_to_dec(row['2nd%']),
                                'ss_w_pctg_less_df': pctg_to_dec(row['2%-InP']),
                                'hold_pctg': pctg_to_dec(row['Hld%']),
                                'pts_per_sg': float(row['Pts/SG']),
                                'pts_l_per_sg': float(row['PtsL/SG']),
                            })
                        elo_action = 'created' if created else 'updated'
                        self.stdout.write(
                            self.style.SUCCESS(f"{elo_action} {player.name}")
                        )
                        success_count += 1
                    except Exception as e:
                        if player:
                            self.stdout.write(
                                self.style.ERROR(f"{e} for {row['Player']}")
                            )
                        else:
                            self.stdout.write(
                                self.style.ERROR(f"{e}, player not found")
                            )

                        error_count += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"{e}"))

            self.stdout.write(f"Summary\n{success_count} successes\n{error_count} errors")

    def player_serve_stats(self):
        def get_recent_results(self, player):
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
                driver.get(f"https://www.tennisabstract.com/cgi-bin/player.cgi?p={player.name.replace(' ', '')}")

                table = driver.find_element(By.ID, "recent-results")
                print(table)

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
                            # The current player (whose page we're on) is in <b> tag
                            current_player_element = cell.find_element(By.TAG_NAME, "b")
                            current_player = current_player_element.text.strip()

                            # The opponent is in <a> tag
                            opponent_link = cell.find_element(By.TAG_NAME, "a")
                            opponent = opponent_link.text.strip()

                            # Get full text to determine who won
                            full_text = cell.text

                            # Check if current player is the winner (appears before "d." in the text)
                            if full_text.find(current_player) < full_text.find(" d. "):
                                # Current player is the winner
                                won = True
                            else:
                                won = False
                            cell_text.append(opponent)
                        elif i == 15:
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

    def pctg_to_dec(self, pctg):
        return float(pctg.replace("%", "")) / 100
