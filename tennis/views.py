import joblib
import pandas as pd
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render
from django.db.models import Q

from tennis.ml.feature_engineering import TennisFeatureEngineer
from tennis.models import Player, PlayerMatch


def prob_to_american(p: float, round_to: int = 1) -> int:
    """
    Convert a fair (no-vig) win probability p to American moneyline.
    p in (0,1). Returns an integer line (e.g., -145, +220).
    """
    # clamp to avoid infinities
    p = min(max(p, 1e-6), 1 - 1e-6)
    if p >= 0.5:
        line = -int(round((p / (1 - p)) * 100.0 / round_to) * round_to)
    else:
        line = int(round(((1 - p) / p) * 100.0 / round_to) * round_to)
    return line

def prob_to_decimal(p: float) -> float:
    """Fair decimal odds (stake-inclusive)."""
    p = min(max(p, 1e-6), 1 - 1e-6)
    return round(1.0 / p, 4)

def american_to_implied_prob(ml: int) -> float:
    """Implied probability from an American moneyline."""
    if ml < 0:
        return (-ml) / ((-ml) + 100.0)
    else:
        return 100.0 / (ml + 100.0)

def home(request):
    return render(request, "home.html")

def about(request):
    return render(request, "about.html")
def contact(request):
    return render(request, "contact.html")

def completed_matches(request):
    from csv import DictReader
    with open("tennis/models/probabilities.csv", 'r') as f:
        dict_reader = DictReader(f)
        list_of_dict = list(dict_reader)

    if request.method == "GET":
        _filter = request.GET.get("filter") if request.GET.get("filter") else "date"

    sorted_dict = sorted(list_of_dict, key=lambda x: x[_filter], reverse=True)

    # Filter only completed matches
    completed_dicts = [item for item in sorted_dict if item["completed"] == "True"]

    # Pagination - show first 10 by default
    page = request.GET.get('page', 1)
    paginator = Paginator(completed_dicts, 10)  # Show 10 matches per page

    try:
        matches_page = paginator.page(page)
    except:
        matches_page = paginator.page(1)

    matches = []
    for item in matches_page:
        match = PlayerMatch.objects.get(id=item["match"])
        winner = match.player if match.won else match.opponent
        p1_pct = round(float(item['ens_prob']) * 100, 1)
        p2_prob = 1 - float(item['ens_prob'])
        p2_pct = round(p2_prob * 100, 1)
        matches_dict = {
            "match": match,
            "winner": winner,
            "log_reg_prob": item["log_reg_prob"],
            "rf_prob": item["rf_prob"],
            "ens_prob": float(item["ens_prob"]),
            "log_reg_ml_p1": item["log_reg_ml_p1"],
            "log_reg_ml_p2": item["log_reg_ml_p2"],
            "rf_ml_p1": item["rf_ml_p1"],
            "rf_ml_p2": item["rf_ml_p2"],
            "ens_ml_p1": item["ens_ml_p1"],
            "ens_ml_p2": item["ens_ml_p2"],
            "p1_pct": p1_pct,
            "p2_pct": p2_pct,
        }
        matches.append(matches_dict)

    # If it's an AJAX request, return JSON
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        matches_data = []
        for m in matches:
            matches_data.append({
                'match_id': m['match'].id,
                'player1_name': m['match'].player.name,
                'player2_name': m['match'].opponent.name,
                'player1_id': m['match'].player.id,
                'player2_id': m['match'].opponent.id,
                'tournament': str(m['match'].tournament),
                'score': m['match'].score,
                'date': m['match'].date.strftime('%Y-%m-%d'),
                'won': m['match'].won,
                'ens_prob': m['ens_prob'],
                'p1_pct': m['p1_pct'],
                'p2_pct': m['p2_pct'],
                'ens_ml_p1': m['ens_ml_p1'],
                'ens_ml_p2': m['ens_ml_p2'],
            })
        return JsonResponse({
            'matches': matches_data,
            'has_next': matches_page.has_next(),
            'next_page': matches_page.next_page_number() if matches_page.has_next() else None
        })

    return render(request, "completed_matches.html", {
        "matches": matches,
        "has_next": matches_page.has_next(),
        "next_page": matches_page.next_page_number() if matches_page.has_next() else None
    })


