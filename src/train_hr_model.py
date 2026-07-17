"""
Trains the game-level HOME RUN projection model: expected total HRs in
a game, from HR-relevant features (park, power, whiff, weather).

Same earn-the-slot rules as every model in this project:
  - evaluated by time-series CV against an always-predict-the-average
    baseline
  - the saved bundle carries its own report card (cv_mae vs
    baseline_mae); the display layer reads it and only shows
    projections from a model that beat its baseline

The target (total HRs per game) is counted directly from Statcast
events — no feature rebuild needed.

    python src/train_hr_model.py
"""
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from config import DATA_DIR, HR_FEATURE_COLUMNS

CUTOFF_DATE = "2026-03-25"
STATCAST_SEASONS = [2024, 2025, 2026]


def count_hrs_per_game():
    counts = []
    for year in STATCAST_SEASONS:
        print(f"Counting home runs in statcast_{year}.csv...")
        sc = pd.read_csv(DATA_DIR / f"statcast_{year}.csv", usecols=["game_pk", "events"])
        hr = (sc["events"] == "home_run").groupby(sc["game_pk"]).sum()
        counts.append(hr)
    return pd.concat(counts).rename("total_hrs")


if __name__ == "__main__":
    df = pd.read_csv(DATA_DIR / "games_with_features_all_seasons.csv")
    df["date"] = pd.to_datetime(df["date"])

    hrs = count_hrs_per_game()
    df = df.merge(hrs, left_on="game_pk", right_index=True, how="inner")

    missing = [c for c in HR_FEATURE_COLUMNS if c not in df.columns]
    if missing:
        raise SystemExit(f"Missing features {missing} — re-run build_features_all_seasons.py.")

    df = df.sort_values("date").reset_index(drop=True)
    X, y = df[HR_FEATURE_COLUMNS], df["total_hrs"]

    print(f"\nTraining HR model on {len(df)} games")
    print(f"Average HRs per game: {y.mean():.2f} (std {y.std():.2f})")

    ridge = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
    forest = RandomForestRegressor(
        n_estimators=200, max_depth=5, min_samples_leaf=25, random_state=42
    )

    tscv = TimeSeriesSplit(n_splits=5)
    print("\n5-fold time-series CV (mean absolute error, lower is better):")
    candidates = {}
    for name, est in [("Ridge regression", ridge), ("Random forest", forest)]:
        mae = -cross_val_score(est, X, y, cv=tscv, scoring="neg_mean_absolute_error")
        candidates[name] = (est, mae.mean())
        print(f"  {name}: MAE {mae.mean():.4f} (+/- {mae.std():.4f})")

    baseline_mae = (y - y.mean()).abs().mean()
    print(f"  Baseline (always predict the average): MAE {baseline_mae:.4f}")

    best_name = min(candidates, key=lambda k: candidates[k][1])
    best_est, best_mae = candidates[best_name]
    print(f"\nSelected: {best_name}")
    if best_mae >= baseline_mae:
        print("WARNING: model does not beat the always-average baseline — "
              "HR projections will stay disabled (same rule as every model here).")
    else:
        print(f"Beats baseline by {baseline_mae - best_mae:.4f} MAE — projections will display.")

    train = df[df["date"] < CUTOFF_DATE]
    test = df[df["date"] >= CUTOFF_DATE]
    best_est.fit(train[HR_FEATURE_COLUMNS], train["total_hrs"])
    residuals = test["total_hrs"] - best_est.predict(test[HR_FEATURE_COLUMNS])
    print(f"2026 holdout ({len(test)} games): MAE {residuals.abs().mean():.4f}, "
          f"residual sigma {residuals.std():.4f}")

    best_est.fit(X, y)

    joblib.dump({
        "model": best_est,
        "model_name": best_name,
        "sigma": float(residuals.std()),
        "cv_mae": float(best_mae),
        "baseline_mae": float(baseline_mae),
        "features": HR_FEATURE_COLUMNS,
    }, DATA_DIR / "hr_model.joblib")
    print(f"\nSaved to {DATA_DIR / 'hr_model.joblib'}")
