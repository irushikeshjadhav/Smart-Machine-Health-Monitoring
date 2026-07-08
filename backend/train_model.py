import numpy as np
import joblib
from sklearn.ensemble import IsolationForest
from feature_extraction import extract_features

X_baseline = extract_features("baseline_normal.csv")

model = IsolationForest(n_estimators=200, contamination=0.03, random_state=42)
model.fit(X_baseline)

scores = model.decision_function(X_baseline)
joblib.dump(model, "isolation_forest_model.pkl")
np.save("score_range.npy", np.array([scores.min(), scores.max()]))
print(f"Trained on {len(X_baseline)} windows. Baseline score range: {scores.min():.3f} to {scores.max():.3f}")