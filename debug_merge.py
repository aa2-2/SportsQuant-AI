import pandas as pd
import numpy as np

print("Debugging the merge issue...")

# Load a small sample to see what's happening
statcast_sample = pd.read_csv("data/statcast_2026.csv").head(10)
print("Sample Statcast columns:")
print(list(statcast_sample.columns))

# Check what team columns exist
team_cols = [col for col in statcast_sample.columns if 'team' in col.lower()]
print(f"Team columns in Statcast: {team_cols}")

# Look at the first row to see what's there
if len(statcast_sample) > 0:
    row = statcast_sample.iloc[0]
    print(f"\nFirst row values:")
    for col in team_cols:
        if col in row:
            print(f"  {col}: {row[col]}")