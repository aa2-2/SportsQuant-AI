import pandas as pd

df = pd.read_csv("data/games_with_features_all_seasons.csv")

FEATURE_COLUMNS = [
    "home_team_run_diff", "away_team_run_diff", "home_pitcher_era", "away_pitcher_era",
    "home_pitcher_whiff_rate", "away_pitcher_whiff_rate", "hr_park_factor", "temp", "wind_speed",
    "home_team_avg_exit_velo", "away_team_avg_exit_velo", "home_team_hr_rate", "away_team_hr_rate",
    "home_team_k_rate", "away_team_k_rate", "home_team_top_power_exit_velo",
    "away_team_top_power_exit_velo", "home_team_top_power_hr_rate", "away_team_top_power_hr_rate",
    "home_pitcher_vs_opp_era", "away_pitcher_vs_opp_era",
    "home_team_vs_away_pitcher_avg", "away_team_vs_home_pitcher_avg",
]

print("Missing values per feature column:")
print(df[FEATURE_COLUMNS].isnull().sum())