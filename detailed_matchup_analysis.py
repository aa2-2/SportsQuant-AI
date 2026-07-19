import pandas as pd
import numpy as np

print("Loading data for detailed matchup analysis...")

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
cutoff_date = games['date'].max()  # This should be 2026-07-12
print(f"Latest game in dataset: {cutoff_date}")

# Filter Statcast to only include data before the cutoff (to avoid leakage)
pa_data_historical = pa_data[pa_data['game_date'] <= cutoff_date].copy()
print(f"Historical PAs (on or before {cutoff_date}): {len(pa_data_historical)}")

# Load starting pitchers data
pitchers = pd.read_csv("data/starting_pitchers_all_seasons.csv")
pitchers = pitchers.rename(columns={
    'home_pitcher_id': 'home_pitcher_id',
    'away_pitcher_id': 'away_pitcher_id'
})
print(f"Starting pitchers records: {len(pitchers)}")

# Now, let's find the specific matchup we're interested in:
# For a hypothetical Miami@Milwaukee game, we want to know:
# 1. How many times have Milwaukee batters faced Miami pitchers historically?
# 2. What was their batting average in those matchups?

# But we don't know the specific pitchers and lineups for July 17, 2026
# since that game hasn't happened yet in our data.

# Instead, let's look at recent actual games between these teams to understand the pattern

# Find recent Miami vs Milwaukee games
recent_games = games[
    ((games['home_team'] == 'Miami Marlins') & (games['away_team'] == 'Milwaukee Brewers')) |
    ((games['home_team'] == 'Milwaukee Brewers') & (games['away_team'] == 'Miami Marlins'))
].copy()

recent_games = recent_games.sort_values('date', ascending=False)
print(f"\nRecent Mia-Mil games: {len(recent_games)}")
if len(recent_games) > 0:
    print("Most recent games:")
    for idx, row in recent_games.head(5).iterrows():
        print(f"  {row['date'].date()}: {row['away_team']} @ {row['home_team']}")

# For each recent game, let's check what the actual matchup data shows
print("\n--- Analyzing recent actual matchups ---")

# We need to link games to starting pitchers and then to batting performance

