"""
Runtime helpers for the totals model.

Converts a predicted run total and a market line into P(over) using
the model's measured error distribution (sigma from the 2026 holdout,
saved at training time). See train_totals_model.py for the caveats.
"""
import math

import joblib

from config import DATA_DIR

TOTALS_MODEL_PATH = DATA_DIR / "totals_model.joblib"


def load_totals_model():
    """Returns the saved bundle, or None if not trained yet."""
    if not TOTALS_MODEL_PATH.exists():
        return None
    return joblib.load(TOTALS_MODEL_PATH)


def totals_model_trusted(bundle):
    """
    True only if the model beat the always-predict-the-average baseline
    in CV at training time. A totals model that can't beat the naive
    baseline produces per-game "edges" that are pure noise — the system
    refuses to log bets from it, automatically.
    """
    return bundle.get("cv_mae", float("inf")) < bundle.get("baseline_mae", 0.0)


def predict_total(bundle, feature_row):
    """Predicted combined runs for one game's feature row."""
    return float(bundle["model"].predict(feature_row)[0])


def prob_over(predicted_total, line, sigma):
    """
    P(actual total > line) assuming normally distributed model errors.
    Uses the standard normal CDF via erf — no scipy dependency.
    """
    z = (line - predicted_total) / sigma
    cdf = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
    return 1.0 - cdf
