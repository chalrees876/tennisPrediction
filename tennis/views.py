import joblib
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render
from django.db.models import Q, F

from tennis.ml.MachineLearning import MachineLearningModels
from tennis.models import (
    Player, PlayerMatch, PlayerMatchServeStats, 
    PlayerMatchReturnStats, MatchFeatures
)

def format_moneyline(ml: int) -> str:
    if ml > 0:
        return f"+{ml}"
    return str(ml)


def prob_to_american(p: float, round_to: int = 1) -> int:
    """Convert a fair (no-vig) win probability p to American moneyline."""
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


# Cache the model bundle (load once)
_model_bundle = None

def get_model_bundle():
    global _model_bundle
    if _model_bundle is None:
        try:
            _model_bundle = joblib.load('tennis_model.joblib')
        except FileNotFoundError:
            _model_bundle = None
    return _model_bundle


def home(request):
    return render(request, "home.html")


def about(request):
    return render(request, "about.html")


def contact(request):
    return render(request, "contact.html")


def completed_matches(request):
    # Get completed matches with training data
    matches_qs = MatchFeatures.objects.filter(
        match__completed=True,
        match__won__isnull=False
    ).select_related(
        'match', 'match__player', 'match__opponent', 'match__tournament'
    ).order_by('-match__date')
    
    # Handle sorting
    sort_field = request.GET.get("filter", "date")
    if sort_field == "date":
        matches_qs = matches_qs.order_by('-match__date')
    elif sort_field == "ens_prob":
        matches_qs = matches_qs.order_by('-player_win_prob')

    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(matches_qs, 10)

    try:
        matches_page = paginator.page(page)
    except:
        matches_page = paginator.page(1)

    bundle = get_model_bundle()
    matches = []

    for td in matches_page:
        match = td.match
        winner = match.player if match.won else match.opponent
        
        if bundle:
            ml = MachineLearningModels()
            prediction = ml.predict_match(bundle, td)
            td.player_win_prob = prediction['player_win_prob']
            td.save(update_fields=['player_win_prob'])

        # Use stored prediction or calculate live
        ens_prob = getattr(td, 'player_win_prob', None)
        if ens_prob is None:
            ens_prob = 0.5  # Fallback
        
        p1_pct = round(ens_prob * 100, 1)
        p2_pct = round((1 - ens_prob) * 100, 1)

        ens_ml_p1 = prob_to_american(ens_prob)
        ens_ml_p2 = prob_to_american(1 - ens_prob)
        
        matches.append({
            "match": match,
            "winner": winner,
            "ens_prob": ens_prob,
            "p1_pct": p1_pct,
            "p2_pct": p2_pct,
            "ens_ml_p1": format_moneyline(ens_ml_p1),
            "ens_ml_p2": format_moneyline(ens_ml_p2),
        })

    # AJAX response
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        matches_data = [{
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
        } for m in matches]

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
    # Get upcoming (not completed) matches with training data
    matches_qs = MatchFeatures.objects.filter(
        match__completed=False,
        match__player_id__lt=F('match__opponent_id')  # Consistent deduplication
    ).select_related(
        'match', 'match__player', 'match__opponent', 'match__tournament'
    ).order_by('match__player__ranking', 'match__date')

    print(f"DEBUG: Found {matches_qs.count()} matches")


    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(matches_qs, 10)

    try:
        matches_page = paginator.page(page)
    except:
        matches_page = paginator.page(1)

    matches = []

    for td in matches_page:
        match = td.match
        
        ens_prob = getattr(td, 'player_win_prob', None)
        if ens_prob is None:
            ens_prob = 0.5

        p1_pct = round(ens_prob * 100, 1)
        p2_pct = round((1 - ens_prob) * 100, 1)
        
        ens_prob_p1 = prob_to_american(ens_prob)
        ens_prob_p2 = prob_to_american(1 - ens_prob)

        matches.append({
            "match": match,
            "ens_prob": ens_prob,
            "p1_pct": p1_pct,
            "p2_pct": p2_pct,
            "ens_ml_p1": format_moneyline(ens_prob_p1),
            "ens_ml_p2": format_moneyline(ens_prob_p2),
        })

    # AJAX response
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        matches_data = [{
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
        } for m in matches]

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
    player = Player.objects.get(id=player_id)
    recent_matches = PlayerMatch.objects.filter(
        completed=True, player_id=player_id
    ).select_related('opponent', 'tournament').order_by('-date')

    return render(request, "player_page.html", {
        "player": player,
        "recent_matches": recent_matches
    })


def match_page(request, match_id):
    player_match = PlayerMatch.objects.select_related(
        'player', 'opponent', 'tournament'
    ).get(id=match_id)

    # Get the reverse match
    try:
        opponent_match = PlayerMatch.objects.get(
            player=player_match.opponent,
            opponent=player_match.player,
            tournament=player_match.tournament,
            date=player_match.date
        )
    except PlayerMatch.DoesNotExist:
        opponent_match = None

    # Get stats
    player_serve_stats = PlayerMatchServeStats.objects.filter(match=player_match)
    player_return_stats = PlayerMatchReturnStats.objects.filter(match=player_match)

    if opponent_match:
        opponent_serve_stats = PlayerMatchServeStats.objects.filter(match=opponent_match)
        opponent_return_stats = PlayerMatchReturnStats.objects.filter(match=opponent_match)
    else:
        opponent_serve_stats = PlayerMatchServeStats.objects.none()
        opponent_return_stats = PlayerMatchReturnStats.objects.none()

    # Get prediction data if available
    try:
        training_data = MatchFeatures.objects.get(match=player_match)
        prediction = {
            'ens_prob': training_data.player_win_prob,
            'p1_pct': round((training_data.player_win_prob or 0.5) * 100, 1),
            'p2_pct': round((1 - (training_data.player_win_prob or 0.5)) * 100, 1),
        }
    except MatchFeatures.DoesNotExist:
        prediction = None

    return render(request, "match_page.html", {
        'match': player_match,
        'opponent_match': opponent_match,
        'player_serve_stats': player_serve_stats,
        'player_return_stats': player_return_stats,
        'opponent_serve_stats': opponent_serve_stats,
        'opponent_return_stats': opponent_return_stats,
        'prediction': prediction,
    })


def h_to_h_page(request, match_id):
    match = PlayerMatch.objects.select_related('player', 'opponent').get(id=match_id)
    player = match.player
    opponent = match.opponent

    h2h_matches = PlayerMatch.objects.filter(
        player=player, opponent=opponent, completed=True
    ).select_related('tournament').order_by('-date')

    player_wins = 0
    opponent_wins = 0
    surface_stats = {}

    for m in h2h_matches:
        if m.won:
            player_wins += 1
            winner = player
        else:
            opponent_wins += 1
            winner = opponent

        surface = m.surface or "Unknown"
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