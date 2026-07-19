import pandas as pd

# Load the Statcast data for 2024-2026
print("Loading Statcast data...")
statcast_2024 = pd.read_csv("/c/Users/Alex/Desktop/SportsQuant-AI/data/statcast_2024.csv")
statcast_2025 = pd.read_csv("/c/Users/Alex/Desktop/SportsQuant-AI/data/statcast_2025.csv")
statcast_2026 = pd.read_csv("/c/Users/Alex/Desktop/SportsQuant-AI/data/statcast_2026.csv")

# Combine all years
statcast_all = pd.concat([statcast_2024, statcast_2025, statcast_2026], ignore_index=False)
print(f"Total Statcast pitches: {len(statcast_all)}")

# Filter to only plate appearances (where events is not null)
pa_data = statcast_all[statcast_all['events'].notna()].copy()
print(f"Total plate appearances: {len(pa_data)}")

# Add date column
pa_data['game_date'] = pd.to_datetime(pa_data['game_date'])

# Define team abbreviations
mia_abbr = "Mia"  # Miami Marlins
mil_abbr = "Mil"  # Milwaukee Brewers

# We need to map team names to IDs or find another approach
# Let's first see what team names are in the data
print("Unique teams in batter team:", pa_data['batter_team'].unique()[:10])
print("Unique teams in pitcher team:", pa_data['pitcher_team'].unique()[:10])

# Actually, let me check what columns are available
print("Columns in Statcast data:", list(pa_data.columns))

# Let's try a different approach - let's look at the games data to get team IDs
# and then map to player teams