import pandas as pd
from features.ballpark import add_hr_park_factor

games = pd.read_csv("data/games_2026.csv")
statcast = pd.read_csv("data/statcast_2026.csv")

result = add_hr_park_factor(games, statcast)

print("Teams with highest HR park factor (most HR-friendly):")
latest = result.sort_values("date").groupby("home_team").tail(1)
print(latest[["home_team", "hr_park_factor"]].sort_values("hr_park_factor", ascending=False).to_string(index=False))