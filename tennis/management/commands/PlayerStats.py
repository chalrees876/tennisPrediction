from datetime import datetime
from pprint import pprint
import time
from django.core.management import BaseCommand
from django.db import transaction
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from tennis.management.commands.CalculateOdds import pctg_to_dec
from tennis.models import Player, PlayerMatch, Tournament, PlayerServeStats, PlayerReturnStats, PlayerBreakStats, \
    PlayerMoreStats


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
       
       self.update_stats("Serve")
       time.sleep(5)  # Wait between stat types
       self.update_stats("Breaks")
       time.sleep(5)
       self.update_stats("More")
       time.sleep(5)
       self.update_stats("Return")


    def update_stats(self, type):

        if type == "Return":
            stats = self.player_stats("Return")
        elif type == "Serve":
            stats = self.player_stats("Serve")
        elif type == "Breaks":
            stats = self.player_stats("Breaks")
        elif type == "More":
            stats = self.player_stats("More")

        success_count = 0
        error_count = 0

        for row in stats:
            with transaction.atomic():
                try:
                    player = Player.objects.get(name=row['Player'].title())
                    if type == "Return":
                        player_stats, created = PlayerReturnStats.objects.get_or_create(player=player, defaults = self.return_defaults(row))
                    elif type == "Serve":
                        player_stats, created = PlayerServeStats.objects.get_or_create(player=player, defaults = self.serve_defaults(row))
                    elif type == "Breaks":
                        player_stats, created = PlayerBreakStats.objects.get_or_create(player=player, defaults=self.breaks_defaults(row))
                    elif type == "More":
                        player_stats, created = PlayerMoreStats.objects.get_or_create(player=player, defaults=self.more_defaults(row))
                    self.stdout.write(
                        self.style.SUCCESS(f"{type} {player.name}")
                    )
                    success_count += 1
                except Player.DoesNotExist:
                    self.stdout.write(
                        self.style.ERROR(f"player not found for row: {row['Player']}")
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"{e}")
                    )

                    error_count += 1

        self.stdout.write(f"Summary\n{success_count} successes\n{error_count} errors")

    def player_stats(self, stat_type):
        # Set up Chrome options
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-images")  # Block images for faster loading
        chrome_options.add_experimental_option("prefs", {
            "profile.managed_default_content_settings.images": 2,  # Disable images
        })
        chrome_options.add_argument("user-agent=TennisBetSmartBot/1.0 (+https://tennisbetsmart.com; contact: chris.mcke876@gmail.com)")


        # Initialize driver
        driver = webdriver.Chrome(options=chrome_options)
        try:
            driver.get("https://www.tennisabstract.com/cgi-bin/leaders.cgi")

            try:
                # Locate the span element by its text content using XPath
                span_element = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, f"//span[text()='{stat_type}']"))
                )
                span_element.click()
                print("Span element clicked successfully.")
            except Exception as e:
                print(f"Error clicking span element: {e}")

            self.stdout.write(f"Starting {stat_type} stats data scraping...")

            table = driver.find_element(By.ID, "matches")

            header_data = table.find_elements(By.TAG_NAME, "th")
            headers = [header.text for header in header_data]

            rows = table.find_element(By.TAG_NAME, "tbody").find_elements(By.TAG_NAME, "tr")
            total_data = []
            for row in rows:
                cell_data = row.find_elements(By.TAG_NAME, "td")
                cell_text = []
                for i, cell in enumerate(cell_data):
                    if i == 1:
                        cell_text.append(cell.find_element(By.TAG_NAME, "a").text)
                    else:
                        cell_text.append(cell.text)
                cell_dict = dict(zip(headers, cell_text))
                total_data.append(cell_dict)
            driver.close()
        except Exception as e:
            print(e)
        self.stdout.write(f"Scraped {len(total_data)} players' {stat_type} stats...")
        return total_data

    def pctg_to_dec(self, pctg):
        return float(pctg.replace("%", "")) / 100


    def serve_defaults(self, row):
        return {
                'matches': int(row['M']),
                'matches_w_pctg': pctg_to_dec(row['M W%']),
                'service_p_w_pctg': pctg_to_dec(row['SPW']),
                'service_p_in_w_pctg': pctg_to_dec(row['SPW-InP']),
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
            }

    def return_defaults(self, row):
        return {
                'matches': int(row['M']),
                'return_p_w_pctg': pctg_to_dec(row['RPW']),
                'return_p_in_w_pctg': pctg_to_dec(row['RPW-InP']),
                'ace_pctg_against': pctg_to_dec(row['vAce%']),
                'df_pctg_against': pctg_to_dec(row['vDF%']),
                'fs_r_p_w_pctg': pctg_to_dec(row['v1st%']),
                'ss_r_p_w_pctg': pctg_to_dec(row['v2nd%']),
                'break_pctg': pctg_to_dec(row['Brk%']),
                'pts_per_rg': pctg_to_dec(row['Pts/RG']),
                'pts_w_per_rg': pctg_to_dec(row['PtsW/RG']),
                'med_opp_ranking': pctg_to_dec(row['MdOppRk']),
                'mean_opp_ranking': pctg_to_dec(row['MnOppRk']),
            }

    def breaks_defaults(self, row):
        return {
                'matches': int(row['M']),
                'break_p_conv_pctg': pctg_to_dec(row['BPConv%']),
                'bp_conv': int(row['BPConv']),
                'bp_chances': int(row['BPChnc']),
                'bp_per_g': float(row['BP/G']),
                'bp_per_s': float(row['BP/S']),
                'bp_per_m': float(row['BP/M']),
                'break_per_s': float(row['Bks/S']),
                'break_per_m': float(row['Bks/M']),
                'bp_saved_pctg': pctg_to_dec(row['BPSvd%']),
                'bp_saved': int(row['BPSaved']),
                'bp_faced': int(row['BPvs']),
                'bp_faced_per_g': float(row['BPvs/G']),
                'bp_faced_per_s': float(row['BPvs/S']),
                'bp_faced_per_m': float(row['BPvs/M']),
                'sg_l_per_s': float(row['Bkn/S']),
                'sg_l_per_m': float(row['Bkn/M']),
            }

    def more_defaults(self, row):
        return {
            'matches': int(row['M']),
            'dominance_ratio': float(row['DR']),
            'points': int(row['Points']),
            'p_w_pctg': pctg_to_dec(row['TPW%']),
            'tbs': int(row['TBs']),
            'tb_wl': row['TB W-L'],
            'tb_w_pctg': pctg_to_dec(row['TB W%']),
            'tb_per_s': pctg_to_dec(row['TB/S']),
            'sets': int(row['Sets']),
            'set_wl': row['Set W-L'],
            'set_w_pctg': pctg_to_dec(row['S W%']),
            'games': int(row['Gms']),
            'game_wl': (row['Game W-L']),
            'game_w_pctg': pctg_to_dec(row['G W%']),
            'time_per_match': row['Time/Mt'],
            'min_per_s': float(row['Min/Set']),
            'sec_per_p': float(row['Sec/Pt']),
        }