def upcoming_matches(request):
    from csv import DictReader
    with open("tennis/models/probabilities.csv", 'r') as f:
        dict_reader = DictReader(f)
        list_of_dict = list(dict_reader)

    # Filter only upcoming matches
    upcoming_dicts = [item for item in list_of_dict if item["completed"] == "False"]

    # Pagination - show first 10 by default
    page = request.GET.get('page', 1)
    paginator = Paginator(upcoming_dicts, 10)  # Show 10 matches per page

    try:
        matches_page = paginator.page(page)
    except:
        matches_page = paginator.page(1)

    matches = []
    for item in matches_page:
        p1_pct = round(float(item['ens_prob']) * 100, 1)
        p2_prob = 1 - float(item['ens_prob'])
        p2_pct = round(p2_prob * 100, 1)
        matches_dict = {
            "match": PlayerMatch.objects.get(id=item["match"]),
            "log_reg_prob": item["log_reg_prob"],
            "rf_prob": item["rf_prob"],
            "ens_prob": float(item["ens_prob"]),
            "log_reg_ml_p1": item["log_reg_ml_p1"],
            "log_reg_ml_p2": item["log_reg_ml_p2"],
            "rf_ml_p1": item["rf_ml_p1"],
            "rf_ml_p2": item["rf_ml_p2"],
            "ens_ml_p1": item["ens_ml_p1"],
            "ens_ml_p2": item["ens_ml_p2"],
            "p1_pct": p1_pct,
            "p2_pct": p2_pct,
        }
        matches.append(matches_dict)

    # If it's an AJAX request, return JSON
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        matches_data = []
        for m in matches:
            matches_data.append({
                'match_id': m['match'].id,
                'player1_name': m['match'].player.name,
                'player2_name': m['match'].opponent.name,
                'player1_id': m['match'].player.id,
                'player2_id': m['match'].opponent.id,
                'tournament': str(m['match'].tournament),
                'date': m['match'].date.strftime('%Y-%m-%d'),
                'ens_prob': m['ens_prob'],
                'p1_pct': m['p1_pct'],
                'p2_pct': m['p2_pct'],
                'ens_ml_p1': m['ens_ml_p1'],
                'ens_ml_p2': m['ens_ml_p2'],
            })
        return JsonResponse({
            'matches': matches_data,
            'has_next': matches_page.has_next(),
            'next_page': matches_page.next_page_number() if matches_page.has_next() else None
        })

    return render(request, "upcoming_matches.html", {
        "matches": matches,
        "has_next": matches_page.has_next(),
        "next_page": matches_page.next_page_number() if matches_page.has_next() else None
    })

def player_page(request, player_id):
    recent_matches = PlayerMatch.objects.filter(Q(completed=True), Q(player_id=player_id)).order_by('-date')
    player = Player.objects.get(id=player_id)

    return render(request, "player_page.html", {"player": player, "recent_matches": recent_matches})


def match_page(request, match_id):
    player_match = PlayerMatch.objects.get(id=match_id)

    # Get the reverse match (where opponent is player and player is opponent)
    try:
        opponent_match = PlayerMatch.objects.get(
            player=player_match.opponent,
            opponent=player_match.player,
            tournament=player_match.tournament,
            date=player_match.date
        )
    except PlayerMatch.DoesNotExist:
        opponent_match = None

    # Get stats for the current match (player perspective)
    player_serve_stats = PlayerMatchServeStats.objects.filter(match=player_match)
    player_return_stats = PlayerMatchReturnStats.objects.filter(match=player_match)

    # Get stats for the opponent's perspective match
    if opponent_match:
        opponent_serve_stats = PlayerMatchServeStats.objects.filter(match=opponent_match)
        opponent_return_stats = PlayerMatchReturnStats.objects.filter(match=opponent_match)
    else:
        opponent_serve_stats = PlayerMatchServeStats.objects.none()
        opponent_return_stats = PlayerMatchReturnStats.objects.none()

    context = {
        'match': player_match,
        'opponent_match': opponent_match,
        'player_serve_stats': player_serve_stats,
        'player_return_stats': player_return_stats,
        'opponent_serve_stats': opponent_serve_stats,
        'opponent_return_stats': opponent_return_stats,
    }

    return render(request, "match_page.html", context=context)


def h_to_h_page(request, match_id):
    match = PlayerMatch.objects.get(id=match_id)
    player = match.player
    opponent = match.opponent
    h2h_matches = PlayerMatch.objects.filter(
        Q(player=player, opponent=opponent, completed=True)
    ).order_by('-date')

    player_wins = 0
    opponent_wins = 0
    surface_stats = {}

    for match in h2h_matches:
        if match.won:
            player_wins += 1
            winner = player
        else:
            opponent_wins += 1
            winner = opponent

        # Calculate surface statistics
        surface = match.surface or "Unknown"
        if surface not in surface_stats:
            surface_stats[surface] = {
                'player_wins': 0,
                'opponent_wins': 0,
                'total': 0
            }

        surface_stats[surface]['total'] += 1
        if winner == player:
            surface_stats[surface]['player_wins'] += 1
        else:
            surface_stats[surface]['opponent_wins'] += 1

    return render(request, "h_to_h_page.html", {
        "h2h_matches": h2h_matches,
        "player_wins": player_wins,
        "opponent_wins": opponent_wins,
        "player": player,
        "opponent": opponent,
        "surface_stats": surface_stats
    })