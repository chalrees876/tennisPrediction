# tennis/management/commands/import_recent_fastest.py
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.core.management import BaseCommand
from django.db.models import Q

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup  # pip install beautifulsoup4
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from tennis.models import (
    Player,
    PlayerMatch,
    Tournament,
    PlayerMatchServeStats,
    PlayerMatchReturnStats,
)

# ---------- helpers ----------
def pctg_to_dec(p):
    if not p:
        return None
    p = p.strip()
    if not p.endswith("%"):
        return None
    try:
        return float(p[:-1]) / 100.0
    except Exception:
        return None

def parse_date(date_str):
    clean = re.sub(r"[\u2010-\u2015\u2212\uFE58\uFE63\uFF0D]", "-", date_str.strip())
    return datetime.strptime(clean, "%d-%b-%Y").date()

def parse_serve_table_html(html, player_name):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#matches")
    if not table:
        return []

    headers = []
    for th in table.select("thead th"):
        txt = (th.get_text(strip=True) or "")
        headers.append("Opponent" if txt == "" else txt)
    headers.append("Won")

    rows_out = []
    for tr in table.select("tbody tr"):
        tds = tr.find_all("td")
        if not tds:
            continue
        cells, won = [], None
        for i, td in enumerate(tds):
            txt = td.get_text(strip=True)
            if i == 6:
                a = td.find("a")
                opponent = (a.get_text(strip=True) if a else txt)
                full_text = td.get_text()
                # same "Won" logic you had
                won = not (full_text.find(opponent) < full_text.find("d."))
                cells.append(opponent)
            elif i == 16:
                cells.append(txt)     # Time
                cells.append(won)     # Won
            else:
                cells.append(txt)

        row = dict(zip(headers, cells))
        row["Player"] = player_name
        score = (row.get("Score") or "").strip()
        if score == "Live Scores" or not score:
            row["Completed"] = False
            row["Won"] = None
        else:
            row["Completed"] = True
        rows_out.append(row)
    return rows_out

def parse_return_table_html(html, player_name):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#matches")
    if not table:
        return []
    headers = [(th.get_text(strip=True) or "") for th in table.select("thead th")]
    rows_out = []
    for tr in table.select("tbody tr"):
        vals = [td.get_text(strip=True) for td in tr.find_all("td")]
        row = dict(zip(headers, vals))
        row["Player"] = player_name
        rows_out.append(row)
    return rows_out

def merge_serve_return(serve_rows, return_rows):
    return [{**s, **r} for s, r in zip(serve_rows, return_rows)]


