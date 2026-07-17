import pandas as pd

statcast = pd.read_csv("data/statcast_2026.csv")
pitchers = pd.read_csv("data/starting_pitchers.csv")

print("statcast dtypes for relevant columns:")
print(statcast[["game_pk", "pitcher", "home_team", "away_team", "inning_topbot"]].dtypes)

print("\nstarting_pitchers dtypes:")
print(pitchers[["game_pk", "home_pitcher_id", "away_pitcher_id"]].dtypes)

starter_ids = pd.concat([
    pitchers[["game_pk", "home_pitcher_id"]].rename(columns={"home_pitcher_id": "pitcher"}),
    pitchers[["game_pk", "away_pitcher_id"]].rename(columns={"away_pitcher_id": "pitcher"}),
])
starter_ids["is_starter"] = True

print(f"\nstarter_ids shape: {starter_ids.shape}")
print(f"starter_ids columns: {list(starter_ids.columns)}")
print(f"Any duplicate (game_pk, pitcher) pairs? {starter_ids.duplicated(subset=['game_pk', 'pitcher']).sum()}")

df = statcast.merge(starter_ids, on=["game_pk", "pitcher"], how="left")
print(f"\nAfter merge, df columns: {list(df.columns)}")
print(f"df shape after merge: {df.shape}")
print(f"df['is_starter'] dtype: {df['is_starter'].dtype}")