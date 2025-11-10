import re
from datetime import datetime
from django.core.management import BaseCommand
from django.db import transaction
from django.db.models import Q
from playwright.sync_api import sync_playwright

from tennis.models import Player, PlayerMatch, Tournament, PlayerMatchServeStats, PlayerMatchReturnStats


class Command(BaseCommand):
    help = "Import players recent matches efficiently"
    """
    Efficient import using single browser instance and batched database operations
    """

    def add_arguments(self, parser):
        parser.add_argument("--min-rank", type=int, default=1)
        parser.add_argument("--max-rank", type=int, default=100)
        parser.add_argument("--batch-size", type=int, default=50, help="Number of database operations per batch")

    def handle(self, *args, **options):
        min_rank = options["min_rank"]
        max_rank = options["max_rank"]
        batch_size = options["batch_size"]

        players = Player.objects.filter(ranking__lte=max_rank, ranking__gt=min_rank)

        self.stdout.write(f"Processing {players.count()} players")

        # Use single browser instance for all operations
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=["--disable-dev-shm-usage", "--no-sandbox"]
            )
            context = browser.new_context(
                user_agent=("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
                viewport={"width": 1280, "height": 900},
                java_script_enabled=True,
            )
            context.set_default_timeout(30_000)

            try:
                # Process players sequentially but efficiently with single browser
                all_player_data = []

                for player in players:
                    self.stdout.write(f"Scraping data for {player.name}...")
                    player_data = self.process_single_player(player, context)
                    if player_data:
                        all_player_data.append(player_data)
                        self.stdout.write(
                            self.style.SUCCESS(f"✓ Scraped {len(player_data['matches'])} matches for {player.name}")
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING(f"⚠ No data for {player.name}")
                        )

                # Batch all database operations
                self.batch_save_all_data(all_player_data, batch_size)

            finally:
                context.close()
                browser.close()

    def process_single_player(self, player, context):
        """Process a single player and return all their match data"""
        try:
            # Create new page for this player (reusing same browser context)
            page = context.new_page()
            page.route("**/*",
                       lambda route: route.abort() if route.request.resource_type == "image" else route.continue_())

            try:
                serve_results = self.get_recent_serve_results(page, player)
                return_results = self.get_recent_return_results(page, player)

                # Merge serve and return data
                matches_data = self.merge_serve_return_data(serve_results, return_results, player)

                return {
                    'player_id': player.id,
                    'player_name': player.name,
                    'matches': matches_data
                }
            finally:
                page.close()

        except Exception as e:
            self.stdout.write(f"Error in process_single_player for {player.name}: {e}")
            return None

    def get_recent_serve_results(self, page, player):
        """Get serve results for a player"""
        url = f"https://www.tennisabstract.com/cgi-bin/player-classic.cgi?p={player.name.replace(' ', '')}"

        try:
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_selector("#matches", timeout=10000)

            table = page.query_selector("#matches")
            if not table:
                return []

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
                    if i == 6:  # Opponent column
                        opponent_link = cell.query_selector("a")
                        opponent = opponent_link.inner_text().strip() if opponent_link else cell.inner_text().strip()

                        full_text = cell.inner_text()
                        if " d. " in full_text:
                            if full_text.find(opponent) < full_text.find(" d. "):
                                won = False
                            else:
                                won = True
                        else:
                            won = None
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
            self.stdout.write(f"Error getting serve results for {player.name}: {e}")
            return []

    def get_recent_return_results(self, page, player):
        """Get return results for a player"""
        url = f"https://www.tennisabstract.com/cgi-bin/player-classic.cgi?p={player.name.replace(' ', '')}&f=r1"

        try:
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_selector("#matches", timeout=10000)

            table = page.query_selector("#matches")
            if not table:
                return []

            header_elements = table.query_selector_all("th")
            headers = [header.inner_text().strip() for header in header_elements]

            rows = table.query_selector("tbody").query_selector_all("tr")
            total_data = []
            for row in rows:
                cell_data = row.query_selector_all("td")
                cell_text = [cell.inner_text() for cell in cell_data]
                cell_dict = dict(zip(headers, cell_text))
                cell_dict['Player'] = player.name
                total_data.append(cell_dict)
            return total_data
        except Exception as e:
            self.stdout.write(f"Error getting return results for {player.name}: {e}")
            return []

    def merge_serve_return_data(self, serve_data, return_data, player):
        """Merge serve and return data by matching rows"""
        merged_data = []

        # Create lookup for return data
        return_lookup = {}
        for return_row in return_data:
            key = (
                return_row.get('Date', '').strip(),
                return_row.get('Tournament', '').strip(),
                return_row.get('Rd', '').strip(),
                return_row.get('Opponent', '').strip()
            )
            return_lookup[key] = return_row

        # Merge with serve data
        for serve_row in serve_data:
            key = (
                serve_row.get('Date', '').strip(),
                serve_row.get('Tournament', '').strip(),
                serve_row.get('Rd', '').strip(),
                serve_row.get('Opponent', '').strip()
            )

            return_row = return_lookup.get(key, {})
            merged_row = {**serve_row, **return_row}

            # Set completion status
            score = merged_row.get('Score', '')
            if score == 'Live Scores' or not score.strip():
                merged_row['Completed'] = False
                merged_row['Won'] = None
            else:
                merged_row['Completed'] = True

            merged_data.append(merged_row)

        return merged_data

    def batch_save_all_data(self, all_player_data, batch_size):
        """Batch save all data in efficient transactions"""
        if not all_player_data:
            self.stdout.write("No data to save")
            return

        # Collect all entities to create
        all_players = set()
        all_tournaments = set()
        all_matches = []

        # Pre-fetch existing entities
        existing_players = {p.name: p for p in Player.objects.all()}
        existing_tournaments = {
            (t.name, str(t.year)): t
            for t in Tournament.objects.all()
        }

        # Process all data
        for player_data in all_player_data:
            player_id = player_data['player_id']
            matches_data = player_data['matches']

            for row in matches_data:
                # Collect opponent
                opponent_name = row.get('Opponent', '').strip()
                if opponent_name and opponent_name not in existing_players:
                    all_players.add(opponent_name)

                # Collect tournament
                tournament_name = row.get('Tournament', '').strip()
                year = row.get('Date', '')[-4:]
                if tournament_name and year and (tournament_name, year) not in existing_tournaments:
                    all_tournaments.add((tournament_name, year))

                # Prepare match data
                match_date = self.parse_date(row.get('Date'))
                if not match_date:
                    continue

                all_matches.append({
                    'player_id': player_id,
                    'row': row,
                    'date': match_date,
                    'tournament_name': tournament_name,
                    'tournament_year': year,
                    'opponent_name': opponent_name
                })

        # Batch create missing players
        if all_players:
            new_players = [Player(name=name) for name in all_players]
            Player.objects.bulk_create(new_players, ignore_conflicts=True)
            self.stdout.write(f"Created {len(new_players)} new players")
            # Refresh existing players cache
            existing_players = {p.name: p for p in Player.objects.all()}

        # Batch create missing tournaments
        if all_tournaments:
            new_tournaments = [
                Tournament(name=name, year=year)
                for name, year in all_tournaments
            ]
            Tournament.objects.bulk_create(new_tournaments, ignore_conflicts=True)
            self.stdout.write(f"Created {len(new_tournaments)} new tournaments")
            # Refresh existing tournaments cache
            existing_tournaments = {
                (t.name, str(t.year)): t
                for t in Tournament.objects.all()
            }

        # Batch create/update matches
        match_objects = []
        for match_data in all_matches:
            player_id = match_data['player_id']
            row = match_data['row']
            opponent = existing_players.get(match_data['opponent_name'])
            tournament = existing_tournaments.get((match_data['tournament_name'], match_data['tournament_year']))

            if not opponent or not tournament:
                continue

            match_objects.append(PlayerMatch(
                player_id=player_id,
                opponent=opponent,
                tournament=tournament,
                date=match_data['date'],
                round=row.get('Rd'),
                completed=row.get('Completed', False),
                surface=row.get('Surface'),
                rank=row.get('Rk'),
                opponent_rank=row.get('vRk'),
                score=row.get('Score'),
                won=row.get('Won')
            ))

        # Batch upsert matches
        if match_objects:
            with transaction.atomic():
                PlayerMatch.objects.bulk_create(
                    match_objects,
                    update_conflicts=True,
                    update_fields=[
                        'completed', 'surface', 'rank', 'opponent_rank',
                        'score', 'won'
                    ],
                    unique_fields=['player', 'opponent', 'tournament', 'date', 'round']
                )
            self.stdout.write(f"Upserted {len(match_objects)} matches")

        # Now handle stats - we need to fetch the created matches and update stats
        self.batch_update_stats(all_matches, existing_players, existing_tournaments)

    def batch_update_stats(self, all_matches, existing_players, existing_tournaments):
        """Batch update serve and return stats"""
        updated_matches = 0

        # Build query to fetch all matches we just created/updated
        match_filters = Q()
        for match_data in all_matches:
            player_id = match_data['player_id']
            opponent = existing_players.get(match_data['opponent_name'])
            tournament = existing_tournaments.get((match_data['tournament_name'], match_data['tournament_year']))

            if opponent and tournament:
                match_filters |= Q(
                    player_id=player_id,
                    opponent=opponent,
                    tournament=tournament,
                    date=match_data['date'],
                    round=match_data['row'].get('Rd')
                )

        if not match_filters:
            return

        # Fetch all matches at once
        matches = PlayerMatch.objects.filter(match_filters).select_related('player', 'opponent', 'tournament')
        match_dict = {}
        for match in matches:
            key = (match.player_id, match.opponent_id, match.tournament_id, match.date, match.round)
            match_dict[key] = match

        # Update stats for each match
        serve_stats_to_create = []
        return_stats_to_create = []

        for match_data in all_matches:
            player_id = match_data['player_id']
            row = match_data['row']
            opponent = existing_players.get(match_data['opponent_name'])
            tournament = existing_tournaments.get((match_data['tournament_name'], match_data['tournament_year']))

            if not opponent or not tournament:
                continue

            key = (player_id, opponent.id, tournament.id, match_data['date'], row.get('Rd'))
            match = match_dict.get(key)

            if not match:
                continue

            # Prepare serve stats
            serve_stats_to_create.append(PlayerMatchServeStats(
                match=match,
                **self.serve_stats_defaults(row)
            ))

            # Prepare return stats
            return_stats_to_create.append(PlayerMatchReturnStats(
                match=match,
                **self.return_stats_defaults(row)
            ))

            updated_matches += 1

        # Bulk create/update stats
        if serve_stats_to_create:
            PlayerMatchServeStats.objects.bulk_create(
                serve_stats_to_create,
                update_conflicts=True,
                update_fields=[
                    'dominance_ratio', 'ace_pctg', 'df_pctg', 'fs_pctg',
                    'fs_w_pctg', 'ss_w_pctg', 'bp_saved', 'bp_faced', 'time'
                ],
                unique_fields=['match']
            )

        if return_stats_to_create:
            PlayerMatchReturnStats.objects.bulk_create(
                return_stats_to_create,
                update_conflicts=True,
                update_fields=[
                    'dominance_ratio', 'total_p_w', 'return_p_w', 'v_ace_pctg',
                    'v_fs_pctg', 'v_ss_pctg', 'bp_conv', 'bp_chances', 'time'
                ],
                unique_fields=['match']
            )

        self.stdout.write(f"Updated stats for {updated_matches} matches")

    @staticmethod
    def pctg_to_dec(pctg):
        if not pctg or pctg.strip() == '' or pctg.strip() == '-':
            return None
        try:
            return float(pctg.replace("%", "")) / 100
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def parse_date(date_str):
        if not date_str:
            return None
        try:
            clean_date = re.sub(r"[\u2010-\u2015\u2212\uFE58\uFE63\uFF0D]", "-", date_str.strip())
            parsed_date = datetime.strptime(clean_date, "%d-%b-%Y").date()
            return parsed_date
        except (ValueError, AttributeError):
            return None

    def serve_stats_defaults(self, row):
        bp_saved, bp_faced = None, None
        if row.get('BPSvd'):
            bp_parts = (row.get('BPSvd') or '').split('/')
            if len(bp_parts) == 2:
                try:
                    bp_saved = int(bp_parts[0])
                    bp_faced = int(bp_parts[1])
                except (ValueError, TypeError):
                    pass

        return {
            'dominance_ratio': row.get('DR'),
            'ace_pctg': self.pctg_to_dec(row.get('A%')),
            'df_pctg': self.pctg_to_dec(row.get('DF%')),
            'fs_pctg': self.pctg_to_dec(row.get('1stIn')),
            'fs_w_pctg': self.pctg_to_dec(row.get('1st%')),
            'ss_w_pctg': self.pctg_to_dec(row.get('2nd%')),
            'bp_saved': bp_saved,
            'bp_faced': bp_faced,
            'time': row.get('Time')
        }

    def return_stats_defaults(self, row):
        bp_conv, bp_chances = None, None
        if row.get('BPCnv'):
            bp_parts = (row.get('BPCnv') or '').split('/')
            if len(bp_parts) == 2:
                try:
                    bp_conv = int(bp_parts[0])
                    bp_chances = int(bp_parts[1])
                except (ValueError, TypeError):
                    pass

        return {
            'dominance_ratio': row.get('DR'),
            'total_p_w': self.pctg_to_dec(row.get('TPW')),
            'return_p_w': self.pctg_to_dec(row.get('RPW')),
            'v_ace_pctg': self.pctg_to_dec(row.get('vA%')),
            'v_fs_pctg': self.pctg_to_dec(row.get('v1st%')),
            'v_ss_pctg': self.pctg_to_dec(row.get('v2nd%')),
            'bp_conv': bp_conv,
            'bp_chances': bp_chances,
            'time': row.get('Time')
        }