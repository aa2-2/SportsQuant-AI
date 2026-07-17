import pandas as pd
from features.batting_strength import build_team_game_batting

statcast = pd.read_csv("data/statcast_2026.csv")
team_batting = build_team_game_batting(statcast)

# Check 1: are any games producing more than 2 team-rows?
counts = team_batting.groupby("game_pk").size()
extra_games = counts[counts != 2]
print(f"Games with NOT exactly 2 team-rows: {len(extra_games)}")
print(extra_games.head(10))

# Check 2: what do team name/abbreviation values actually look like?
print(f"\nUnique batting_team values (sample): {sorted(team_batting['batting_team'].unique())[:10]}")

games_df = pd.read_csv("data/games_2026.csv")
print(f"\nUnique home_team values in games_2026.csv (sample): {sorted(games_df['home_team'].unique())[:5]}")