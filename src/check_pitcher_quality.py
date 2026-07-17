import pandas as pd
from features.pitcher_quality import add_pitcher_quality

games = pd.read_csv("data/games_2026.csv")
statcast = pd.read_csv("data/statcast_2026.csv")
pitchers = pd.read_csv("data/starting_pitchers.csv")

result = add_pitcher_quality(games, statcast, pitchers)

print(f"Total games: {len(result)}")
cols = ["date", "home_pitcher_exit_velo_allowed", "home_pitcher_barrel_rate_allowed", "home_pitcher_whiff_rate"]
print(f"\nLast 10 games:\n{result[cols].tail(10).to_string(index=False)}")
print(f"\nMissing values:\n{result[cols[1:]].isnull().sum()}")