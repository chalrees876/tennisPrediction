import joblib
import pandas as pd
from django.shortcuts import render
from django.db.models import Q

from tennis.ml.feature_engineering import TennisFeatureEngineer
from tennis.models import Player, PlayerElo, PlayerMatch


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

def completed_matches(request):
    from csv import DictReader
    with open("tennis/models/probabilities.csv", 'r') as f:
        dict_reader = DictReader(f)
        list_of_dict = list(dict_reader)
    if request.method == "GET":
        _filter = request.GET.get("filter") if request.GET.get("filter") else "date"
    sorted_dict = sorted(list_of_dict, key=lambda x: x[_filter], reverse=True)
    matches = []
    for item in sorted_dict:
        if item["completed"] == "True":
            match = PlayerMatch.objects.get(id=item["match"])
            winner = match.player if match.won else match.opponent
            p1_pct = round(float(item['ens_prob']) * 100, 1)
            p2_prob = 1 - float(item['ens_prob'])
            p2_pct = round(p2_prob * 100, 1)
            matches_dict = {
                "match": PlayerMatch.objects.get(id=item["match"]),
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

    return render(request, "completed_matches.html", {"matches": matches})

def upcoming_matches(request):
    from csv import DictReader
    # open file in read mode
    with open("tennis/models/probabilities.csv", 'r') as f:
        dict_reader = DictReader(f)
        list_of_dict = list(dict_reader)
    matches = []
    for item in list_of_dict:
        if item["completed"] == "False":
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
    return render(request, "upcoming_matches.html", {"matches": matches})

def player_page(request, player_id):
    recent_matches = PlayerMatch.objects.filter(Q(completed=True), Q(player_id=player_id)).order_by('-date')
    player = Player.objects.get(id=player_id)

    return render(request, "player_page.html", {"player": player, "recent_matches": recent_matches})

def match_page(request, match_id):
    match = PlayerMatch.objects.get(id=match_id)
    return render(request, "match_page.html", {"match": match})

def h_to_h_page(request, match_id):
    match = PlayerMatch.objects.get(id=match_id)
    player = match.player
    opponent = match.opponent
    h2h_matches = PlayerMatch.objects.filter(player=player, opponent=opponent)
    player_wins = 0
    opponent_wins = 0
    for match in h2h_matches:
        if match.won:
            player_wins += 1
        else:
            opponent_wins += 1


    return render(request, "h_to_h_page.html", {"h2h_matches": h2h_matches, "player_wins": player_wins, "opponent_wins": opponent_wins, "player": player, "opponent": opponent})