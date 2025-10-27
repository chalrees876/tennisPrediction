from django.shortcuts import render

from tennis.ml.feature_engineering import TennisFeatureEngineer
from tennis.models import Player, PlayerElo, PlayerMatch


def home(request):
    match_feature_list = []
    try:
        upcoming_matches = PlayerMatch.objects.filter(completed=False)
    except PlayerMatch.DoesNotExist:
        upcoming_matches = "No features available"
    context = {"upcoming_matches": upcoming_matches}
    return render(request, "home.html", context)

def match_features(request, match_id):

    try:
        match = PlayerMatch.objects.get(id=match_id)
        features = TennisFeatureEngineer().create_match_features(match)
    except Exception as e:
        return render(request, "home.html", {"error": e})
    context = {"match": match, "features": features}
    return render(request, "features.html", context)