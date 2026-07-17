"""
Turns a prediction into a human-readable "why".

For a logistic regression, each feature's contribution to a single
prediction is exactly (coefficient x standardized feature value) —
positive pushes toward a home win, negative toward an away win. This
uses the RAW (uncalibrated) logistic regression for the breakdown:
calibration rescales the final probability but doesn't change which
features are driving it or in which direction.

This is deliberately simple and exact — no approximation methods
needed while the production model is linear.
"""
import joblib

from config import DATA_DIR, FEATURE_COLUMNS

READABLE_NAMES = {
    "home_team_elo": "home team Elo rating",
    "away_team_elo": "away team Elo rating",
    "home_pitcher_era": "home starter's recent ERA",
    "away_pitcher_era": "away starter's recent ERA",
    "home_pitcher_whiff_rate": "home starter's whiff rate",
    "away_pitcher_whiff_rate": "away starter's whiff rate",
    "hr_park_factor": "ballpark HR factor",
    "temp": "temperature",
    "signed_wind": "wind (out/in)",
    "home_team_avg_exit_velo": "home team exit velocity",
    "away_team_avg_exit_velo": "away team exit velocity",
    "home_team_hr_rate": "home team HR rate",
    "away_team_hr_rate": "away team HR rate",
    "home_team_k_rate": "home team strikeout rate",
    "away_team_k_rate": "away team strikeout rate",
    "home_team_top_power_exit_velo": "home top power hitters (exit velo)",
    "away_team_top_power_exit_velo": "away top power hitters (exit velo)",
    "home_team_top_power_hr_rate": "home top power hitters (HR rate)",
    "away_team_top_power_hr_rate": "away top power hitters (HR rate)",
    "home_pitcher_vs_opp_era": "home starter's history vs this opponent",
    "away_pitcher_vs_opp_era": "away starter's history vs this opponent",
    "home_team_vs_away_pitcher_avg": "home lineup's history vs away starter",
    "away_team_vs_home_pitcher_avg": "away lineup's history vs home starter",
    "home_team_bullpen_fatigue": "home bullpen fatigue",
    "away_team_bullpen_fatigue": "away bullpen fatigue",
}


def load_raw_model():
    """The uncalibrated logistic regression (has readable coefficients)."""
    return joblib.load(DATA_DIR / "trained_model.joblib")


def explain_prediction(raw_model, scaler, feature_row, top_n=3):
    """
    Returns two lists of (readable_name, contribution) tuples:
    the strongest factors pushing toward the HOME team, and toward
    the AWAY team, for this specific game.
    """
    z = scaler.transform(feature_row)[0]
    contributions = raw_model.coef_[0] * z

    pairs = sorted(
        zip(FEATURE_COLUMNS, contributions), key=lambda p: p[1], reverse=True
    )

    toward_home = [
        (READABLE_NAMES.get(name, name), value)
        for name, value in pairs[:top_n] if value > 0
    ]
    toward_away = [
        (READABLE_NAMES.get(name, name), value)
        for name, value in reversed(pairs[-top_n:]) if value < 0
    ]
    return toward_home, toward_away


def format_reasons(reasons):
    """'home team Elo rating, away starter's recent ERA' style string."""
    return ", ".join(name for name, _ in reasons) if reasons else "(none stood out)"

def full_breakdown(raw_model, scaler, feature_row):
    """
    The complete ledger for one game: every feature with its RAW value
    and its exact contribution to the home team's log-odds, sorted by
    absolute impact. Positive contribution -> pushes home, negative ->
    pushes away.
    """
    z = scaler.transform(feature_row)[0]
    contributions = raw_model.coef_[0] * z
    raw_values = feature_row.iloc[0]

    rows = []
    for name, contribution in zip(FEATURE_COLUMNS, contributions):
        rows.append({
            "feature": name,
            "readable": READABLE_NAMES.get(name, name),
            "value": float(raw_values[name]),
            "contribution": float(contribution),
        })
    return sorted(rows, key=lambda r: -abs(r["contribution"]))


def strength_label(contribution):
    """Plain-English size of a contribution (in log-odds units)."""
    size = abs(contribution)
    if size >= 0.15:
        return "strong"
    if size >= 0.07:
        return "moderate"
    return "slight"