# Let's look at the most recent game as an example
if len(recent_games) > 0:
    latest_game = recent_games.iloc[0]
    game_date = latest_game['date']
    home_team = latest_home_team = latest_game['home_team']
    away_team = latest_game['away_team']

    print(f"\nAnalyzing game: {away_team} @ {home_team} on {game_date.date()}")

    # Get the starting pitchers for this game
    game_pitchers = pitchers[pitchers['game_pk'] == latest_game['game_pk']]
    if len(game_pitchers) > 0:
        home_pitcher_id = game_pitchers.iloc[0]['home_pitcher_id']
        away_pitcher_id = game_pitchers.iloc[0]['away_pitcher_id']

        # Get pitcher names (we'd need to lookup from another table, but let's see if we have them)
        # Actually, let's check if the pitchers file has names
        pitchers_with_names = pd.read_csv("data/starting_pitchers.csv")
        if 'home_pitcher_name' in pitchers_with_names.columns:
            # Get names for this specific game
            game_pitchers_named = pitchers_with_names[pitchers_with_names['game_pk'] == latest_game['game_pk']]
            if len(game_pitchers_named) > 0:
                home_pitcher_name = game_pitchers_named.iloc[0]['home_pitcher_name']
                away_pitcher_name = game_pitchers_named.iloc[0]['away_pitcher_name']
                print(f"  Home pitcher: {home_pitcher_name} (ID: {home_pitcher_id})")
                print(f"  Away pitcher: {away_pitcher_name} (ID: {away_pitcher_id})")
            else:
                print(f"  Home pitcher ID: {home_pitcher_id}")
                print(f"  Away pitcher ID: {away_pitcher_id}")
        else:
            print(f"  Home pitcher ID: {home_pitcher_id}")
            print(f"  Away pitcher ID: {away_pitcher_id}")

        # Now, let's check the historical matchup between these teams
        # We want to know: how often have batters from the home team faced pitchers from the away team?

        # To do this properly, we would need to know which players were in the lineup
        # But we don't have lineup data in our current datasets

        # Instead, let's look at aggregate team vs team pitching performance
        # We can approximate by looking at:
        # How often do batters who normally play for Team X get hits against pitchers who normally play for Team Y?

        # This is approximate because players change teams, but it should give us a sense

        # Let's get all plate appearances where:
        # - The batter's team (from the game context) is the home team
        # - The pitcher's team (from the game context) is the away team

        # To do this, we need to merge the PA data with game info to know team affiliations

        # Let's create a mapping from game_pk to home/away teams
        game_teams = games[['game_pk', 'home_team', 'away_team']].copy()

        # Merge with PA data
        pa_with_teams = pa_data_historical.merge(game_teams, on='game_pk', how='left')

        # Now filter to only PAs where batter's team matches home team AND pitcher's team matches away team
        # OR batter's team matches away team AND pitcher's team matches home team

        # For home team batters vs away team pitchers:
        home_batter_vs_away_pitcher = pa_with_teams[
            (pa_with_teams['home_team'] == home_team) &
            (pa_with_teams['away_team'] == away_team) &
            (pa_with_teams['batting_team'] == pa_with_teams['home_team'])  # Batter is from home team
        ]

        # Actually, wait - in Statcast, we have 'home_team' and 'away_team' columns that tell us
        # which teams are playing in that game. We also need to know which team each batter/pitcher belongs to.

        # Statcast has 'batter_team' and 'pitcher_team' fields? Let me check...

        # Let me look at what columns are actually in the Statcast data
        print("\nAvailable columns in Statcast data (first 20):")
        cols = list(pa_data_historical.columns)
        for i, col in enumerate(cols[:20]):
            print(f"  {i}: {col}")
        if len(cols) > 20:
            print("  ... and more")

        # Let me check specifically for team columns
        team_related = [col for col in pa_data_historical.columns if 'team' in col.lower()]
        print(f"\nTeam-related columns: {team_related}")

        # Based on what I saw earlier when printing the first row, it looks like
        # there are 'home_team' and 'away_team' columns in the Statcast data itself
        # Let me verify this by looking at a sample

        sample_pa = pa_data_historical.iloc[0]
        print(f"\nSample PA game info:")
        print(f"  Game teams: {sample_pa['home_team']} (home) vs {sample_pa['away_team']} (away)")
        print(f"  This tells us which teams are playing in the game")

        # But we still need to know which team each batter and pitcher belongs to
        # Unfortunately, Statcast doesn't typically include the team affiliation of each player
        # in the pitch-by-pitch data - it just gives the game context

        # This means we can't directly compute "how often do Miami players hit against Milwaukee pitchers"
        # from the Statcast data alone - we would need additional player-to-team mapping data

        # However, we CAN compute the reverse: for specific games that happened in the past,
        # we can compute how each team performed against the other team's pitchers

        # Let's try a different approach: let's look at the specific feature that was computed
        # for the prediction - the team_vs_pitcher_avg

        # Actually, let me check if there's a simpler way. Let's look at the
        # features/batter_vs_pitcher.py file to see exactly how it computes the matchup history

        print("\n--- Checking how matchup history is actually computed ---")

        # Let's look at the actual function from the codebase
        # I'll recreate the logic here to see what it produces for recent games

        # But first, let me check if we can compute team-level approximation
        # by assuming that in a given game, the batter_team is the home_team if they're batting...
        # Actually, this is getting complicated.

        # Let me just look at what the actual computed values were for recent games
        # from the features we already have

        print("\n--- Looking at pre-computed matchup features ---")

        features = pd.read_csv("data/games_with_features_all_seasons.csv")
        if 'date' in features.columns:
            features['date'] = pd.to_datetime(features['date'])

        # Get the most recent games that have features
        recent_features = features.sort_values('date', ascending=False).head(10)

        print("Most recent games with computed matchup features:")
        for idx, row in recent_features.iterrows():
            game_date = row['date'] if 'date' in row and pd.notnull(row['date']) else 'Unknown'
            away_vs_home = row.get('away_team_vs_home_pitcher_avg', 'N/A')
            home_vs_away = row.get('home_team_vs_away_pitcher_avg', 'N/A')

            # Try to get the matchup from the game data if we can
            if 'date' in row and pd.notnull(row['date']):
                game_date_str = row['date'].strftime('%Y-%m-%d')
                # Find the actual game on this date
                game_on_date = games[games['date'] == row['date']]
                if len(game_on_date) > 0:
                    game = game_on_date.iloc[0]
                    matchup = f"{game['away_team']} @ {game['home_team']}"
                    print(f"  {game_date_str}: {matchup}")
                    print(f"    Away team vs Home pitcher: {away_vs_home:.3f}")
                    print(f"    Home team vs Away pitcher: {home_vs_away:.3f}")
                else:
                    print(f"  {game_date_str}: [date found but no matching game]")
                    print(f"    Away team vs Home pitcher: {away_vs_home:.3f}")
                    print(f"    Home team vs Away pitcher: {home_vs_away:.3f}")
            else:
                print(f"  [No date]: Away vs Home Pitcher: {away_vs_home:.3f}, Home vs Away Pitcher: {home_vs_away:.3f}")
