# export_model.py
import json
import joblib
model = joblib.load("models/logreg.joblib")
payload = {
  "intercept": float(model.intercept_[0]),
  "coef": [float(c) for c in model.coef_[0]],  # order: [first_serve_pctg, double_faults]
  "feature_order": ["first_serve_pctg", "double_faults"]
}
open("../docs/model.json", "w").write(json.dumps(payload))
print("Wrote docs/model.json")
