# tennis/ml/train_models.py

import os
import joblib
import numpy as np
import pandas as pd

from typing import List

from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    roc_auc_score,
    log_loss,
    brier_score_loss,
    accuracy_score,
)


DATA_PATH = "tennis/data/match_features.csv"
MODEL_DIR = "tennis/ml/models"


def load_dataset(path: str = DATA_PATH) -> pd.DataFrame:
    df = pd.read_csv(path)
    # drop any rows without label just in case
    df = df.dropna(subset=["winner_is_first"])
    return df


def pick_feature_columns(df: pd.DataFrame, variant: str = "all") -> List[str]:
    """
    variant:
      - "all": stats + odds
      - "no_odds": stats only (exclude odds_*)
      - "odds_only": only odds_* columns
    """
    meta_cols = [
        "match_key",
        "date",
        "time",
        "tournament",
        "round",
        "first_player",
        "second_player",
        "winner_is_first",
        "has_stats",
        "has_enough_stats",
        "has_odds",
        "num_stats_values",
    ]

    all_feature_cols = [c for c in df.columns if c not in meta_cols]
    odds_cols = [c for c in all_feature_cols if c.startswith("odds_")]
    stat_cols = [c for c in all_feature_cols if not c.startswith("odds_")]

    if variant == "all":
        return stat_cols + odds_cols
    elif variant == "no_odds":
        return stat_cols
    elif variant == "odds_only":
        return odds_cols
    else:
        raise ValueError(f"Unknown feature variant: {variant}")



def build_pipelines(feature_cols: List[str]):
    """
    Build two pipelines:
      - Logistic regression (with impute + scaling)
      - Random forest (with impute, no scaling)
    """
    numeric_features = feature_cols

    # Preprocess for LR: impute + scale
    preprocessor_lr = ColumnTransformer(
        transformers=[
            (
                "num",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                numeric_features,
            )
        ]
    )

    # Preprocess for RF: impute only
    preprocessor_rf = ColumnTransformer(
        transformers=[
            (
                "num",
                SimpleImputer(strategy="median"),
                numeric_features,
            )
        ]
    )

    # Logistic Regression
    lr = LogisticRegression(
        penalty="l2",
        C=1.0,
        max_iter=2000,
        class_weight="balanced",
        solver="lbfgs",
        n_jobs=-1,
    )

    pipe_lr = Pipeline(
        steps=[
            ("preprocessor", preprocessor_lr),
            ("clf", lr),
        ]
    )

    # Random Forest
    rf = RandomForestClassifier(
        n_estimators=500,
        max_depth=None,
        min_samples_leaf=10,
        n_jobs=-1,
        class_weight="balanced_subsample",
        random_state=42,
    )

    pipe_rf = Pipeline(
        steps=[
            ("preprocessor", preprocessor_rf),
            ("clf", rf),
        ]
    )

    return pipe_lr, pipe_rf


def evaluate_ensemble(y_true, p_lr, p_rf, name_prefix=""):
    p_ens = 0.5 * p_lr + 0.5 * p_rf

    metrics = {
        "auc_lr": roc_auc_score(y_true, p_lr),
        "auc_rf": roc_auc_score(y_true, p_rf),
        "auc_ens": roc_auc_score(y_true, p_ens),
        "logloss_lr": log_loss(y_true, p_lr),
        "logloss_rf": log_loss(y_true, p_rf),
        "logloss_ens": log_loss(y_true, p_ens),
        "brier_lr": brier_score_loss(y_true, p_lr),
        "brier_rf": brier_score_loss(y_true, p_rf),
        "brier_ens": brier_score_loss(y_true, p_ens),
    }

    # choose 0.5 cut for accuracy just to see
    y_lr = (p_lr >= 0.5).astype(int)
    y_rf = (p_rf >= 0.5).astype(int)
    y_ens = (p_ens >= 0.5).astype(int)

    metrics.update(
        {
            "acc_lr": accuracy_score(y_true, y_lr),
            "acc_rf": accuracy_score(y_true, y_rf),
            "acc_ens": accuracy_score(y_true, y_ens),
        }
    )

    print(f"\n=== {name_prefix}Metrics ===")
    for k, v in metrics.items():
        print(f"{k:12s}: {v:.4f}")

    return metrics, p_ens


def main(
    data_path: str = DATA_PATH,
    feature_variant: str = "all",  # "all" | "no_odds" | "odds_only"
    test_size: float = 0.2,
    random_state: int = 42,
):
    os.makedirs(MODEL_DIR, exist_ok=True)

    print(f"Loading data from {data_path}...")
    df = load_dataset(data_path)

    # --- row-level filtering depending on model type ---
    if feature_variant in ("all", "no_odds"):
        # only matches with enough stats
        df = df[df["has_enough_stats"] == 1]
    if feature_variant == "odds_only":
        # only matches that actually have odds
        df = df[df["has_odds"] == 1]

    print(f"Rows after filtering for '{feature_variant}': {len(df)}")

    feature_cols = pick_feature_columns(df, variant=feature_variant)
    print(f"Using {len(feature_cols)} features (variant={feature_variant})")

    X = df[feature_cols].astype(float)
    y = df["winner_is_first"].astype(int)

    X_train, X_valid, y_train, y_valid = train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=random_state,
        stratify=y,
    )

    pipe_lr, pipe_rf = build_pipelines(feature_cols)

    print("\nFitting Logistic Regression...")
    pipe_lr.fit(X_train, y_train)

    print("Fitting Random Forest...")
    pipe_rf.fit(X_train, y_train)

    p_lr = pipe_lr.predict_proba(X_valid)[:, 1]
    p_rf = pipe_rf.predict_proba(X_valid)[:, 1]

    metrics, p_ens = evaluate_ensemble(
        y_valid, p_lr, p_rf, name_prefix=f"{feature_variant.upper()} "
    )

    lr_path = os.path.join(MODEL_DIR, f"logreg_{feature_variant}.joblib")
    rf_path = os.path.join(MODEL_DIR, f"rf_{feature_variant}.joblib")

    joblib.dump(pipe_lr, lr_path)
    joblib.dump(pipe_rf, rf_path)

    print(f"\nSaved Logistic Regression to: {lr_path}")
    print(f"Saved Random Forest       to: {rf_path}")

    return metrics



if __name__ == "__main__":
    # Train with all features (stats + odds).
    # You can also call main(feature_variant="no_odds") or "odds_only"
    main(feature_variant="all")
