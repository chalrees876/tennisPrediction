import joblib
import pandas as pd
from django.shortcuts import render

from tennis.ml.feature_engineering import TennisFeatureEngineer
from tennis.models import Player, PlayerElo, PlayerMatch


def home(request):
    match_odds_list = []
    model = joblib.load('adjusted_model.joblib')
    try:
        upcoming_matches = PlayerMatch.objects.filter(completed=False)
        for match in upcoming_matches:
            match_features = TennisFeatureEngineer().create_match_features(match)
            X_one = pd.DataFrame([match_features])
            print(f"X_one: {X_one}")
            p1_prob = model.predict_proba(X_one)
            match_features["match"] = match
            match_features["odds"] = p1_prob[0][1]
            match_odds_list.append(match_features)
    except PlayerMatch.DoesNotExist:
        upcoming_matches = "No features available"
    context = {"match_odds_list": match_odds_list}
    return render(request, "home.html", context)

def match_odds(request, match_id):
    features_adjusted = ['win_rate_adjusted', 'dominance_ratio_adjusted', 'serve_rating_adjusted',
                         'return_rating_adjusted']

    try:
        match = PlayerMatch.objects.get(id=match_id)
        model = joblib.load('adjusted_model.joblib')
        match_features = TennisFeatureEngineer().create_match_features(match)
        X_one = pd.DataFrame([match_features], columns=features_adjusted)
        p1_prob = model.predict_proba(X_one)
        odds = p1_prob / (1 - p1_prob)
        context = {"odds": odds, "p1_prob": p1_prob, "match": match}
        return render(request, "odds.html", context)
    except Exception as e:
        return render(request, "tennis/error.html", {"error": e})