import pandas as pd
import numpy as np

print("Loading data...")

# Load Statcast data
print("Loading Statcast 2024-2026...")
statcast_2024 = pd.read_csv("data/statcast_2024.csv")
statcast_2025 = pd.read_csv("data/statcast_2025.csv")
statcast_2026 = pd.read_csv("data/statcast_2026.csv")

# Combine
statcast_all = pd.concat([statcast_2024, statcast_2025, statcast_2026], ignore_index=True)
print(f"Total pitches: {len(statcast_all)}")

# Filter to plate appearances
pa_data = statcast_all[statcast_all['events'].notna()].copy()
pa_data['game_date'] = pd.to_datetime(pa_data['game_date'])
print(f"Total plate appearances: {len(pa_data)}")

# Load games data to get cutoff date (should be before 2026-07-17)
games = pd.read_csv("data/games_all_seasons.csv")
games['date'] = pd.to_datetime(games['date'])
cutoff_date = games['date'].max()
print(f"Latest game in dataset: {cutoff_date}")

# Filter Statcast to only include data before the cutoff (to avoid leakage)
pa_data_historical = pa_data[pa_data['game_date'] <= cutoff_date].copy()
print(f"Historical PAs (on or before {cutoff_date}): {len(pa_data_historical)}")

# Team abbreviations from the Statcast data
# Let's check what team abbreviations are used (home_team and away_team columns)
print("\nUnique home_team values:", pa_data_historical['home_team'].unique()[:10])
print("Unique away_team values:", pa_data_historical['away_team'].unique()[:10])

# Based on the project, it seems like they use full team names in some places
# Let's check the games data for team names
print("\nUnique away teams in games:", games['away_team'].unique()[:10])
print("Unique home teams in games:", games['home_team'].unique()[:10])

# For MIA and MIL, let's see how they appear in the games data
mia_games = games[(games['away_team'] == 'Miami Marlins') | (games['home_team'] == 'Miami Marlins')]
mil_games = games[(games['away_team'] == 'Milwaukee Brewers') | (games['home_team'] == 'Milwaukee Brewers')]
print(f"\nMiami Marlins games in dataset: {len(mia_games)}")
print(f"Milwaukee Brewers games in dataset: {len(mil_games)}")

if len(mia_games) > 0:
    print("Sample Mia games:")
    print(mia_games[['date', 'away_team', 'home_team']].tail())

if len(mil_games) > 0:
    print("Sample Mil games:")
    print(mil_games[['date', 'away_team', 'home_team']].tail())

# Now let's check the actual matchup data between Mia and Mil pitchers and batters
# First, let's get the team IDs for Mia and Mil from the Statcast data
# We need to find games where either team is Mia or Mil, then look at matchups

# Let's check what team abbreviations are actually used in Statcast for Mia and Mil
statcast_teams = set(pa_data_historical['home_team'].unique()) | set(pa_data_historical['away_team'].unique())
print(f"\nAll teams in Statcast: {sorted(list(statcast_teams))}")

# Let's look for Miami and Milwaukee team names
mia_teams = [t for t in statcast_teams if 'Miami' in t or 'Marlins' in t]
mil_teams = [t for t in statcast_teams if 'Milwaukee' in t or 'Brewers' in t]
print(f"\nMiami-related teams in Statcast: {mia_teams}")
print(f"Milwaukee-related teams in Statcast: {mil_teams}")

# Now let's get historical matchups
# We need to find plate appearances where batter is from Mia team and pitcher is from Mil team, or vice versa
# But first we need to map player teams - this is tricky without a direct mapping

# Let's try a different approach - let's look at the games_with_features_all_seasons.csv
# which should have the matchup history feature already calculated
print("\n--- Checking matchup history feature from features file ---")
features = pd.read_csv("data/games_with_features_all_seasons.csv")
print(f"Features shape: {features.shape}")
print("Columns related to matchup:", [col for col in features.columns if 'matchup' in col.lower() or 'vs' in col.lower()])

# Let's look for July 17, 2026 game specifically - but we know it's not in the games data
# Let's check what the latest date is in the features data
if 'date' in features.columns:
    features['date'] = pd.to_datetime(features['date'])
    latest_feature_date = features['date'].max()
    print(f"\nLatest date in features data: {latest_feature_date}")
else:
    print("No date column in features data")

# Let's look at the batter_vs_pitcher feature specifically
mia_vs_mil_col = 'away_team_vs_home_pitcher_avg'  # This would be MIA batting average vs MIL pitcher
mil_vs_mia_col = 'home_team_vs_away_pitcher_avg'  # This would be MIL batting average vs MIA pitcher

if mia_vs_mil_col in features.columns and mil_vs_mia_col in features.columns:
    print(f"\nLatest {mia_vs_mil_col}: {features[mia_vs_mil_col].iloc[-1]:.3f}")
    print(f"Latest {mil_vs_mia_col}: {features[mil_vs_mia_col].iloc[-1]:.3f}")

    # Let's look at a few recent values
    print(f"\nLast 5 values of {mia_vs_mil_col}:")
    print(features[mia_vs_mil_col].tail(5).tolist())
    print(f"Last 5 values of {mil_vs_mia_col}:")
    print(features[mil_vs_mia_col].tail(5).tolist())
else:
    print("Matchup history columns not found in features data")

# Let's also check what the actual game was on 2026-07-17 based on the edge report
print("\n--- Based on edge_report_2026-07-17.html ---")
print("The game was: Miami Marlins @ Milwaukee Brewers")
print("Model probability: MIA 58.3%")
print("Market probability: MIA 41.7%")
print("Edge: +16.6%")
print("This was suppressed by the 15% edge sanity cap")
print("Also noted: 'game already started'")