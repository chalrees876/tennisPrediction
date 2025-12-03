# tennis/ml/predictor.py - UPDATED VERSION

import joblib
import pandas as pd
from typing import Dict, Any
import numpy as np

from tennis.ml.apiFeatures import get_match_features, get_odds_features
from tennis.utils.odds import prob_to_american

# Load models ONCE at import time (per process)
LR_MODEL = joblib.load("tennis/ml/models/logreg_all.joblib")
RF_MODEL = joblib.load("tennis/ml/models/rf_all.joblib")

# Infer feature columns from the LR pipeline
FEATURE_COLUMNS = LR_MODEL.named_steps["preprocessor"].transformers_[0][2]


def build_feature_dict_for_match(match, max_matches: int = 20) -> Dict[str, Any]:
    """
    Rebuild the same feature dict used in training for a single match.
    Returns features even if some/all are missing (will be filled with defaults).
    """
    stats_feats = get_match_features(match, max_matches=max_matches) or {}
    odds_feats = get_odds_features(match) or {}

    feats: Dict[str, Any] = {}
    feats.update(stats_feats)
    feats.update(odds_feats)
    return feats


def has_sufficient_features(feats: Dict[str, Any], min_required: int = 5) -> bool:
    """
    Check if we have enough non-null features to make a reasonable prediction.
    """
    non_null_count = sum(1 for v in feats.values() if v is not None and not pd.isna(v))
    return non_null_count >= min_required


def predict_for_match(match, allow_low_confidence: bool = True) -> Dict[str, Any]:
    """
    Compute probabilities + moneylines for a single PlayerMatch.

    Args:
        match: PlayerMatch object
        allow_low_confidence: If True, returns 50/50 predictions when features are insufficient.
                             If False, raises ValueError for insufficient features.

    Returns:
        Dict with prediction probabilities and moneylines
    """
    feats = build_feature_dict_for_match(match)

    # Check if we have sufficient features
    has_features = has_sufficient_features(feats)

    if not has_features and not allow_low_confidence:
        raise ValueError(f"Insufficient features for match {match.pk}")

    # Create DataFrame with features
    row = pd.DataFrame([feats])
    X = row.reindex(columns=FEATURE_COLUMNS, fill_value=None)

    # Check if we have ANY features at all
    if X.isna().all().all() or not has_features:
        # Return 50/50 prediction for matches without data
        return {
            "log_reg_prob": 0.5,
            "rf_prob": 0.5,
            "ens_prob": 0.5,
            "log_reg_ml_p1": 0,
            "log_reg_ml_p2": 0,
            "rf_ml_p1": 0,
            "rf_ml_p2": 0,
            "ens_ml_p1": 0,
            "ens_ml_p2": 0,
            "low_confidence": True,  # Flag to indicate uncertain prediction
        }

    try:
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
            "low_confidence": False,
        }
    except Exception as e:
        # If prediction fails, return 50/50
        if allow_low_confidence:
            return {
                "log_reg_prob": 0.5,
                "rf_prob": 0.5,
                "ens_prob": 0.5,
                "log_reg_ml_p1": 0,
                "log_reg_ml_p2": 0,
                "rf_ml_p1": 0,
                "rf_ml_p2": 0,
                "ens_ml_p1": 0,
                "ens_ml_p2": 0,
                "low_confidence": True,
                "error": str(e),
            }
        else:
            raise ValueError(f"Prediction failed for match {match.pk}: {e}")