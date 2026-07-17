import pandas as pd
from features.batter_vs_pitcher import build_matchup_history

paths = ["data/statcast_2024.csv", "data/statcast_2025.csv", "data/statcast_2026.csv"]
history = build_matchup_history(paths)

print(f"Total plate-appearance rows: {len(history)}")
print(f"\nSample:\n{history.head(10).to_string(index=False)}")
print(f"\nUnique batter-pitcher pairs: {history.groupby(['batter', 'pitcher']).ngroups}")