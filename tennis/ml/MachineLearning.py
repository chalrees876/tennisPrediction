import joblib
import numpy as np
import pandas as pd
from IPython.core.display_functions import display
from sklearn.inspection import permutation_importance
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, precision_score, recall_score, ConfusionMatrixDisplay
from sklearn.model_selection import RandomizedSearchCV, train_test_split
from scipy.stats import randint

# Tree Visualisation
from sklearn.tree import export_graphviz
from IPython.display import Image
import graphviz
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import TimeSeriesSplit, GridSearchCV, train_test_split
from sklearn.metrics import (
    log_loss, roc_auc_score, accuracy_score,
    precision_recall_fscore_support, confusion_matrix
)

class MachineLearningModels:
    def __init__(self, training_df):
        self.training_df = training_df

    def log_reg_train(self, features):
        # 1) Data
        print("-------------------------------\n Logistic Regression --------------------")

        df = self.training_df.sort_values('date').reset_index(drop=True)
        X = df[features]
        y = df['target'].astype(int)

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        model = LogisticRegression(random_state=42, max_iter=10000, solver='liblinear')
        model.fit(X_train, y_train)

        accuracy = model.score(X_train, y_train)
        print(f"Accuracy: {accuracy}")

        coefficients = model.coef_[0]
        odds_ratios = np.exp(coefficients)

        # Display feature importance using coefficients and odds ratios
        feature_importance = pd.DataFrame({
            'Feature': X.columns,
            'Coefficient': coefficients,
            'Odds Ratio': odds_ratios
        })
        print("\nFeature Importance (Coefficient and Odds Ratio):")
        print(feature_importance.sort_values(by='Coefficient', ascending=False))

        perm_importance = permutation_importance(model, X_test, y_test, n_repeats=30, random_state=42, n_jobs=-1)
        perm_importance_df = pd.DataFrame({
            'Feature': X.columns,
            'Importance Mean': perm_importance.importances_mean,
            'Importance Std': perm_importance.importances_std
        })
        print("\nPermutation Importance:")
        print(perm_importance_df.sort_values(by='Importance Mean', ascending=False))

        print(model.score(X_test, y_test))
        return model