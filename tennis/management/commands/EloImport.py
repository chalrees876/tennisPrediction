from pprint import pprint

from django.core.management.base import BaseCommand
from django.db import transaction
import math

from selenium import webdriver
from selenium.common import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from tennis.models import Player, PlayerElo

class Command(BaseCommand):
    help = "Import elo data from tennisabstract.com"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Dry run, print what would be updated without saving to db.'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        self.stdout.write("Starting elo data scraping...")
        elo_data = self.get_men_elo_data()
        self.stdout.write(f"Scraped {len(elo_data)} players...")

        success_count = 0
        error_count = 0

        for row in elo_data:

            if dry_run:
                self.stdout.write(f"Would process {row['Player']}")
                continue

            with transaction.atomic():
                try:

                    player, created = Player.objects.get_or_create(name=row['Player'].title(), defaults={
                        'ranking': int(row['ATP Rank']),
                        'age': math.ceil(float(row['Age']))
                    })
                    if player.ranking is not None and player.ranking != int(row['ATP Rank']):
                        player.ranking = int(row['ATP Rank'])
                        player.save(update_fields=['ranking'])
                    if player.age is not None and player.age != math.floor(float(row['Age'])):
                        player.age = math.ceil(float(row['Age']))
                        player.save(update_fields=['age'])
                    player_action = 'created' if created else 'update'
                    self.stdout.write(
                        self.style.SUCCESS(f"{player_action} {player}")
                    )
                    player_elo, created = PlayerElo.objects.update_or_create(player=player,
                        defaults={
                            'elo': float(row['Elo']),
                            'elo_ranking': float(row['Elo Rank']),
                            'h_elo': float(row['hElo']),
                            'h_elo_ranking': int(row['hElo Rank']),
                            'c_elo': float(row['cElo']),
                            'c_elo_ranking': int(row['cElo Rank']),
                            'g_elo': float(row['gElo']),
                            'g_elo_ranking': int(row['gElo Rank']),
                            'peak_elo': float(row['Peak Elo']),
                        })
                    elo_action = 'created' if created else 'updated'
                    self.stdout.write(
                        self.style.SUCCESS(f"{elo_action} {player.name} ranking: {player.ranking}")
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

            self.stdout.write(f"Summary\n{success_count} successes\n{error_count} errors")

    def get_men_elo_data(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_experimental_option("prefs", {
            "profile.managed_default_content_settings.images": 2,
        })
        chrome_options.add_argument(
            "user-agent=TennisBetSmartBot/1.0 (+https://tennisbetsmart.com; contact: chris.mcke876@gmail.com)"
        )

        try:
            driver = webdriver.Chrome(options=chrome_options)
        except WebDriverException as e:
            self.stderr.write(f"[EloImport] Failed to start Chrome: {e}")
            return []

        try:
            driver.get("https://tennisabstract.com/reports/atp_elo_ratings.html")

            self.stdout.write(f"[EloImport] Loaded URL: {driver.current_url}")
            self.stdout.write(f"[EloImport] Page title: {driver.title!r}")

            wait = WebDriverWait(driver, 20)

            try:
                ranking_element = wait.until(
                    EC.presence_of_element_located((By.ID, "reportable"))
                )
            except TimeoutException:
                self.stderr.write("[EloImport] Timed out waiting for #reportable")
                snippet = driver.page_source[:700].replace("\n", " ")
                self.stderr.write(f"[EloImport] Page snippet: {snippet}")
                return []

            header_data = ranking_element.find_elements(By.TAG_NAME, "th")
            headers = [h.text for h in header_data if h.text.strip()]

            rows = ranking_element.find_element(By.TAG_NAME, "tbody").find_elements(By.TAG_NAME, "tr")
            total_data = []
            for row in rows:
                cell_data = row.find_elements(By.TAG_NAME, "td")
                cells = [cell.text for cell in cell_data if cell.text.strip()]
                row_dict = dict(zip(headers, cells))
                total_data.append(row_dict)

            return total_data

        except WebDriverException as e:
            self.stderr.write(f"[EloImport] WebDriverException while loading page: {e}")
            return []

        finally:
            driver.quit()
