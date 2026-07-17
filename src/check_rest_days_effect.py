import pandas as pd
import joblib

FEATURE_COLUMNS = [
    "home_team_pre_game_win_pct", "away_team_pre_game_win_pct",
    "home_team_recent_form", "away_team_recent_form",
    "home_team_run_diff", "away_team_run_diff",
    "home_team_rest_days", "away_team_rest_days",
    "home_pitcher_era", "away_pitcher_era",
    "park_factor", "temp", "wind_speed",
]

model = joblib.load("data/trained_model.joblib")
scaler = joblib.load("data/feature_scaler.joblib")

# One made-up, perfectly even matchup — identical stats for both teams
# in every way EXCEPT we'll vary rest_days to isolate its effect alone.
base_row = {
    "home_team_pre_game_win_pct": 0.5,
    "away_team_pre_game_win_pct": 0.5,
    "home_team_recent_form": 0.5,
    "away_team_recent_form": 0.5,
    "home_team_run_diff": 0.0,
    "away_team_run_diff": 0.0,
    "home_pitcher_era": 4.0,
    "away_pitcher_era": 4.0,
    "park_factor": 1.0,
    "temp": 75.0,
    "wind_speed": 0.0,
}

for rest_value in [1, 2, 4]:
    row = base_row.copy()
    row["home_team_rest_days"] = rest_value
    row["away_team_rest_days"] = rest_value
    df_row = pd.DataFrame([row])[FEATURE_COLUMNS]
    scaled = scaler.transform(df_row)
    prob = model.predict_proba(scaled)[0][1]
    print(f"Both teams at {rest_value} rest days -> home win probability: {prob:.1%}")