# ---------- command ----------
class Command(BaseCommand):
    help = "Fast import with --dry-run: reuse one HTTP client, small-parallel fetch, then batched upserts. Opponent/Won/Completed logic unchanged."

    def add_arguments(self, parser):
        parser.add_argument("--min-rank", type=int, default=1)
        parser.add_argument("--max-rank", type=int, default=200)
        parser.add_argument("--workers", type=int, default=4, help="Parallel fetchers (3–6 is safe)")
        parser.add_argument("--limit-players", type=int, default=None)
        parser.add_argument("--dry-run", action="store_true", help="Do not write to DB; print what would change")
        parser.add_argument("--sample", type=int, default=3, help="Rows to print per player in dry-run")

    def handle(self, *args, **opts):
        min_r, max_r = opts["min_rank"], opts["max_rank"]
        workers = opts["workers"]
        limit_players = opts["limit_players"]
        dry_run = opts["dry_run"]
        sample_n = opts["sample"]

        players = list(
            Player.objects.filter(ranking__gte=min_r, ranking__lte=max_r, ranking__gt=0)
            .only("id", "name", "ranking")
            .order_by("ranking")
        )
        if limit_players:
            players = players[:limit_players]
        if not players:
            self.stdout.write(self.style.WARNING("No players in range."))
            return

        self.stdout.write(f"Fetching {len(players)} players with {workers} workers...")

        # --- network phase (parallel) ---
        results_by_player = {}
        def fetch_one(player):
            ua = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

            # thread-local session with retries
            s = requests.Session()
            retries = Retry(
                total=3,
                backoff_factor=0.5,
                status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods=frozenset(["GET"]),
                raise_on_status=False,
            )
            s.headers.update({"User-Agent": ua})
            s.mount("https://", HTTPAdapter(max_retries=retries))
            s.mount("http://", HTTPAdapter(max_retries=retries))

            base = f"https://www.tennisabstract.com/cgi-bin/player-classic.cgi?p={player.name.replace(' ', '')}"

            r1 = s.get(base, timeout=30)
            r1.raise_for_status()
            serve_rows = parse_serve_table_html(r1.text, player.name)

            r2 = s.get(base + "&f=r1", timeout=30)
            r2.raise_for_status()
            return_rows = parse_return_table_html(r2.text, player.name)

            merged = merge_serve_return(serve_rows, return_rows)
            return (player, merged)

        results_by_player = {}
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(fetch_one, p) for p in players]
            for fut in as_completed(futures):
                player, rows = fut.result()
                results_by_player[player] = rows

        # --- DB phase (single-threaded) ---
        players_by_name = {p.name: p for p in Player.objects.all().only("id", "name")}

        for player in players:
            rows = results_by_player.get(player, [])
            if not rows:
                self.stdout.write(self.style.WARNING(f"{player.name}: 0 rows scraped"))
                continue

            # collect required entities
            opponent_names = set()
            tour_keys = set()  # (name, year)
            for row in rows:
                opp = " ".join((row.get("Opponent") or "").split()).strip()
                if opp:
                    opponent_names.add(opp)
                year = (row.get("Date") or "")[-4:]
                tour_name = " ".join((row.get("Tournament") or "").split()).strip()
                if tour_name and year:
                    tour_keys.add((tour_name, year))

            missing_opps = [n for n in opponent_names if n not in players_by_name]

            existing_tours = {
                (t.name, str(t.year)): t
                for t in Tournament.objects.filter(
                    name__in=[n for n, _ in tour_keys],
                    year__in=[y for _, y in tour_keys]
                ).only("id", "name", "year")
            }
            missing_tours = [(name, year) for (name, year) in tour_keys if (name, year) not in existing_tours]

            # Build match objects (for preview/upsert)
            match_objs = []
            natural_key_to_row = {}
            for row in rows:
                opp_name = " ".join((row.get("Opponent") or "").split()).strip()
                if not opp_name:
                    continue
                year = (row.get("Date") or "")[-4:]
                t_name = " ".join((row.get("Tournament") or "").split()).strip()
                if not t_name or not year:
                    continue

                match_date = parse_date(row["Date"])
                match_round = row.get("Rd")

                # For dry-run preview, we don't need DB IDs — show natural key
                match_objs.append({
                    "player": player.name,
                    "opponent": opp_name,
                    "tournament": t_name,
                    "year": year,
                    "date": match_date.isoformat(),
                    "round": match_round,
                    "completed": row.get("Completed", False),
                    "surface": row.get("Surface"),
                    "rank": row.get("Rk"),
                    "opponent_rank": row.get("vRk"),
                    "score": row.get("Score"),
                    "won": row.get("Won"),
                })
                natural_key_to_row[(player.name, opp_name, t_name, year, match_date, match_round)] = row

            # --------- DRY RUN OUTPUT ---------
            if dry_run:
                self.stdout.write(self.style.NOTICE(f"\n=== DRY RUN: {player.name} (rank {player.ranking}) ==="))
                self.stdout.write(f"Scraped rows: {len(rows)}")
                if missing_opps:
                    self.stdout.write(self.style.WARNING(f"Would create opponents: {len(missing_opps)}"))
                    self.stdout.write(f"  e.g. {missing_opps[:min(5, len(missing_opps))]}")
                if missing_tours:
                    self.stdout.write(self.style.WARNING(f"Would create tournaments: {len(missing_tours)}"))
                    self.stdout.write(f"  e.g. {missing_tours[:min(5, len(missing_tours))]}")

                self.stdout.write(self.style.SUCCESS(f"Would upsert matches: {len(match_objs)}"))
                # samples
                for i, m in enumerate(match_objs[:sample_n], 1):
                    self.stdout.write(
                        f"  [{i}] {m['player']} vs {m['opponent']} | {m['tournament']} {m['year']} "
                        f"| {m['date']} {m['round']} | completed={m['completed']} won={m['won']} score={m['score']}"
                    )

                # show a sample of computed stats payloads (serve/return)
                shown = 0
                for key, row in natural_key_to_row.items():
                    if shown >= sample_n:
                        break
                    # serve stats preview
                    bp_saved = bp_faced = None
                    if row.get("BPSvd"):
                        parts = (row["BPSvd"] or "").split("/")
                        if len(parts) == 2:
                            try:
                                bp_saved, bp_faced = int(parts[0]), int(parts[1])
                            except Exception:
                                pass
                    # return stats preview
                    bp_conv = bp_chances = None
                    if row.get("BPCnv"):
                        parts = (row["BPCnv"] or "").split("/")
                        if len(parts) == 2:
                            try:
                                bp_conv, bp_chances = int(parts[0]), int(parts[1])
                            except Exception:
                                pass

                    self.stdout.write(
                        f"    serve_stats -> DR={row.get('DR')} A%={pctg_to_dec(row.get('A%'))} "
                        f"DF%={pctg_to_dec(row.get('DF%'))} 1stIn={pctg_to_dec(row.get('1stIn'))} "
                        f"1st%={pctg_to_dec(row.get('1st%'))} 2nd%={pctg_to_dec(row.get('2nd%'))} "
                        f"BPSvd={bp_saved}/{bp_faced} Time={row.get('Time')}"
                    )
                    self.stdout.write(
                        f"    return_stats -> DR={row.get('DR')} TPW={pctg_to_dec(row.get('TPW'))} "
                        f"RPW={pctg_to_dec(row.get('RPW'))} vA%={pctg_to_dec(row.get('vA%'))} "
                        f"v1st%={pctg_to_dec(row.get('v1st%'))} v2nd%={pctg_to_dec(row.get('v2nd%'))} "
                        f"BPCnv={bp_conv}/{bp_chances} Time={row.get('Time')}"
                    )
                    shown += 1
                continue  # skip DB writes entirely

            # --------- REAL WRITES (same as before) ---------
            # Opponents
            if missing_opps:
                Player.objects.bulk_create(
                    [Player(name=n) for n in missing_opps],
                    ignore_conflicts=True,
                    batch_size=500,
                )
                for pnew in Player.objects.filter(name__in=missing_opps).only("id", "name"):
                    players_by_name[pnew.name] = pnew

            # Tournaments
            to_create = [
                Tournament(name=name, year=year)
                for (name, year) in missing_tours
            ]
            if to_create:
                Tournament.objects.bulk_create(to_create, ignore_conflicts=True, batch_size=500)
                for t in Tournament.objects.filter(
                    name__in=[n for n, _ in tour_keys],
                    year__in=[y for _, y in tour_keys]
                ).only("id", "name", "year"):
                    existing_tours[(t.name, str(t.year))] = t

            # Build concrete ORM objects with IDs
            match_models = []
            for row in rows:
                opp_name = " ".join((row.get("Opponent") or "").split()).strip()
                opponent = players_by_name.get(opp_name)
                if not opponent:
                    continue
                year = (row.get("Date") or "")[-4:]
                t_name = " ".join((row.get("Tournament") or "").split()).strip()
                tournament = existing_tours.get((t_name, year))
                if not tournament:
                    continue

                mdate = parse_date(row["Date"])
                mround = row.get("Rd")
                match_models.append(
                    PlayerMatch(
                        player_id=player.id,
                        opponent_id=opponent.id,
                        tournament_id=tournament.id,
                        date=mdate,
                        round=mround,
                        completed=row.get("Completed", False),
                        surface=row.get("Surface"),
                        rank=row.get("Rk"),
                        opponent_rank=row.get("vRk"),
                        score=row.get("Score"),
                        won=row.get("Won"),
                    )
                )

            if match_models:
                PlayerMatch.objects.bulk_create(
                    match_models,
                    update_conflicts=True,
                    unique_fields=["player", "opponent", "tournament", "date", "round"],
                    update_fields=["completed", "surface", "rank", "opponent_rank", "score", "won"],
                    batch_size=500,
                )

            # Re-fetch to get IDs
            keys = []
            for row in rows:
                opp_name = " ".join((row.get("Opponent") or "").split()).strip()
                year = (row.get("Date") or "")[-4:]
                t_name = " ".join((row.get("Tournament") or "").split()).strip()
                if not opp_name or not year or not t_name:
                    continue
                keys.append((player.id, opp_name, t_name, year, parse_date(row["Date"]), row.get("Rd")))

            # Map tournament name/year and opponent name back to IDs
            # (already in caches)
            q = Q()
            for (pid, opp_name, tname, year, d, rd) in keys:
                opp = players_by_name.get(opp_name)
                tour = existing_tours.get((tname, year))
                if not opp or not tour:
                    continue
                q |= Q(player_id=pid, opponent_id=opp.id, tournament_id=tour.id, date=d, round=rd)

            if not q:
                self.stdout.write(self.style.SUCCESS(f"{player.name}: 0 matches written"))
                continue

            existing_matches = {
                (m.player_id, m.opponent_id, m.tournament_id, m.date, m.round): m
                for m in PlayerMatch.objects.filter(q).only(
                    "id", "player_id", "opponent_id", "tournament_id", "date", "round"
                )
            }

            serve_stats, return_stats = [], []
            for row in rows:
                opp_name = " ".join((row.get("Opponent") or "").split()).strip()
                year = (row.get("Date") or "")[-4:]
                t_name = " ".join((row.get("Tournament") or "").split()).strip()
                if not opp_name or not year or not t_name:
                    continue
                opp = players_by_name.get(opp_name)
                tour = existing_tours.get((t_name, year))
                if not opp or not tour:
                    continue
                key = (player.id, opp.id, tour.id, parse_date(row["Date"]), row.get("Rd"))
                match = existing_matches.get(key)
                if not match:
                    continue

                bp_saved = bp_faced = None
                if row.get("BPSvd"):
                    parts = (row["BPSvd"] or "").split("/")
                    if len(parts) == 2:
                        try:
                            bp_saved, bp_faced = int(parts[0]), int(parts[1])
                        except Exception:
                            pass

                serve_stats.append(
                    PlayerMatchServeStats(
                        match_id=match.id,
                        dominance_ratio=row.get("DR"),
                        ace_pctg=pctg_to_dec(row.get("A%")),
                        df_pctg=pctg_to_dec(row.get("DF%")),
                        fs_pctg=pctg_to_dec(row.get("1stIn")),
                        fs_w_pctg=pctg_to_dec(row.get("1st%")),
                        ss_w_pctg=pctg_to_dec(row.get("2nd%")),
                        bp_saved=bp_saved,
                        bp_faced=bp_faced,
                        time=row.get("Time"),
                    )
                )

                bp_conv = bp_chances = None
                if row.get("BPCnv"):
                    parts = (row["BPCnv"] or "").split("/")
                    if len(parts) == 2:
                        try:
                            bp_conv, bp_chances = int(parts[0]), int(parts[1])
                        except Exception:
                            pass

                return_stats.append(
                    PlayerMatchReturnStats(
                        match_id=match.id,
                        dominance_ratio=row.get("DR"),
                        total_p_w=pctg_to_dec(row.get("TPW")),
                        return_p_w=pctg_to_dec(row.get("RPW")),
                        v_ace_pctg=pctg_to_dec(row.get("vA%")),
                        v_fs_pctg=pctg_to_dec(row.get("v1st%")),
                        v_ss_pctg=pctg_to_dec(row.get("v2nd%")),
                        bp_conv=bp_conv,
                        bp_chances=bp_chances,
                        time=row.get("Time"),
                    )
                )

            if serve_stats:
                PlayerMatchServeStats.objects.bulk_create(
                    serve_stats,
                    update_conflicts=True,
                    unique_fields=["match"],
                    update_fields=[
                        "dominance_ratio", "ace_pctg", "df_pctg",
                        "fs_pctg", "fs_w_pctg", "ss_w_pctg",
                        "bp_saved", "bp_faced", "time",
                    ],
                    batch_size=500,
                )

            if return_stats:
                PlayerMatchReturnStats.objects.bulk_create(
                    return_stats,
                    update_conflicts=True,
                    unique_fields=["match"],
                    update_fields=[
                        "dominance_ratio", "total_p_w", "return_p_w",
                        "v_ace_pctg", "v_fs_pctg", "v_ss_pctg",
                        "bp_conv", "bp_chances", "time",
                    ],
                    batch_size=500,
                )

            self.stdout.write(self.style.SUCCESS(f"{player.name}: wrote {len(match_models)} matches"))