import pandas as pd
from features.batter_power import add_batter_power

games = pd.read_csv("data/games_2026.csv")
statcast = pd.read_csv("data/statcast_2026.csv")

result = add_batter_power(games, statcast)

print(f"Total games: {len(result)}")

cols = [
    "date", "home_team", "home_team_top_power_exit_velo", "home_team_top_power_hr_rate",
    "away_team", "away_team_top_power_exit_velo", "away_team_top_power_hr_rate",
]

print(f"\nFirst 5 games (should show neutral defaults - 88.0, 0.03):")
print(result[cols].head(5).to_string(index=False))

print(f"\nLast 10 games (should show real, varied values):")
print(result[cols].tail(10).to_string(index=False))

print(f"\nAny missing values?")
new_cols = [c for c in cols if c not in ["date", "home_team", "away_team"]]
print(result[new_cols].isnull().sum())