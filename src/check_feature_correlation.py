import pandas as pd

df = pd.read_csv("data/games_with_features.csv")

FEATURE_COLUMNS = [
    "home_team_pre_game_win_pct", "away_team_pre_game_win_pct",
    "home_team_recent_form", "away_team_recent_form",
    "home_team_run_diff", "away_team_run_diff",
    "home_team_rest_days", "away_team_rest_days",
    "home_pitcher_era", "away_pitcher_era",
    "park_factor", "hr_park_factor", "temp", "wind_speed",
    "home_team_avg_exit_velo", "away_team_avg_exit_velo",
    "home_team_hr_rate", "away_team_hr_rate",
    "home_team_k_rate", "away_team_k_rate",
    "home_pitcher_exit_velo_allowed", "away_pitcher_exit_velo_allowed",
    "home_pitcher_barrel_rate_allowed", "away_pitcher_barrel_rate_allowed",
    "home_pitcher_whiff_rate", "away_pitcher_whiff_rate",
]

corr = df[FEATURE_COLUMNS].corr()

# Find pairs of features that are highly correlated with each other
# (not counting a feature's correlation with itself)
pairs = []
for i, col1 in enumerate(FEATURE_COLUMNS):
    for col2 in FEATURE_COLUMNS[i+1:]:
        pairs.append((col1, col2, corr.loc[col1, col2]))

pairs_df = pd.DataFrame(pairs, columns=["feature_1", "feature_2", "correlation"])
pairs_df["abs_correlation"] = pairs_df["correlation"].abs()
pairs_df = pairs_df.sort_values("abs_correlation", ascending=False)

print("Top 15 most correlated feature pairs (candidates for redundancy):")
print(pairs_df.head(15).to_string(index=False))