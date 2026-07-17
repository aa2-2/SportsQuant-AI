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

# Print each feature's learned coefficient — a large positive or negative
# number relative to the others suggests that feature has outsized
# influence on the prediction.
for name, coef in zip(FEATURE_COLUMNS, model.coef_[0]):
    print(f"{name}: {coef:.4f}")

print(f"\nIntercept: {model.intercept_[0]:.4f}")

# Check what the training data's rest_days actually ranged over
df = pd.read_csv("data/games_with_features.csv")
print(f"\nTraining rest_days range: min={df['home_team_rest_days'].min()}, max={df['home_team_rest_days'].max()}")
print(df["home_team_rest_days"].value_counts().sort_index())