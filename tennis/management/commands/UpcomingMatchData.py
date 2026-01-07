import re
from datetime import datetime
from pprint import pprint
import time

from django.core.management import BaseCommand
from django.db import transaction
from django.db.models import Q
from playwright.sync_api import sync_playwright

from tennis.ml.feature_engineering import TennisFeatureEngineer
from tennis.models import MatchFeatures, Player, PlayerMatch, Tournament


class Command(BaseCommand):

    def handle(self, *args, **options):

        tournaments = self.get_tournament_urls()
        
        for tournament in tournaments:
            time.sleep(5)
            url = tournament['url']
            name = tournament['name']
            upcoming_matches = self.parse_tournament(url)
            
            for match in upcoming_matches:
                player_obj1 = Player.objects.filter(name__iexact=match['player1']).first()
                player_obj2 = Player.objects.filter(name__iexact=match['player2']).first()
                
                if not player_obj1 or not player_obj2:
                    self.stdout.write(
                        self.style.ERROR(f"Player not found: {match['player1']} or {match['player2']}")
                    )
                    continue
                
                tournament_obj, created = Tournament.objects.get_or_create(
                    name=name, 
                    year=datetime.now().year
                )
                
                try:
                    # Try to find existing match (any date)
                    existing_match1 = PlayerMatch.objects.filter(
                        player=player_obj1,
                        opponent=player_obj2,
                        round=match['round'],
                        tournament=tournament_obj,
                        completed=False
                    ).first()
                    
                    if existing_match1:
                        self.make_match_features(existing_match1)
                    else:
                        # Create new
                        pm_obj1 = PlayerMatch.objects.create(
                            player=player_obj1,
                            opponent=player_obj2,
                            round=match['round'],
                            tournament=tournament_obj,
                            date=None,
                            completed=False,
                            surface="Not Specified",
                            rank=player_obj1.ranking,
                            opponent_rank=player_obj2.ranking,
                            score="N/A",
                            won=None
                        )
                        self.stdout.write(
                            self.style.SUCCESS(f"Created match: {player_obj1.name} vs {player_obj2.name}")
                        )
                        self.make_match_features(pm_obj1)

                    # Same for reverse match
                    existing_match2 = PlayerMatch.objects.filter(
                        player=player_obj2,
                        opponent=player_obj1,
                        round=match['round'],
                        tournament=tournament_obj,
                        completed=False
                    ).first()
                    
                    if existing_match2:
                        self.stdout.write(
                            self.style.WARNING(f"Match already exists: {player_obj2.name} vs {player_obj1.name}")
                        )
                        self.make_match_features(existing_match2)
                    else:
                        pm_obj2 = PlayerMatch.objects.create(
                            player=player_obj2,
                            opponent=player_obj1,
                            round=match['round'],
                            tournament=tournament_obj,
                            date=None,
                            completed=False,
                            surface="Not Specified",
                            rank=player_obj2.ranking,
                            opponent_rank=player_obj1.ranking,
                            score="N/A",
                            won=None
                        )
                        self.stdout.write(
                            self.style.SUCCESS(f"Created match: {player_obj2.name} vs {player_obj1.name}")
                        )
                        self.make_match_features(pm_obj2)
                        
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"Error creating match: {match['player1']} vs {match['player2']}: {e}")
                    )
                    continue
                    
                    

    def get_tournament_urls(self):
        url = "https://www.tennisabstract.com/cgi-bin/leaders.cgi"
        
        def parse_tournaments_page(page):
            try:
                page.goto(url, wait_until="domcontentloaded")
                page.wait_for_selector("#navbar", timeout=10000)
                
                # Find the Tournaments button and its parent dropdown div
                tournaments_button = page.query_selector("button.dropbtn:has-text('Tournaments')")
                parent_div = tournaments_button.evaluate_handle("el => el.parentElement")
                
                # Hover to reveal dropdown
                tournaments_button.hover()
                page.wait_for_timeout(500)
                
                # Get links within this specific dropdown
                links = parent_div.query_selector_all(".dropdown-content a")
                                
                tournament_urls = []
                for link in links:
                    href = link.get_attribute("href")
                    name = link.inner_text().strip()
                    if name.startswith("WTA"):
                        continue  # Skip WTA tournaments
                    if href:
                        tournament_urls.append({"name": name, "url": href})
                        
                return tournament_urls
            
            except Exception as e:
                print(f"Error getting tournament URLs: {e}")
                return []
        
        return self._with_page(url, parse_tournaments_page)
    
    def parse_tournament(self, tournament_url):
    
        def parse_upcoming_page(page):
            try:
                page.goto(tournament_url, wait_until="domcontentloaded")
                
                upcoming_span = page.query_selector("#upcoming")
                if not upcoming_span:
                    print("No upcoming matches found.")
                    return []
                
                # Get all player links within the upcoming section
                links = upcoming_span.query_selector_all("a")
                
                # Links come in pairs (player1, player2, h2h link, player1, player2, h2h link...)
                # Filter to only player links (exclude h2h links which contain "&f=ACareerqq")
                player_links = [link for link in links if "&f=ACareerqq" not in (link.get_attribute("href") or "")]

                inner_html = upcoming_span.inner_html()
                lines = inner_html.split("<br>")
                for line in lines:
                    if not line.strip() or line.strip() == "&nbsp;":
                        continue
                    # Extract round (text before first "<a")
                    round_match = re.match(r'^([^<]+)<a', line)
                    round_info = ""
                    if round_match:
                        # Clean up: "R2: (1)" -> "R2"
                        round_text = round_match.group(1).strip()
                        # Extract just the round part (e.g., "R2", "QF", "SF", "F")
                        round_clean = re.match(r'^(R\d+|QF|SF|F|RR)', round_text)
                        if round_clean:
                            round_info = round_clean.group(1)
                
                matches = []
                # Process in pairs
                for i in range(0, len(player_links) - 1, 2):
                    player1_name = player_links[i].inner_text().strip()
                    player2_name = player_links[i + 1].inner_text().strip()
                    matches.append({
                        "player1": player1_name,
                        "player2": player2_name,
                        "round": round_info
                    })
                    
                
                return matches
            except Exception as e:
                print(f"Error getting upcoming matches: {e}")
                return []
    
        return self._with_page(tournament_url, parse_upcoming_page)
    
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
                
    def make_match_features(self, match):
        if not MatchFeatures.objects.filter(match=match).exists():
            self.stdout.write(
                self.style.WARNING(f"match features don't exist for match {match.id}, creating...")
            )
            fe = TennisFeatureEngineer().create_match_features(match)
            if not fe:
                self.stdout.write(
                    self.style.ERROR(f"Could not create features for match {match.id}")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"Created features for match {match.id}")
                )
            return fe

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