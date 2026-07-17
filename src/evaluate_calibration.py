import pandas as pd
import numpy as np
import joblib
from sklearn.metrics import log_loss, brier_score_loss

from config import FEATURE_COLUMNS

df = pd.read_csv("data/games_with_features_all_seasons.csv")
df["date"] = pd.to_datetime(df["date"])

model = joblib.load("data/calibrated_model.joblib")
scaler = joblib.load("data/feature_scaler.joblib")

cutoff = pd.to_datetime("2026-03-25")
test_df = df[df["date"] >= cutoff].copy()

X_test = test_df[FEATURE_COLUMNS]
y_test = test_df["home_win"]

X_test_scaled = scaler.transform(X_test)
predicted_probs = model.predict_proba(X_test_scaled)[:, 1]

print(f"Test set: {len(test_df)} games\n")

ll = log_loss(y_test, predicted_probs)
brier = brier_score_loss(y_test, predicted_probs)

print(f"Log loss: {ll:.4f}  (lower is better; 0 = perfect, ~0.693 = random guessing at 50%)")
print(f"Brier score: {brier:.4f}  (lower is better; 0 = perfect, 0.25 = always guessing 50%)")

test_df["predicted_prob"] = predicted_probs

bins = [0, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 1.0]
labels = ["<45%", "45-50%", "50-55%", "55-60%", "60-65%", "65-70%", "70%+"]
test_df["prob_bucket"] = pd.cut(test_df["predicted_prob"], bins=bins, labels=labels)

calibration_table = test_df.groupby("prob_bucket", observed=True).agg(
    games=("home_win", "count"),
    actual_home_win_rate=("home_win", "mean"),
    avg_predicted_prob=("predicted_prob", "mean"),
).reset_index()

calibration_table["gap"] = calibration_table["actual_home_win_rate"] - calibration_table["avg_predicted_prob"]

print("\nCalibration table (predicted vs. actual):")
print(calibration_table.to_string(index=False))

print("\nHow to read this: 'gap' close to 0 means well-calibrated.")
print("A large positive gap means the model is UNDER-confident in that range.")
print("A large negative gap means the model is OVER-confident in that range.")