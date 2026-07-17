import pandas as pd

pitchers = pd.read_csv("data/starting_pitchers.csv")

print(f"Total rows in starting_pitchers.csv: {len(pitchers)}")
print(f"Unique game_pk values: {pitchers['game_pk'].nunique()}")

duplicates = pitchers[pitchers.duplicated(subset="game_pk", keep=False)]
print(f"\nDuplicate rows found: {len(duplicates)}")
if len(duplicates) > 0:
    print(duplicates.sort_values("game_pk").to_string(index=False))
    