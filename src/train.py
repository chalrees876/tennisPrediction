# scripts/train.py
from pathlib import Path
import joblib, pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from src.trainingModel import run_pipeline as run_pipeline

CSV = "../data/matches.csv"  # has columns: first_serve_pctg, double_faults, win

df = pd.read_csv(CSV)
X = df[["first_serve_pctg", "double_faults"]].values
y = df["win"].astype(int).values  # ensure 0/1

X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)
model = LogisticRegression(max_iter=1000, random_state=42)
model.fit(X_tr, y_tr)

Path("models").mkdir(exist_ok=True)
joblib.dump(model, "models/logreg.joblib")
print("Saved models/logreg.joblib")
