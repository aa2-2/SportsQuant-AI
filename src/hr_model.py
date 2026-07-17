"""
Runtime helpers for the game-level HR projection model.
Same trust pattern as totals: the bundle carries its own validation
report card, and projections only display from a model that beat its
baseline.
"""
import joblib

from config import DATA_DIR, HR_FEATURE_COLUMNS

HR_MODEL_PATH = DATA_DIR / "hr_model.joblib"


def load_hr_model():
    if not HR_MODEL_PATH.exists():
        return None
    return joblib.load(HR_MODEL_PATH)


def hr_model_trusted(bundle):
    return bundle.get("cv_mae", float("inf")) < bundle.get("baseline_mae", 0.0)


def predict_game_hrs(bundle, win_feature_row):
    """
    Projected total HRs for a game. Every HR feature is already present
    in the win model's feature row, so the HR row is a column subset —
    one recipe, no train/serve drift for this model.
    """
    hr_row = win_feature_row[HR_FEATURE_COLUMNS]
    return float(bundle["model"].predict(hr_row)[0])
