# tennis/views.py
import datetime

from django.core.paginator import Paginator
from django.db.models.functions import Least
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.db.models import Q, OuterRef, Subquery, IntegerField

from tennis.models import (
    Player,
    PlayerMatch,
    MatchStatistic,
    MatchPrediction, PlayerRanking,
)


# ---------- Simple pages ----------

def home(request):
    return render(request, "home.html")


def about(request):
    return render(request, "about.html")


def contact(request):
    return render(request, "contact.html")


# ---------- Completed & upcoming match lists (read from MatchPrediction) ----------

def completed_matches(request):
    # Completed = winner exists
    matches_qs = (
        PlayerMatch.objects
        .filter(winner__isnull=False, tournament__event_type_type="Atp Singles")
        .select_related("tournament", "first_player", "second_player", "winner")
        .prefetch_related("prediction")
        .order_by("-date", "-time")
    )

    # Sorting
    _filter = request.GET.get("filter") or "date"
    if _filter == "tournament":
        matches_qs = matches_qs.order_by("tournament__name", "-date")
    elif _filter == "round":
        matches_qs = matches_qs.order_by("round", "-date")
    # default is already date

    # Pagination
    page = request.GET.get("page", 1)
    paginator = Paginator(matches_qs, 10)

    try:
        matches_page = paginator.page(page)
    except Exception:
        matches_page = paginator.page(1)

    matches = []
    for match in matches_page:
        pred: MatchPrediction = getattr(match, "prediction", None)
        if not pred:
            continue

        ens_prob = pred.ens_prob
        p1_pct = round(ens_prob * 100, 1)
        p2_pct = round((1.0 - ens_prob) * 100, 1)

        matches.append(
            {
                "match": match,
                "winner": match.winner,
                "log_reg_prob": pred.log_reg_prob,
                "rf_prob": pred.rf_prob,
                "ens_prob": ens_prob,
                "log_reg_ml_p1": pred.log_reg_ml_p1,
                "log_reg_ml_p2": pred.log_reg_ml_p2,
                "rf_ml_p1": pred.rf_ml_p1,
                "rf_ml_p2": pred.rf_ml_p2,
                "ens_ml_p1": pred.ens_ml_p1,
                "ens_ml_p2": pred.ens_ml_p2,
                "p1_pct": p1_pct,
                "p2_pct": p2_pct,
            }
        )

    # AJAX
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        matches_data = []
        for m in matches:
            match_obj = m["match"]
            matches_data.append(
                {
                    "match_id": match_obj.pk,
                    "player1_name": match_obj.first_player.name,
                    "player2_name": match_obj.second_player.name,
                    "player1_id": match_obj.first_player.pk,
                    "player2_id": match_obj.second_player.pk,
                    "tournament": str(match_obj.tournament),
                    "score": match_obj.score_line,
                    "date": match_obj.date.strftime("%Y-%m-%d"),
                    "ens_prob": m["ens_prob"],
                    "p1_pct": m["p1_pct"],
                    "p2_pct": m["p2_pct"],
                    "ens_ml_p1": m["ens_ml_p1"],
                    "ens_ml_p2": m["ens_ml_p2"],
                }
            )
        return JsonResponse(
            {
                "matches": matches_data,
                "has_next": matches_page.has_next(),
                "next_page": matches_page.next_page_number()
                if matches_page.has_next()
                else None,
            }
        )

    return render(
        request,
        "completed_matches.html",
        {
            "matches": matches,
            "has_next": matches_page.has_next(),
            "next_page": matches_page.next_page_number()
            if matches_page.has_next()
            else None,
        },
    )


