import pybaseball

# Pull one day of real Statcast pitch-by-pitch data as a test
data = pybaseball.statcast(start_dt="2026-04-01", end_dt="2026-04-01")

print(f"Total pitches: {len(data)}")
print(f"\nColumns available:\n{list(data.columns)}")
print(f"\nSample row:\n{data.iloc[0]}")