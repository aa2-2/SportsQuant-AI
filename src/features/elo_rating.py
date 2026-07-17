import pandas as pd

INITIAL_ELO = 1500
K_FACTOR = 20        # how much each game can move a team's rating
HOME_ADVANTAGE = 24  # standard home-field Elo boost, based on typical MLB home win rates


def calculate_expected_win_prob(team_elo, opponent_elo):
    """
    Standard Elo expected-outcome formula: given two ratings, what's
    the probability the first team wins? A 100-point Elo gap corresponds
    to roughly a 64% win probability for the stronger team.
    """
    return 1 / (1 + 10 ** ((opponent_elo - team_elo) / 400))


def add_elo_ratings(games_df):
    """
    Adds home_team_elo / away_team_elo: each team's Elo rating going
    INTO this game (before it's played, no leakage) - since Elo updates
    are inherently sequential (each game's update depends on the
    previous one), this is calculated with a single pass through the
    data in chronological order, not a vectorized shift/rolling
    operation like the other features.
    """
    df = games_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["date", "game_number", "game_pk"], kind="mergesort").reset_index(drop=True)

    elo_ratings = {}  # team_name -> current Elo rating

    home_elo_before = []
    away_elo_before = []

    for _, row in df.iterrows():
        home_team = row["home_team"]
        away_team = row["away_team"]

        home_elo = elo_ratings.get(home_team, INITIAL_ELO)
        away_elo = elo_ratings.get(away_team, INITIAL_ELO)

        # Record each team's rating BEFORE this game - this is what
        # gets used as the actual feature (no leakage).
        home_elo_before.append(home_elo)
        away_elo_before.append(away_elo)

        # Now update both ratings based on what actually happened,
        # for use in the NEXT game each team plays.
        home_elo_with_advantage = home_elo + HOME_ADVANTAGE
        expected_home_win = calculate_expected_win_prob(home_elo_with_advantage, away_elo)

        actual_home_result = 1 if row["home_win"] else 0

        elo_change = K_FACTOR * (actual_home_result - expected_home_win)

        elo_ratings[home_team] = home_elo + elo_change
        elo_ratings[away_team] = away_elo - elo_change

    df["home_team_elo"] = home_elo_before
    df["away_team_elo"] = away_elo_before

    return df


if __name__ == "__main__":
    games = pd.read_csv("data/games_all_seasons.csv")
    result = add_elo_ratings(games)

    print(f"Total games: {len(result)}")
    print(f"\nFirst 5 games (should show 1500 - everyone starts equal):")
    print(result[["date", "home_team", "home_team_elo", "away_team", "away_team_elo"]].head(5).to_string(index=False))

    print(f"\nLast 10 games (should show real, spread-out ratings):")
    print(result[["date", "home_team", "home_team_elo", "away_team", "away_team_elo"]].tail(10).to_string(index=False))

    print(f"\nCurrent Elo ratings, top 10 teams (most recent rating per team):")
    latest = pd.concat([
        result[["date", "home_team", "home_team_elo"]].rename(columns={"home_team": "team", "home_team_elo": "elo"}),
        result[["date", "away_team", "away_team_elo"]].rename(columns={"away_team": "team", "away_team_elo": "elo"}),
    ])
    latest = latest.sort_values("date").groupby("team").tail(1).sort_values("elo", ascending=False)
    print(latest[["team", "elo"]].head(10).to_string(index=False))