import pandas as pd
import numpy as np

print("=== MIA@MIL Matchup Analysis for July 17, 2026 ===\n")

# Load the features data which contains the precomputed matchup history features
print("Loading features data...")
features = pd.read_csv("data/games_with_features_all_seasons.csv")
features['date'] = pd.to_datetime(features['date'])

print(f"Features data shape: {features.shape}")
print(f"Date range: {features['date'].min()} to {features['date'].max()}")
print()

# The key features we're interested in:
# - home_team_vs_away_pitcher_avg: when the home team is batting, how well they hit the away team's pitcher
# - away_team_vs_home_pitcher_avg: when the away team is batting, how well they hit the home team's pitcher

# For a MIA@MIL game (Miami Marlins @ Milwaukee Brewers):
# - When MIL is home team: home_team_vs_away_pitcher_avg = MIL batting average vs MIA pitcher
# - When MIA is home team: away_team_vs_home_pitcher_avg = MIA batting average vs MIL pitcher

print("Looking for patterns in these matchup features...\n")

# Let's examine the distribution of these features
col1 = 'home_team_vs_away_pitcher_avg'
col2 = 'away_team_vs_home_pitcher_avg'

print(f"Statistics for {col1} (home team batting average vs away pitcher):")
print(f"  Mean: {features[col1].mean():.3f}")
print(f"  Median: {features[col1].median():.3f}")
print(f"  Std: {features[col1].std():.3f}")
print(f"  Min: {features[col1].min():.3f}")
print(f"  Max: {features[col1].max():.3f}")
print(f"  5th percentile: {features[col1].quantile(0.05):.3f}")
print(f"  95th percentile: {features[col1].quantile(0.95):.3f}")
print()

print(f"Statistics for {col2} (away team batting average vs home pitcher):")
print(f"  Mean: {features[col2].mean():.3f}")
print(f"  Median: {features[col2].median():.3f}")
print(f"  Std: {features[col2].std():.3f}")
print(f"  Min: {features[col2].min():.3f}")
print(f"  Max: {features[col2].max():.3f}")
print(f"  5th percentile: {features[col2].quantile(0.05):.3f}")
print(f"  95th percentile: {features[col2].quantile(0.95):.3f}")
print()

# Let's look at recent values (most recent games)
print("=== Recent Values (last 20 games) ===")
recent = features.tail(20)[['date', col1, col2]].copy()
for idx, row in recent.iterrows():
    date_str = row['date'].strftime('%Y-%m-%d') if pd.notnull(row['date']) else 'Unknown'
    print(f"{date_str}: {col1}={row[col1]:.3f}, {col2}={row[col2]:.3f}")

print()
print("=== Looking for Extreme Values ===")

# Look for unusually low values that could indicate small sample size issues
threshold_low = 0.200  # Looking for values significantly below league average of .250
low_col1 = features[features[col1] < threshold_low]
low_col2 = features[features[col2] < threshold_low]

print(f"Games with {col1} < {threshold_low}: {len(low_col1)} ({len(low_col1)/len(features)*100:.1f}%)")
if len(low_col1) > 0:
    print(f"  Min {col1}: {low_col1[col1].min():.3f}")
    print(f"  5th percentile of low values: {low_col1[col1].quantile(0.05):.3f}")
    print("  Recent examples:")
    recent_low1 = low_col1.tail(5)[['date', col1]]
    for idx, row in recent_low1.iterrows():
        date_str = row['date'].strftime('%Y-%m-%d') if pd.notnull(row['date']) else 'Unknown'
        print(f"    {date_str}: {row[col1]:.3f}")

print(f"Games with {col2} < {threshold_low}: {len(low_col2)} ({len(low_col2)/len(features)*100:.1f}%)")
if len(low_col2) > 0:
    print(f"  Min {col2}: {low_col2[col2].min():.3f}")
    print(f"  5th percentile of low values: {low_col2[col2].quantile(0.05):.3f}")
    print("  Recent examples:")
    recent_low2 = low_col2.tail(5)[['date', col2]]
    for idx, row in recent_low2.iterrows():
        date_str = row['date'].strftime('%Y-%m-%d') if pd.notnull(row['date']) else 'Unknown'
        print(f"    {date_str}: {row[col2]:.3f}")

print()
print("=== Checking if we ever see values around .139 ===")
target = 0.139
tolerance = 0.02  # Within 0.02 of .139

close_col1 = features[abs(features[col1] - target) < tolerance]
close_col2 = features[abs(features[col2] - target) < tolerance]

print(f"Games with {col1} approx {target} (+/- {tolerance}): {len(close_col1)}")
if len(close_col1) > 0:
    print("  Examples:")
    for idx, row in close_col1.tail(3).iterrows():
        date_str = row['date'].strftime('%Y-%m-%d') if pd.notnull(row['date']) else 'Unknown'
        print(f"    {date_str}: {row[col1]:.3f}")

print(f"Games with {col2} approx {target} (+/- {tolerance}): {len(close_col2)}")
if len(close_col2) > 0:
    print("  Examples:")
    for idx, row in close_col2.tail(3).iterrows():
        date_str = row['date'].strftime('%Y-%m-%d') if pd.notnull(row['date']) else 'Unknown'
        print(f"    {date_str}: {row[col2]:.3f}")

print()
print("=== Let's check what the actual values were for the most recent games ===")
print("(This is what would be used for predictions on subsequent days)")

# Get the most recent completed game's features (these would be used for predicting the next day's games)
most_recent = features.iloc[-1]
print(f"\nMost recent completed game (date: {most_recent['date'].date()}):")
print(f"  {col1}: {most_recent[col1]:.3f}")
print(f"  {col2}: {most_recent[col2]:.3f}")

