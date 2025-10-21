from datetime import datetime
from pprint import pprint

from django.core.management import BaseCommand
from django.db import transaction
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

from tennis.models import Player, PlayerMatch, Tournament


class Command(BaseCommand):
    help = "Import players recent matches"

    def handle(self, *args, **options):

        players = Player.objects.filter(ranking__gt=30)
        self.stdout.write(f"Found {len(players)} players")
        for player in players:
            try:
                self.stdout.write(f"Importing recent matches for {player.name}")
                self.stdout.write(f"Ranking: {player.ranking}")
                recent_results = self.get_recent_results(player)
                for row in recent_results:
                    with transaction.atomic():
                        try:
                            tournament, tournament_created = Tournament.objects.get_or_create(name=row['Tournament'], year=row['Date'][-4:])
                            tournament_action = 'created' if tournament_created else 'update'

                            self.stdout.write(
                                self.style.SUCCESS(f'{tournament_action} {tournament.name}')
                            )

                            opponent, opponent_created = Player.objects.get_or_create(name=row['Opponent'])
                            opponent_action = 'created' if opponent_created else 'update'

                            self.stdout.write(
                                self.style.SUCCESS(f'{opponent_action} {opponent.name}')
                            )

                            match, match_created = PlayerMatch.objects.update_or_create(
                                player=player,
                                opponent=opponent,
                                tournament = tournament,
                                defaults={
                                'date': datetime.strptime(row['Date'], "%d-%b-%Y").date(),
                                'surface': row['Surface'],
                                'round': row['Rd'],
                                'rank': row['Rk'],
                                'opponent_rank': row['vRk'],
                                'opponent': opponent,
                                'score': row['Score'],
                                'won': row['Won']
                            })

                            match_action = 'created' if match else 'update'

                            self.stdout.write(
                                self.style.SUCCESS(f'{match_action} {match.player.name} v {match.opponent.name} at {match.tournament.name}')
                            )
                        except Exception as e:
                            self.stdout.write(
                                self.style.ERROR(f'Error {e}')
                            )
            except Exception as e:
                self.stdout.write

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
