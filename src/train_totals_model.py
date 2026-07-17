"""
Trains the run-TOTALS model: predicts a game's combined runs from the
same 25 leakage-safe features as the win model.

The prediction alone isn't enough to bet on — comparing "model 8.2 vs
line 7.5" needs a PROBABILITY that the total goes over. That comes
from the model's own measured uncertainty: the standard deviation of
its errors on held-out 2026 games (sigma). Assuming roughly normal
errors, P(over line) = 1 - CDF((line - prediction) / sigma).

That normal-error assumption is exactly the extra leap of faith the
totals ledger exists to test — if totals bets underperform their
logged probabilities, this is the first suspect.

Run once (and again after any feature rebuild):
    python src/train_totals_model.py

Saves data/totals_model.joblib: {model, scaler, sigma, mae, features}.
"""
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from config import DATA_DIR, TOTALS_FEATURE_COLUMNS

CUTOFF_DATE = "2026-03-25"  # same holdout split as the win model


if __name__ == "__main__":
    df = pd.read_csv(DATA_DIR / "games_with_features_all_seasons.csv")
    df["date"] = pd.to_datetime(df["date"])

    if "home_score" not in df.columns or "away_score" not in df.columns:
        raise SystemExit(
            "Scores not found in the features CSV — re-run "
            "build_features_all_seasons.py first."
        )

    df["total_runs"] = df["home_score"] + df["away_score"]
    missing = [c for c in TOTALS_FEATURE_COLUMNS if c not in df.columns]
    if missing:
        raise SystemExit(
            f"Missing totals features {missing} — re-run "
            "build_features_all_seasons.py first (run-environment features are new)."
        )
    X, y = df[TOTALS_FEATURE_COLUMNS], df["total_runs"]

    print(f"Training totals model on {len(df)} games")
    print(f"Average total: {y.mean():.2f} runs (std {y.std():.2f})")

    ridge = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
    forest = RandomForestRegressor(
        n_estimators=200, max_depth=5, min_samples_leaf=25, random_state=42
    )

    tscv = TimeSeriesSplit(n_splits=5)
    print("\n5-fold time-series CV (mean absolute error, lower is better):")
    candidates = {}
    for name, est in [("Ridge regression", ridge), ("Random forest", forest)]:
        mae_scores = -cross_val_score(est, X, y, cv=tscv, scoring="neg_mean_absolute_error")
        candidates[name] = (est, mae_scores.mean())
        print(f"  {name}: MAE {mae_scores.mean():.3f} (+/- {mae_scores.std():.3f})")

    # naive baseline: always predict the training-period average total
    baseline_mae = (y - y.mean()).abs().mean()
    print(f"  Baseline (always predict the average): MAE {baseline_mae:.3f}")

    best_name = min(candidates, key=lambda k: candidates[k][1])
    best_est, best_mae = candidates[best_name]
    print(f"\nSelected: {best_name}")
    if best_mae >= baseline_mae:
        print("WARNING: model does not beat the always-average baseline — "
              "totals edges from this model should not be trusted.")

    # Holdout fit: measure sigma on 2026 games the model never saw,
    # then refit on everything for production.
    train = df[df["date"] < CUTOFF_DATE]
    test = df[df["date"] >= CUTOFF_DATE]
    best_est.fit(train[TOTALS_FEATURE_COLUMNS], train["total_runs"])
    residuals = test["total_runs"] - best_est.predict(test[TOTALS_FEATURE_COLUMNS])
    sigma = float(residuals.std())
    holdout_mae = float(residuals.abs().mean())
    print(f"2026 holdout ({len(test)} games): MAE {holdout_mae:.3f}, "
          f"residual sigma {sigma:.3f}")

    best_est.fit(X, y)

    bundle = {
        "model": best_est,
        "model_name": best_name,
        "sigma": sigma,
        "holdout_mae": holdout_mae,
        "cv_mae": float(best_mae),
        "baseline_mae": float(baseline_mae),
        "features": TOTALS_FEATURE_COLUMNS,
    }
    joblib.dump(bundle, DATA_DIR / "totals_model.joblib")
    print(f"\nSaved to {DATA_DIR / 'totals_model.joblib'}")
