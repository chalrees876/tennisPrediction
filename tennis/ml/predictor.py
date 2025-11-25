# tennis/ml/predictor.py

import joblib
import pandas as pd
from typing import Dict, Any

from tennis.ml.apiFeatures import get_match_features, get_odds_features
from tennis.utils.odds import prob_to_american  # move odds helpers here


# Load models ONCE at import time (per process)
LR_MODEL = joblib.load("tennis/ml/models/logreg_all.joblib")
RF_MODEL = joblib.load("tennis/ml/models/rf_all.joblib")

# Infer feature columns from the LR pipeline
FEATURE_COLUMNS = LR_MODEL.named_steps["preprocessor"].transformers_[0][2]


def build_feature_dict_for_match(match, max_matches: int = 20) -> Dict[str, Any]:
    """
    Rebuild the same feature dict used in training for a single match.
    Currently just stats; if you add odds features, merge them here.
    """
    stats_feats = get_match_features(match, max_matches=max_matches) or {}
    odds_feats = get_odds_features(match) or {}

    feats: Dict[str, Any] = {}
    feats.update(stats_feats)
    feats.update(odds_feats)
    return feats


def predict_for_match(match) -> Dict[str, Any]:
    """
    Compute probabilities + moneylines for a single PlayerMatch.
    This is meant to be used offline (e.g. in a management command).
    """

    feats = build_feature_dict_for_match(match)
    if not feats:
        raise ValueError(f"No features available for match {match.pk}")

    row = pd.DataFrame([feats])
    X = row.reindex(columns=FEATURE_COLUMNS, fill_value=None)

    # Model predictions (prob first_player wins)
    p_lr = float(LR_MODEL.predict_proba(X)[0, 1])
    p_rf = float(RF_MODEL.predict_proba(X)[0, 1])
    p_ens = 0.5 * p_lr + 0.5 * p_rf

    lr_ml_p1 = prob_to_american(p_lr)
    lr_ml_p2 = prob_to_american(1.0 - p_lr)

    rf_ml_p1 = prob_to_american(p_rf)
    rf_ml_p2 = prob_to_american(1.0 - p_rf)

    ens_ml_p1 = prob_to_american(p_ens)
    ens_ml_p2 = prob_to_american(1.0 - p_ens)

    return {
        "log_reg_prob": p_lr,
        "rf_prob": p_rf,
        "ens_prob": p_ens,
        "log_reg_ml_p1": lr_ml_p1,
        "log_reg_ml_p2": lr_ml_p2,
        "rf_ml_p1": rf_ml_p1,
        "rf_ml_p2": rf_ml_p2,
        "ens_ml_p1": ens_ml_p1,
        "ens_ml_p2": ens_ml_p2,
    }