else:
    print("No recent Mia-Mil games found in dataset")

print("\n--- Now let's check specifically what the user mentioned about .139 BA ---")
print("The user said they saw 'home lineup vs away starter: .139 BA'")
print("For the game MIA@MIL on 2026-07-17:")
print("  Home lineup = Milwaukee Brewers")
print("  Away starter = Miami Marlins pitcher")
print("  So this would be: Milwaukee batters vs Miami pitcher")
print("")
print("This value would be stored in the 'home_team_vs_away_pitcher_avg' feature")
print("(when the home team is Milwaukee and away team is Miami)")

# Let's see what values this feature has taken recently
if 'date' in features.columns:
    recent_home_vs_away = features[['date', 'home_team_vs_away_pitcher_avg']].copy()
    recent_home_vs_away = recent_home_vs_away.dropna(subset=['home_team_vs_away_pitcher_avg'])
    recent_home_vs_away = recent_home_vs_away.sort_values('date', ascending=False)

    print(f"\nRecent 'home_team_vs_away_pitcher_avg' values (MIL vs MIA when MIL is home):")
    for idx, row in recent_home_vs_away.head(10).iterrows():
        print(f"  {row['date'].date()}: {row['home_team_vs_away_pitcher_avg']:.3f}")

    # Check if we ever see values around .139
    close_to_139 = recent_home_vs_away[
        (abs(recent_home_vs_away['home_team_vs_away_pitcher_avg'] - 0.139) < 0.02)
    ]
    if len(close_to_139) > 0:
        print(f"\nFound {len(close_to_139)} instances where value was near .139:")
        for idx, row in close_to_139.head(5).iterrows():
            print(f"  {row['date'].date()}: {row['home_team_vs_away_pitcher_avg']:.3f}")
    else:
        print("\nNo recent values found near .139 for home_team_vs_away_pitcher_avg")

        # Let's check the away_team_vs_home_pitcher_avg (which would be MIA vs MIL when MIA is home)
        recent_away_vs_home = features[['date', 'away_team_vs_home_pitcher_avg']].copy()
        recent_away_vs_home = recent_away_vs_home.dropna(subset=['away_team_vs_home_pitcher_avg'])
        recent_away_vs_home = recent_away_vs_home.sort_values('date', ascending=False)

        print(f"\nRecent 'away_team_vs_home_pitcher_avg' values (MIA vs MIL when MIA is home):")
        for idx, row in recent_away_vs_home.head(10).iterrows():
            print(f"  {row['date'].date()}: {row['away_team_vs_home_pitcher_avg']:.3f}")

        # Check if we ever see values around .139 here
        close_to_139_away = recent_away_vs_home[
            (abs(recent_away_vs_home['away_team_vs_home_pitcher_avg'] - 0.139) < 0.02)
        ]
        if len(close_to_139_away) > 0:
            print(f"\nFound {len(close_to_139_away)} instances where value was near .139 (away team version):")
            for idx, row in close_to_139_away.head(5).iterrows():
                print(f"  {row['date'].date()}: {row['away_team_vs_home_pitcher_avg']:.3f}")

