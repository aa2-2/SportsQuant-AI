import pandas as pd
from features.bullpen_strength import add_bullpen_strength

games = pd.read_csv("data/games_2026.csv")
statcast = pd.read_csv("data/statcast_2026.csv")
pitchers = pd.read_csv("data/starting_pitchers.csv")

result = add_bullpen_strength(games, statcast, pitchers)

print(f"Total games: {len(result)}")

cols = ["date", "home_team", "home_team_bullpen_exit_velo", "home_team_bullpen_barrel_rate",
        "away_team", "away_team_bullpen_exit_velo", "away_team_bullpen_barrel_rate"]

print(f"\nFirst 5 games (should show neutral defaults - 88.0, 0.08):")
print(result[cols].head(5).to_string(index=False))

print(f"\nLast 10 games (should show real, varied values):")
print(result[cols].tail(10).to_string(index=False))

print(f"\nAny missing values?")
new_cols = [c for c in cols if c not in ["date", "home_team", "away_team"]]
print(result[new_cols].isnull().sum())