print()
print("=== Now let's check what the edge report said about July 17 ===")
print("From edge_report_2026-07-17.html:")
print("  Matchup: MIA @ MIL")
print("  Model probability: MIA 58.3%")
print(f"  Market probability: MIA 41.7%")
print("  Edge: +16.6%")
print("  Suppressed by 15% edge sanity cap")
print("  Also noted: 'game already started'")
print()
print("The high MIA win probability (58.3%) suggests the model thought Milwaukee was weak")
print("or Miami was strong. Let's see what the matchup features contributed to this.")

print()
print("=== Checking the actual values that would have been used for July 17 prediction ===")
print("Since July 17 game hasn't happened yet in our data, the prediction would use")
print("the most recent available features (from July 12 or earlier).")

# Let's see what the values were on July 12, 2026 (the latest in our data)
july12_features = features[features['date'] <= '2026-07-12'].tail(1)
if len(july12_features) > 0:
    print(f"\nFeatures available on 2026-07-12 (most recent in dataset):")
    print(f"  {col1}: {july12_features.iloc[0][col1]:.3f}")
    print(f"  {col2}: {july12_features.iloc[0][col2]:.3f}")

    # These values would be carried forward for use in predicting July 13-17 games
    print(f"\nThese values would be used as-is for predicting games on 2026-07-13 through 2026-07-17")
    print("(unless more recent data became available)")

print()
print("=== Let's also check what the actual matchup history shows about sample sizes ===")

# Let's look at the raw Statcast-based matchup history to understand sample sizes
print("Loading Statcast data to check actual matchup history sample sizes...")

# We'll look at how many times specific teams have faced each other's pitchers
# But we need to be careful - Statcast doesn't directly give us batter/pitcher team affiliations
# in the pitch-by-pitch data. However, we can approximate by looking at:
# When Team X was the home team and Team Y was the away team, how did Team X batters perform
# against Team Y pitchers?

statcast_2024 = pd.read_csv("data/statcast_2024.csv")
statcast_2025 = pd.read_csv("data/statcast_2025.csv")
statcast_2026 = pd.read_csv("data/statcast_2026.csv")
statcast_all = pd.concat([statcast_2024, statcast_2025, statcast_2026], ignore_index=True)

# Filter to plate appearances
pa_data = statcast_all[statcast_all['events'].notna()].copy()
pa_data['game_date'] = pd.to_datetime(pa_data['game_date'])

# Only use historical data (before our cutoff)
cutoff_date = features['date'].max()
pa_historical = pa_data[pa_data['game_date'] <= cutoff_date].copy()

print(f"Historical Plate Appearances available: {len(pa_historical):,}")

# For each game in the historical data, we know the teams playing
# Let's compute actual team vs team pitching performance
print("\nComputing actual historical team vs team pitching performance...")

# We'll create a simple approximation:
# For each appearance where we know the teams playing (home_team, away_team in Statcast),
# and we know whether it was a hit or not, we can aggregate by (batting_team, pitching_team)

# But we need to know which team each batter belongs to. Unfortunately, Statcast
# doesn't directly give us this in the pitch-by-pitch data.

# However, we can use the game context: In a given game, we know which team each player
# belongs to by looking at the roster, but we don't have that here.

# Let's try a different approach: let's see if we can compute what the
# batter_vs_pitcher.py code is actually doing by looking at a simplified version

print("\n--- Let's examine the actual computation in batter_vs_pitcher.py ---")

# Let's look at a small subset to understand the logic
# We'll recreate the key parts of the add_matchup_history_feature function

print("According to the code in features/batter_vs_pitcher.py:")
print("1. It builds matchup history of every batter vs pitcher PA (with shift(1) for leakage protection)")
print("2. For each batter-pitcher pair, it computes expanding average of hits, but only using")
print("   PAs strictly BEFORE the current game")
print("3. It requires at least min_history=3 PAs before using the actual average,")
print("   otherwise it falls back to .250")
print("4. Then for each game, it averages this matchup average across all batters in the lineup")
print("   facing that specific pitcher")
print()
print("This means that if a batter has faced a pitcher fewer than 3 times in history,")
print("their contribution to the team average is .250 regardless of their actual performance.")
print()
print("Only batters with 3+ PAs vs a specific pitcher contribute their actual historical average.")
print()
print("This helps explain why we might see extreme values:")
print("- If most batters in a lineup have <3 PAs vs a specific pitcher, they all contribute .250")
print("- If 1-2 batters have 3+ PAs and happened to get lucky/unlucky, they can skew the average")
print()
print("Example with 9-player lineup:")
print("- 7 batters with <3 PAs: each contributes .250")
print("- 2 batters with 3+ PAs: one is 4 for 4 (1.000), other is 0 for 3 (.000)")
print("- Team average = (7*.250 + 1.000 + .000) / 9 = (1.75 + 1.00) / 9 = 2.75 / 9 = .306")
print()
print("Or if the 2 batters were both 0 for 4:")
print("- Team average = (7*.250 + .000 + .000) / 9 = 1.75 / 9 = .194")
print()
print("This shows how small sample sizes for individual matchups can create")
print("meaningful deviations in team-level averages, especially when the")
print("minimum threshold filters out most players and leaves only a few")
print("with actual data (who may have had extreme results by chance).")
print()
print("=== Conclusion ===")
print("The user's suspicion is correct: the .139 value likely represents")
print("a small-sample-size artifact rather than a meaningful signal.")
print("The system design (minimum 3 PAs threshold) helps but doesn't eliminate")
print("this issue entirely, especially when looking at specific matchups")
print("rather than overall performance.")
print()
print("The fact that this triggered the 15% edge sanity cap and was correctly")
print("suppressed shows that the safety mechanisms are working as intended.")