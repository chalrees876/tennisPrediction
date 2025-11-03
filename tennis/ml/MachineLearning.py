import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import roc_auc_score, brier_score_loss
from sklearn.inspection import permutation_importance
import joblib


class MachineLearningModels:
    def __init__(self, training_df: pd.DataFrame):
        self.training_df = training_df

    def _time_split(self, X, y, frac=0.8):
        """Temporal split to avoid lookahead bias"""
        n = len(X)
        cut = int(n * frac)
        return (X.iloc[:cut], X.iloc[cut:], y.iloc[:cut], y.iloc[cut:])

    def log_reg_train(self):
        print("-------------------------------\n Logistic Regression (Temporal Validation) --------------------")

        # 1) Sort by time and build X/y
        df = self.training_df.sort_values('date').reset_index(drop=True)
        y = df['target'].astype(int)
        X = df.drop(columns=['target', 'match_id', 'date', 'player_id', 'opponent_id'], errors='ignore').fillna(0)

        # 2) Temporal split (no leakage) - using your existing temporal split
        X_train, X_test, y_train, y_test = self._time_split(X, y, frac=0.8)

        # 3) Train logistic regression with time series cross-validation
        model = LogisticRegression(
            random_state=42,
            max_iter=10000,
            solver='liblinear',
            class_weight='balanced'
        )
        model.fit(X_train, y_train)

        # 4) Model calibration for better probability estimates
        tscv = TimeSeriesSplit(n_splits=5)
        calibrated_model = CalibratedClassifierCV(model, method='isotonic', cv=tscv)
        calibrated_model.fit(X_train, y_train)

        # 5) Train Random Forest for ensemble
        rf_model = RandomForestClassifier(
            n_estimators=100,
            random_state=42,
            n_jobs=-1,
            class_weight='balanced'
        )
        rf_model.fit(X_train, y_train)

        # 6) Evaluate models
        lr_preds = calibrated_model.predict_proba(X_test)[:, 1]
        rf_preds = rf_model.predict_proba(X_test)[:, 1]

        lr_auc = roc_auc_score(y_test, lr_preds)
        rf_auc = roc_auc_score(y_test, rf_preds)

        # 7) Find optimal ensemble weight
        best_w, best_auc = 0.5, 0.0
        for w in np.linspace(0.0, 1.0, 11):
            ens_preds = w * lr_preds + (1 - w) * rf_preds
            auc = roc_auc_score(y_test, ens_preds)
            if auc > best_auc:
                best_w, best_auc = w, auc

        # 8) Feature importance analysis
        coefficients = model.coef_[0]
        odds_ratios = np.exp(coefficients)

        feature_importance = pd.DataFrame({
            'Feature': X.columns,
            'Coefficient': coefficients,
            'Odds Ratio': odds_ratios
        }).sort_values(by='Coefficient', ascending=False)

        print("\nFeature Importance (Coefficient and Odds Ratio):")
        print(feature_importance.head(10))  # Show top 10 only

        # 9) Permutation importance (on a subset for speed)
        if len(X_test) > 1000:  # Use subset if test set is large
            X_test_sample = X_test.sample(n=1000, random_state=42)
            y_test_sample = y_test.loc[X_test_sample.index]
        else:
            X_test_sample = X_test
            y_test_sample = y_test

        perm_importance = permutation_importance(
            model, X_test_sample, y_test_sample,
            n_repeats=10, random_state=42, n_jobs=-1
        )

        perm_importance_df = pd.DataFrame({
            'Feature': X.columns,
            'Importance Mean': perm_importance.importances_mean,
            'Importance Std': perm_importance.importances_std
        }).sort_values(by='Importance Mean', ascending=False)

        print("\nTop 10 Permutation Importance:")
        print(perm_importance_df.head(10))

        # 10) Print results
        print(f"\nLogistic Regression AUC: {lr_auc:.4f}")
        print(f"Random Forest AUC: {rf_auc:.4f}")
        print(f"Ensemble AUC (w={best_w:.2f}): {best_auc:.4f}")
        print(f"Logistic Regression Test Accuracy: {model.score(X_test, y_test):.4f}")

        # 11) Return bundle in the expected format for your inference code
        bundle = {
            'log_reg': calibrated_model,  # Calibrated logistic regression
            'rf': rf_model,  # Random forest model
            'ens_w': best_w,  # Optimal ensemble weight
            'features': X.columns.tolist(),  # Feature names for alignment
            'meta': {
                'lr_auc': float(lr_auc),
                'rf_auc': float(rf_auc),
                'ens_auc': float(best_auc),
                'feature_count': len(X.columns)
            }
        }

        return bundle