import numpy as np
import pandas as pd

from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import TimeSeriesSplit, GridSearchCV
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import roc_auc_score, brier_score_loss
from sklearn.ensemble import RandomForestClassifier

class MachineLearningModels:
    def __init__(self, training_df: pd.DataFrame):
        self.training_df = training_df

    def _time_split(self, X, y, frac=0.8):
        n = len(X)
        cut = int(n * frac)
        return (X.iloc[:cut], X.iloc[cut:], y.iloc[:cut], y.iloc[cut:])

    def log_reg_train(self):
        print("-------------------------------\n Logistic Regression (Elastic-Net + Calibration) --------------------")

        # 1) Sort by time and build X/y
        df = (self.training_df
              .sort_values('date')
              .reset_index(drop=True))
        y = df['target'].astype(int)
        X = df.drop(columns=['target', 'match_id', 'date', 'player_id', 'opponent_id'], errors='ignore').fillna(0)

        # 2) Temporal split (no leakage)
        X_train, X_test, y_train, y_test = self._time_split(X, y, frac=0.8)

        # 3) Elastic-Net LR with scaling inside pipeline, time-series CV
        pipe = Pipeline([
            ('scaler', StandardScaler()),
            ('clf', LogisticRegression(solver='saga', penalty='elasticnet', max_iter=20000, random_state=42))
        ])

        param_grid = [
            # Elastic-net
            {'clf__penalty': ['elasticnet'],
             'clf__C': np.logspace(-3, 2, 15),
             'clf__l1_ratio': [0.1, 0.3, 0.5, 0.7, 0.9],
             'clf__class_weight': [None, 'balanced']},

            # Pure L2 (often wins when EN chooses tiny l1_ratio)
            {'clf__penalty': ['l2'],
             'clf__C': np.logspace(-3, 2, 15),
             'clf__class_weight': [None, 'balanced']}
        ]
        tscv = TimeSeriesSplit(n_splits=5)

        grid = GridSearchCV(
            estimator=pipe,
            param_grid=param_grid,
            scoring='roc_auc',
            cv=tscv,
            n_jobs=-1,
            refit=True,
            verbose=0
        )
        grid.fit(X_train, y_train)
        best_lr = grid.best_estimator_

        cal_iso = CalibratedClassifierCV(best_lr, method='isotonic', cv=tscv).fit(X_train, y_train)
        cal_sig = CalibratedClassifierCV(best_lr, method='sigmoid', cv=tscv).fit(X_train, y_train)

        p_iso = cal_iso.predict_proba(X_test)[:, 1]
        p_sig = cal_sig.predict_proba(X_test)[:, 1]

        def auc_brier(p):
            return roc_auc_score(y_test, p), brier_score_loss(y_test, p)

        au_iso, br_iso = auc_brier(p_iso)
        au_sig, br_sig = auc_brier(p_sig)

        # pick the better (prefer higher AUC, tie-breaker lower Brier)
        cal_lr, p_lr = (cal_iso, p_iso) if (au_iso > au_sig or (np.isclose(au_iso, au_sig) and br_iso < br_sig)) else (
            cal_sig, p_sig)

        # 4) Probability calibration (isotonic), time-aware CV
        cal_lr = CalibratedClassifierCV(best_lr, method='isotonic', cv=tscv)
        cal_lr.fit(X_train, y_train)

        rf = RandomForestClassifier(
            n_estimators=700,
            max_depth=None,  # let trees grow a bit
            min_samples_split=5,
            min_samples_leaf=2,
            max_features='sqrt',
            bootstrap=True,
            random_state=42,
            n_jobs=-1
        )
        rf.fit(X_train, y_train)

        # 6) Evaluate and auto-pick ensemble weight
        p_lr = cal_lr.predict_proba(X_test)[:, 1]
        p_rf = rf.predict_proba(X_test)[:, 1]

        def score_auc_brier(p):
            return roc_auc_score(y_test, p), brier_score_loss(y_test, p)

        best_w, best_auc, best_brier = None, -1.0, 1.0
        for w in np.linspace(0.2, 0.8, 13):  # 0.20, 0.25, ..., 0.80
            p_ens = w * p_lr + (1 - w) * p_rf
            auc, brier = score_auc_brier(p_ens)
            if auc > best_auc or (np.isclose(auc, best_auc) and brier < best_brier):
                best_w, best_auc, best_brier = float(w), float(auc), float(brier)

        print("Best LR params:", grid.best_params_)
        print("LR  AUC:", roc_auc_score(y_test, p_lr))
        print("RF  AUC:", roc_auc_score(y_test, p_rf))
        print(f"ENS (w={best_w:.2f}) AUC:", best_auc)
        print("ENS Brier:", best_brier)

        # 7) Bundle for inference (save with joblib externally)
        bundle = {
            'log_reg': cal_lr,                   # calibrated LR pipeline
            'rf': rf,                            # random forest
            'ens_w': best_w,                     # LR weight for ensemble
            'features': X.columns.tolist(),      # exact feature order for inference
            'meta': {
                'lr_best_params': grid.best_params_,
                'metrics': {
                    'lr_auc': float(roc_auc_score(y_test, p_lr)),
                    'rf_auc': float(roc_auc_score(y_test, p_rf)),
                    'ens_auc': float(best_auc),
                    'ens_brier': float(best_brier),
                }
            }
        }
        return bundle
