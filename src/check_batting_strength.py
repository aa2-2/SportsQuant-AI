import pandas as pd
from features.batting_strength import add_batting_strength

games = pd.read_csv("data/games_2026.csv")
statcast = pd.read_csv("data/statcast_2026.csv")

result = add_batting_strength(games, statcast)

print(f"Total games: {len(result)}")

cols = [
    "date", "home_team", "home_team_avg_exit_velo", "home_team_hr_rate", "home_team_k_rate",
    "away_team", "away_team_avg_exit_velo", "away_team_hr_rate", "away_team_k_rate",
]
print(f"\nFirst 5 games (should show neutral defaults - 88.0, 0.03, 0.22):")
print(result[cols].head(5).to_string(index=False))

print(f"\nLast 5 games (should show real, varied values):")
print(result[cols].tail(5).to_string(index=False))

print(f"\nAny missing values in new columns?")
new_cols = ["home_team_avg_exit_velo", "home_team_hr_rate", "home_team_k_rate",
            "away_team_avg_exit_velo", "away_team_hr_rate", "away_team_k_rate"]
print(result[new_cols].isnull().sum())