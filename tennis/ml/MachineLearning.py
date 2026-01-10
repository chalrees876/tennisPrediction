import pandas as pd
import numpy as np
from sklearn import metrics
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import roc_auc_score, brier_score_loss
from sklearn.inspection import permutation_importance
import joblib
from tennis.models import MatchFeatures


class MachineLearningModels:
    
    FEATURE_FIELDS = [
        'h2h_win_ratio_diff',
        'h2h_recent_momentum',
        'recent_form_diff',
        'win_rate_diff',
        'serve_rating_diff',
        'bp_conv_pctg_diff',
        'dom_ratio_diff',
        'fatigue_diff',
        'match_volume_14d_diff',
        'win_rate_hard_diff',
        'win_rate_clay_diff',
        'win_rate_grass_diff',
    ]

    def __init__(self, queryset=None):
        """
        Initialize with optional queryset filter.
        If None, uses all MatchTrainingData with valid targets.
        """
        if queryset is None:
            self.queryset = MatchFeatures.objects.filter(
                match__won__isnull=False
            ).select_related('match').order_by('match__date')
        else:
            self.queryset = queryset.order_by('match__date')

    def _load_data(self):
        """Load features and target from Django models into numpy arrays."""
        data = list(self.queryset.values(
            'match__date',
            'match_id',
            'player_won',
            *self.FEATURE_FIELDS
        ))
        
        if not data:
            raise ValueError("No training data found")
        
        n = len(data)
        n_features = len(self.FEATURE_FIELDS)
        
        X = np.zeros((n, n_features), dtype=np.float32)
        y = np.zeros(n, dtype=np.int32)
        
        for i, row in enumerate(data):
            y[i] = int(row['player_won'])
            for j, field in enumerate(self.FEATURE_FIELDS):
                val = row[field]
                X[i, j] = float(val) if val is not None else 0.0
                
        df = pd.DataFrame(X, columns=self.FEATURE_FIELDS)
        
        return df, y

    def log_reg_train(self):
        print("-------------------------------\n Logistic Regression (Temporal Validation) --------------------")

        # 1) Load data from Django models (already sorted by date in queryset)
        X, y = self._load_data()
        print(f"Loaded {len(y)} training samples with {len(self.FEATURE_FIELDS)} features")

        # 2) Temporal train/test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.20, random_state=42, shuffle=False  # No shuffle for temporal split
        )

        # 3) Train Logistic Regression
        model = LogisticRegression(
            random_state=42,
            max_iter=10000,
            solver='liblinear',
            class_weight='balanced'
        )
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        cnf_matrix = metrics.confusion_matrix(y_test, y_pred)
        print("Confusion matrix:\n", cnf_matrix)

        # 4) Model calibration for better probability estimates
        tscv = TimeSeriesSplit(n_splits=5)
        calibrated_model = CalibratedClassifierCV(model, method='isotonic', cv=tscv)
        calibrated_model.fit(X_train, y_train)
        calibrated_cnf_matrix = metrics.confusion_matrix(y_test, calibrated_model.predict(X_test))
        print("Calibrated confusion matrix:\n", calibrated_cnf_matrix)

        # 5) Train Random Forest for ensemble
        rf_model = RandomForestClassifier(
            n_estimators=100,
            random_state=42,
            n_jobs=-1,
            class_weight='balanced'
        )
        rf_model.fit(X_train, y_train)
        rf_confusion_matrix = metrics.confusion_matrix(y_test, rf_model.predict(X_test))
        print(f"Random forest classifier confusion matrix:\n{rf_confusion_matrix}")

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

        print("\nFeature Importance (Coefficient and Odds Ratio):")
        for i, field in enumerate(self.FEATURE_FIELDS):
            print(f"  {field}: coef={coefficients[i]:.4f}, odds_ratio={odds_ratios[i]:.4f}")

        # 9) Permutation importance (on a subset for speed)
        if len(X_test) > 1000:
            indices = np.random.RandomState(42).choice(len(X_test), 1000, replace=False)
            X_test_sample = X_test[indices]
            y_test_sample = y_test[indices]
        else:
            X_test_sample = X_test
            y_test_sample = y_test

        perm_importance = permutation_importance(
            model, X_test_sample, y_test_sample,
            n_repeats=10, random_state=42, n_jobs=-1
        )

        print("\nTop 10 Permutation Importance:")
        importance_order = np.argsort(perm_importance.importances_mean)[::-1]
        for idx in importance_order[:10]:
            print(f"  {self.FEATURE_FIELDS[idx]}: {perm_importance.importances_mean[idx]:.4f} +/- {perm_importance.importances_std[idx]:.4f}")

        # 10) Print results
        print(f"\nLogistic Regression AUC: {lr_auc:.4f}")
        print(f"Random Forest AUC: {rf_auc:.4f}")
        print(f"Ensemble AUC (w={best_w:.2f}): {best_auc:.4f}")
        print(f"Logistic Regression Test Accuracy: {model.score(X_test, y_test):.4f}")

        # 11) Return bundle for inference
        bundle = {
            'log_reg': calibrated_model,
            'rf': rf_model,
            'ens_w': best_w,
            'features': self.FEATURE_FIELDS,
            'meta': {
                'lr_auc': float(lr_auc),
                'rf_auc': float(rf_auc),
                'ens_auc': float(best_auc),
                'feature_count': len(self.FEATURE_FIELDS),
                'training_samples': len(y),
            }
        }

        return bundle
    
    def save_model(self, bundle, path='tennis_model.joblib'):
        """Save trained model bundle to disk."""
        joblib.dump(bundle, path)
        print(f"Model saved to {path}")

    @staticmethod
    def load_model(path='tennis_model.joblib'):
        """Load trained model bundle from disk."""
        return joblib.load(path)

    def predict_match(self, bundle, match_training_data):
        """
        Predict outcome for a single match using the trained ensemble.
        
        Args:
            bundle: Trained model bundle from log_reg_train()
            match_training_data: MatchTrainingData instance
        
        Returns:
            dict with prediction probabilities
        """
        # Build feature vector
        X = np.zeros((1, len(self.FEATURE_FIELDS)), dtype=np.float32)
        for j, field in enumerate(self.FEATURE_FIELDS):
            val = getattr(match_training_data, field, None)
            X[0, j] = float(val) if val is not None else 0.0

        # Get predictions from both models
        lr_prob = bundle['log_reg'].predict_proba(X)[0, 1]
        rf_prob = bundle['rf'].predict_proba(X)[0, 1]
        
        # Ensemble prediction
        w = bundle['ens_w']
        ens_prob = w * lr_prob + (1 - w) * rf_prob

        return {
            'player_win_prob': float(ens_prob),
            'opponent_win_prob': float(1 - ens_prob),
            'lr_prob': float(lr_prob),
            'rf_prob': float(rf_prob),
        }
        
    def generate_all_predictions(self, bundle=None, model_path='tennis_model.joblib', 
                                  queryset=None, verbose=True):
        """
        Generate predictions for all MatchFeatures and save to database.
        
        Args:
            bundle: Pre-loaded model bundle (optional)
            model_path: Path to model file if bundle not provided
            queryset: Optional queryset to filter which matches to predict
            verbose: Print progress updates
        
        Returns:
            dict with success/error counts
        """
        # Load model if not provided
        if bundle is None:
            try:
                bundle = self.load_model(model_path)
                if verbose:
                    print(f"Model loaded from {model_path}")
            except FileNotFoundError:
                raise FileNotFoundError(f"Model file not found at {model_path}. Run training first.")

        # Get queryset
        if queryset is None:
            queryset = MatchFeatures.objects.select_related('match').all()
        
        total = queryset.count()
        if verbose:
            print(f"Generating predictions for {total} matches...")

        success_count = 0
        error_count = 0

        for i, mf in enumerate(queryset.iterator()):
            try:
                # Build feature vector
                X = np.zeros((1, len(self.FEATURE_FIELDS)), dtype=np.float32)
                for j, field in enumerate(self.FEATURE_FIELDS):
                    val = getattr(mf, field, None)
                    X[0, j] = float(val) if val is not None else 0.0

                # Get predictions
                lr_prob = bundle['log_reg'].predict_proba(X)[0, 1]
                rf_prob = bundle['rf'].predict_proba(X)[0, 1]
                
                # Ensemble
                w = bundle['ens_w']
                ens_prob = w * lr_prob + (1 - w) * rf_prob

                # Save prediction
                mf.player_win_prob = float(ens_prob)
                mf.save(update_fields=['player_win_prob'])
                
                success_count += 1

                if verbose and (i + 1) % 500 == 0:
                    print(f"Processed {i + 1}/{total}...")

            except Exception as e:
                if verbose:
                    print(f"Error on MatchFeatures {mf.id}: {e}")
                error_count += 1

        if verbose:
            print(f"\nDone: {success_count} predictions generated, {error_count} errors")

        return {
            'success': success_count,
            'errors': error_count,
            'total': total
        }

    def generate_predictions_for_upcoming(self, bundle=None, model_path='tennis_model.joblib', 
                                           verbose=True):
        """
        Generate predictions only for upcoming (not completed) matches.
        
        Args:
            bundle: Pre-loaded model bundle (optional)
            model_path: Path to model file if bundle not provided
            verbose: Print progress updates
        
        Returns:
            dict with success/error counts
        """
        queryset = MatchFeatures.objects.filter(
            match__completed=False
        ).select_related('match')
        
        return self.generate_all_predictions(
            bundle=bundle,
            model_path=model_path,
            queryset=queryset,
            verbose=verbose
        )

    def generate_predictions_missing(self, bundle=None, model_path='tennis_model.joblib',
                                      verbose=True):
        """
        Generate predictions only for matches missing player_win_prob.
        
        Args:
            bundle: Pre-loaded model bundle (optional)
            model_path: Path to model file if bundle not provided
            verbose: Print progress updates
        
        Returns:
            dict with success/error counts
        """
        queryset = MatchFeatures.objects.filter(
            player_win_prob__isnull=True
        ).select_related('match')
        
        return self.generate_all_predictions(
            bundle=bundle,
            model_path=model_path,
            queryset=queryset,
            verbose=verbose
        )