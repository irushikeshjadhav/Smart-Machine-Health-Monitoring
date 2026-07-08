import joblib
from feature_extraction import extract_features

model = joblib.load("isolation_forest_model.pkl")
X_fault = extract_features("fault_imbalance.csv")

scores = model.decision_function(X_fault)
predictions = model.predict(X_fault)
print(f"Fault scores — min/mean/max: {scores.min():.3f} / {scores.mean():.3f} / {scores.max():.3f}")
print(f"Fraction flagged anomalous: {(predictions == -1).mean()*100:.1f}%")