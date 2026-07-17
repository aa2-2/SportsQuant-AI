"""
Tests whether the improved weather features actually help, before
trusting them — same empirical pattern as every other feature decision
in this project.

Variants compared (everything else identical):
  A) temp + raw wind_speed        (the old features)
  B) temp + signed_wind           (direction-aware wind)
  C) temp + signed_wind + dome    (B plus the dome-game flag)
  D) no weather at all            (baseline — is weather helping, period?)

Run AFTER rebuilding features (build_features_all_seasons.py), since
signed_wind only exists in the rebuilt CSV.
"""
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from config import DATA_DIR, FEATURE_COLUMNS, TARGET_COLUMN

WEATHER_COLUMNS = {"temp", "wind_speed", "signed_wind", "is_dome_game"}

df = pd.read_csv(DATA_DIR / "games_with_features_all_seasons.csv")
df["date"] = pd.to_datetime(df["date"])
df["is_dome_game"] = df["is_dome_game"].astype(int)

base = [c for c in FEATURE_COLUMNS if c not in WEATHER_COLUMNS]

variants = [
    ("A) temp + raw wind_speed (old)", base + ["temp", "wind_speed"]),
    ("B) temp + signed_wind", base + ["temp", "signed_wind"]),
    ("C) temp + signed_wind + dome", base + ["temp", "signed_wind", "is_dome_game"]),
    ("D) no weather features", base),
]

y = df[TARGET_COLUMN]
tscv = TimeSeriesSplit(n_splits=5)

for name, features in variants:
    X = df[features]

    lr = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
    lr_scores = cross_val_score(lr, X, y, cv=tscv)

    rf_scores = cross_val_score(
        RandomForestClassifier(n_estimators=100, max_depth=3, min_samples_leaf=20, random_state=42),
        X, y, cv=tscv,
    )

    print(f"\n{name} ({len(features)} features)")
    print(f"  Logistic Regression CV: {lr_scores.mean():.3f} (+/- {lr_scores.std():.3f})")
    print(f"  Random Forest CV:       {rf_scores.mean():.3f} (+/- {rf_scores.std():.3f})")
