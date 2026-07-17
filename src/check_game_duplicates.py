import pandas as pd

games = pd.read_csv("data/games_2026.csv")

print(f"Total rows in games_2026.csv: {len(games)}")
print(f"Unique game_pk values: {games['game_pk'].nunique()}")

duplicates = games[games.duplicated(subset="game_pk", keep=False)]
print(f"\nDuplicate rows found: {len(duplicates)}")
if len(duplicates) > 0:
    print(duplicates.to_string(index=False))