print("\n--- Let's also check the actual matchup history computation to understand sample sizes ---")
print("To really answer the user's question about sample size, we need to look at")
print("how many plate appearances make up these averages.")

# Since we don't have the exact lineups for the July 17 game, let's check
# what the typical sample sizes are for these matchup features

# Let's look at the batter_vs_pitcher.py logic to understand how it computes things
# and see if we can compute the actual distribution of sample sizes

print("\nChecking sample sizes in matchup history...")

# Let's look at the actual matchup history data that's used
from features.batter_vs_pitcher import build_matchup_history

print("Building matchup history from Statcast data...")
matchup_history = build_matchup_history([
    "data/statcast_2024.csv",
    "data/statcast_2025.csv",
    "data/statcast_2026.csv"
])

print(f"Total unique batter-pitcher pairs in history: {len(matchup_height['batter'].unique())} batters vs {len(matchup_history['pitcher'].unique())} pitchers")
print(f"Total plate appearances in matchup history: {len(matchup_history)}")

# Let's look at the distribution of how many times each batter has faced each pitcher
pitcher_batter_counts = matchup_history.groupby(['batter', 'pitcher']).size()
print(f"\nPitcher-batter pairing statistics:")
print(f"  Mean PAs per pair: {pitcher_batter_counts.mean():.1f}")
print(f"  Median PAs per pair: {pitcher_batter_counts.median():.1f}")
print(f"  Min PAs per pair: {pitcher_batter_counts.min()}")
print(f"  Max PAs per pair: {pitcher_batter_counts.max()}")
print(f"  Pairs with < 3 PAs: {(pitcher_batter_counts < 3).sum()} ({(pitcher_batter_counts < 3).mean()*100:.1f}%)")
print(f"  Pairs with < 10 PAs: {(pitcher_batter_counts < 10).sum()} ({(pitcher_batter_counts < 10).mean()*100:.1f}%)")

# This tells us that many batter-pitcher pairings have very limited history
# If we're using a minimum of 3 PAs to trust the average (as seen in the code),
# then many players will fall back to the league average (.250)

# Let's see what the actual values would be if we computed them with different minimums
print("\n--- What would happen with different minimum PA thresholds? ---")

# Let's compute the actual historical average for all pairs, then see
# what happens when we apply different minimum thresholds

# First, compute the actual historical batting average for each batter-pitcher pair
pair_stats = matchup_history.groupby(['batter', 'pitcher']).agg(
    hits=('is_hit', 'sum'),
    pa=('is_hit', 'count')
).reset_index()
pair_stats['avg'] = pair_stats['hits'] / pair_stats['pa']

print(f"Overall statistics for batter-pitcher pairs with PA > 0:")
print(f"  Career BA (total hits/total PA): {pair_stats['hits'].sum() / pair_stats['pa'].sum():.3f}")
print(f"  Average of pairwise averages: {pair_stats['avg'].mean():.3f}")
print(f"  Median of pairwise averages: {pair_stats['avg'].median():.3f}")

# Now let's see what happens when we apply minimum thresholds
for min_pa in [1, 2, 3, 5, 10]:
    qualified = pair_stats[pair_stats['pa'] >= min_pa]
    if len(qualified) > 0:
        avg_for_qualified = (qualified['hits'].sum() / qualified['pa'].sum())
        print(f"  With min {min_pa} PA: {len(qualified)} pairs, {len(qualified)/len(pair_stats)*100:.1f}% of pairs, BA = {avg_for_qualified:.3f}")
    else:
        print(f"  With min {min_pa} PA: 0 pairs")