def upcoming_matches(request):
    first_rank_subq = PlayerRanking.objects.filter(
        player=OuterRef("first_player"),
    ).values("ranking")[:1]

    second_rank_subq = PlayerRanking.objects.filter(
        player=OuterRef("second_player"),
    ).values("ranking")[:1]

    matches_qs = (
        PlayerMatch.objects
        .filter(winner__isnull=True, date__gte=datetime.date.today())
        .annotate(
            first_rank=Subquery(first_rank_subq, output_field=IntegerField()),
            second_rank=Subquery(second_rank_subq, output_field=IntegerField()),
            min_rank=Least("first_rank", "second_rank"),
        )
        .select_related("tournament", "first_player", "second_player")
        .prefetch_related("prediction")  # This prefetches predictions
        .order_by("min_rank", "date", "time")
    )

    page = request.GET.get("page", 1)
    paginator = Paginator(matches_qs, 10)

    try:
        matches_page = paginator.page(page)
    except Exception:
        matches_page = paginator.page(1)

    matches = []
    for match in matches_page:
        # IMPORTANT: When using prefetch_related, we need to check if
        # the prediction exists in the prefetched queryset
        # The prediction might be accessible as match.prediction_set.first()
        # or just match.prediction if you have a OneToOne relationship

        # Try different ways to get the prediction
        pred = None

        # Method 1: Direct attribute (for OneToOneField)
        if hasattr(match, 'prediction'):
            pred = match.prediction

        # Method 2: Through related manager (for ForeignKey)
        elif hasattr(match, 'prediction_set'):
            pred = match.prediction_set.first()

        # Method 3: Query directly if prefetch didn't work
        if pred is None:
            pred = MatchPrediction.objects.filter(match=match).first()

        if not pred:
            # Instead of skipping, show match without prediction details
            matches.append(
                {
                    "match": match,
                    "log_reg_prob": None,
                    "rf_prob": None,
                    "ens_prob": 0.5,  # Default 50/50
                    "log_reg_ml_p1": None,
                    "log_reg_ml_p2": None,
                    "rf_ml_p1": None,
                    "rf_ml_p2": None,
                    "ens_ml_p1": 0,  # Even money
                    "ens_ml_p2": 0,  # Even money
                    "p1_pct": 50.0,  # 50%
                    "p2_pct": 50.0,  # 50%
                    "has_prediction": False,
                }
            )
            continue

        ens_prob = pred.ens_prob
        p1_pct = round(ens_prob * 100, 1)
        p2_pct = round((1.0 - ens_prob) * 100, 1)

        matches.append(
            {
                "match": match,
                "log_reg_prob": pred.log_reg_prob,
                "rf_prob": pred.rf_prob,
                "ens_prob": ens_prob,
                "log_reg_ml_p1": pred.log_reg_ml_p1,
                "log_reg_ml_p2": pred.log_reg_ml_p2,
                "rf_ml_p1": pred.rf_ml_p1,
                "rf_ml_p2": pred.rf_ml_p2,
                "ens_ml_p1": pred.ens_ml_p1,
                "ens_ml_p2": pred.ens_ml_p2,
                "p1_pct": p1_pct,
                "p2_pct": p2_pct,
                "has_prediction": True,
            }
        )

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        matches_data = []
        for m in matches:
            match_obj = m["match"]
            matches_data.append(
                {
                    "match_id": match_obj.pk,
                    "player1_name": match_obj.first_player.name,
                    "player2_name": match_obj.second_player.name,
                    "player1_id": match_obj.first_player.pk,
                    "player2_id": match_obj.second_player.pk,
                    "tournament": str(match_obj.tournament),
                    "date": match_obj.date.strftime("%Y-%m-%d"),
                    "ens_prob": m["ens_prob"],
                    "p1_pct": m["p1_pct"],
                    "p2_pct": m["p2_pct"],
                    "ens_ml_p1": m["ens_ml_p1"],
                    "ens_ml_p2": m["ens_ml_p2"],
                }
            )
        return JsonResponse(
            {
                "matches": matches_data,
                "has_next": matches_page.has_next(),
                "next_page": matches_page.next_page_number()
                if matches_page.has_next()
                else None,
            }
        )

    return render(
        request,
        "upcoming_matches.html",
        {
            "matches": matches,
            "has_next": matches_page.has_next(),
            "next_page": matches_page.next_page_number()
            if matches_page.has_next()
            else None,
        },
    )


# ---------- Player / match detail ----------

def player_page(request, player_id):
    recent_matches = PlayerMatch.objects.filter(
        Q(status="Finished"), Q(Q(first_player__pk=player_id) | Q(second_player__pk=player_id))
    ).order_by("-date")
    player = get_object_or_404(Player, pk=player_id)

    return render(request, "player_page.html", {"player": player, "recent_matches": recent_matches})


def _group_stats_by_category(stats_qs):
    grouped = {}
    for stat in stats_qs:
        grouped.setdefault(stat.category, []).append(stat)
    return grouped


def match_page(request, match_id):
    match = get_object_or_404(
        PlayerMatch.objects.select_related(
            "tournament", "first_player", "second_player", "winner"
        ).prefetch_related("prediction"),
        pk=match_id,
    )

    pred: MatchPrediction = getattr(match, "prediction", None)

    ens_prob = pred.ens_prob if pred else None
    if ens_prob is not None:
        p1_pct = round(ens_prob * 100, 1)
        p2_pct = round((1.0 - ens_prob) * 100, 1)
    else:
        p1_pct = p2_pct = None

    all_stats = MatchStatistic.objects.filter(
        match=match,
        period=MatchStatistic.Period.MATCH,
    ).order_by("player__name", "category", "name")

    p1_stats = all_stats.filter(player=match.first_player)
    p2_stats = all_stats.filter(player=match.second_player)

    context = {
        "match": match,
        "first_player": match.first_player,
        "second_player": match.second_player,
        "winner": match.winner,
        "score_line": match.score_line,
        "surface": match.surface,
        "tournament": match.tournament,
        "round": match.round,
        "date": match.date,
        "p1_stats": _group_stats_by_category(p1_stats),
        "p2_stats": _group_stats_by_category(p2_stats),
        "pred": pred,
        "ens_prob": ens_prob,
        "p1_pct": p1_pct,
        "p2_pct": p2_pct,
    }

    return render(request, "match_page.html", context)


def h_to_h_page(request, match_id):
    # Load current match
    match = get_object_or_404(PlayerMatch, pk=match_id)

    # These two players
    player = match.first_player
    opponent = match.second_player

    # Find any matches where they have faced each other
    h2h_matches = PlayerMatch.objects.filter(
        (
            Q(first_player=player, second_player=opponent) |
            Q(first_player=opponent, second_player=player)
        ),
        winner__isnull=False  # Only completed matches
    ).order_by("-date", "-time")

    player_wins = 0
    opponent_wins = 0
    surface_stats = {}

    for m in h2h_matches:
        # Determine who won
        if m.winner == player:
            player_wins += 1
            winner = player
        else:
            opponent_wins += 1
            winner = opponent

        # Surface stats
        surface = m.surface or "Unknown"
        if surface not in surface_stats:
            surface_stats[surface] = {
                "player_wins": 0,
                "opponent_wins": 0,
                "total": 0,
            }

        surface_stats[surface]["total"] += 1
        if winner == player:
            surface_stats[surface]["player_wins"] += 1
        else:
            surface_stats[surface]["opponent_wins"] += 1

    return render(
        request,
        "h_to_h_page.html",
        {
            "h2h_matches": h2h_matches,
            "player_wins": player_wins,
            "opponent_wins": opponent_wins,
            "player": player,
            "opponent": opponent,
            "surface_stats": surface_stats,
        },
    )
