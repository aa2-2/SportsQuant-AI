import pandas as pd

df = pd.read_csv("data/statcast_2026.csv")

print(f"Total rows: {len(df)}")
print(f"\nMissing values in key columns:")
key_cols = ["batter", "pitcher", "launch_speed", "launch_angle", "events", "stand", "p_throws", "home_team", "away_team", "game_pk"]
print(df[key_cols].isnull().sum())

print(f"\nSample of events (what happened on each pitch):")
print(df["events"].value_counts().head(15))

print(f"\nUnique batters: {df['batter'].nunique()}")
print(f"Unique pitchers: {df['pitcher'].nunique()}")