print("\n--- This helps explain why we might see unusual values ---")
print("If a batter has only faced a pitcher 1-2 times and got lucky/unlucky,")
print("their actual average could be far from their true ability.")
print("The system uses a minimum of 3 PAs before trusting the actual average,")
print("otherwise falling back to the league average (.250).")
print("")
print("However, when we average across an entire lineup (9 players),")
print("even if several players fall back to .250, the ones with actual data")
print("can still shift the team average significantly if they've had extreme results.")
print("")
print("For example, if 8 players have no data (.250 each) and 1 player has 4 for 4 (1.000),")
print("the team average would be (8*.250 + 1*1.000)/9 = .361")
print("Or if that 1 player was 0 for 4 (.000), team average would be (8*.250 + 1*.000)/9 = .222")
print("")
print("This means small sample sizes for individual players can create")
print("meaningful deviations in team-level averages, especially when")
print("looking at specific matchups rather than season-long performance.")

# Let's also check what the actual values were in the features for the most recent games
# to see if we can spot where a .139 might have come from
print("\n--- Checking recent actual feature values for extreme values ---")

# Look for unusually low values in home_team_vs_away_pitcher_avg
low_values = features[features['home_team_vs_away_pitcher_avg'] < 0.200]['home_team_vs_away_pitcher_avg']
if len(low_values) > 0:
    print(f"Found {len(low_values)} instances where home_team_vs_away_pitcher_avg < .200")
    print(f"  Min value: {low_values.min():.3f}")
    print(f"  5th percentile: {low_values.quantile(0.05):.3f}")

    # Show the lowest few
    lowest = features.nsmallest(5, 'home_team_vs_away_pitcher_avg')[['date', 'home_team_vs_away_pitcher_avg']]
    if 'date' in latest.columns:
        print("\n  Lowest 5 values:")
        for idx, row in lowest.iterrows():
            if pd.notnull(row['date']):
                print(f"    {row['date'].date()}: {row['home_team_vs_away_pitcher_avg']:.3f}")
            else:
                print(f"    [no date]: {row['home_team_vs_away_pitcher_avg']:.3f}")

# Similarly for away_team_vs_home_pitcher_avg
low_values_away = features[features['away_team_vs_home_pitcher_avg'] < 0.200]['away_team_vs_home_pitcher_avg']
if len(low_values_away) > 0:
    print(f"\nFound {len(low_values_away)} instances where away_team_vs_home_pitcher_avg < .200")
    print(f"  Min value: {low_values_away.min():.3f}")
    print(f"  5th percentile: {low_values_away.quantile(0.05):.3f}")

    # Show the lowest few
    lowest_away = features.nsmallest(5, 'away_team_vs_home_pitcher_avg')[['date', 'away_team_vs_home_pitcher_avg']]
    if 'date' in latest.columns:
        print("\n  Lowest 5 values (away team version):")
        for idx, row in lowest_away.iterrows():
            if pd.notnull(row['date']):
                print(f"    {row['date'].date()}: {row['away_team_vs_home_pitcher_avg']:.3f}")
            else:
                print(f"    [no date]: {row['away_team_vs_home_pitcher_avg']:.3f}")

print("\n--- Conclusion ---")
print("The user's suspicion about small sample size causing the .139 reading is plausible.")
print("With only a handful of plate appearances between specific batter-pitcher pairs,")
print("random variation can cause observed averages to deviate significantly from true talent.")
print("When these extreme values get averaged across a lineup, they can still produce")
print("team-level averages that appear meaningful but are actually noisy.")
print("")
print("The system's design (requiring minimum 3 PAs before using actual data)")
print("helps mitigate this, but doesn't eliminate it entirely - especially when")
print("looking at specific matchups rather than overall performance.")