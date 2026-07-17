import pandas as pd


def build_matchup_history(statcast_paths):
    """
    Loads Statcast files across multiple seasons and combines them into
    one long history of every batter-vs-pitcher plate appearance.
    """
    all_years = []
    for path in statcast_paths:
        print(f"Loading {path}...")
        df = pd.read_csv(path, usecols=[
            "game_date", "game_pk", "batter", "pitcher", "events", "at_bat_number",
        ])
        all_years.append(df)

    combined = pd.concat(all_years, ignore_index=True)
    combined["game_date"] = pd.to_datetime(combined["game_date"])

    pa_rows = combined[combined["events"].notna()].copy()
    pa_rows["is_hit"] = pa_rows["events"].isin(["single", "double", "triple", "home_run"])

    return pa_rows.sort_values(
        ["batter", "pitcher", "game_date", "game_pk", "at_bat_number"], kind="mergesort"
    ).reset_index(drop=True)


def add_matchup_history_feature(games_df, matchup_history, pitchers_df, min_history=3):
    """
    For each game, calculates the average historical batting-average
    of the batters who've faced today's opposing starter before (using
    ONLY plate appearances strictly before the current game). Falls
    back to neutral .250 when there's not enough shared history.
    """
    df = games_df.copy()
    df["date"] = pd.to_datetime(df["date"])

    matchup_history = matchup_history.copy()

    matchup_history["prior_hits"] = (
        matchup_history.groupby(["batter", "pitcher"])["is_hit"]
        .transform(lambda x: x.shift(1).expanding().sum())
    )
    matchup_history["prior_pa_count"] = matchup_history.groupby(["batter", "pitcher"]).cumcount()

    matchup_history["matchup_avg"] = matchup_history["prior_hits"] / matchup_history["prior_pa_count"]
    matchup_history.loc[matchup_history["prior_pa_count"] < min_history, "matchup_avg"] = pd.NA
    matchup_history["matchup_avg"] = matchup_history["matchup_avg"].fillna(0.250)

    game_level = matchup_history.groupby(["game_pk", "pitcher"])["matchup_avg"].mean().reset_index()
    game_level = game_level.rename(columns={"matchup_avg": "team_vs_pitcher_avg"})

    df = df.merge(
        pitchers_df[["game_pk", "home_pitcher_id", "away_pitcher_id"]],
        on="game_pk", how="left",
    )

    df = df.merge(
        game_level.rename(columns={"pitcher": "away_pitcher_id", "team_vs_pitcher_avg": "home_team_vs_away_pitcher_avg"}),
        on=["game_pk", "away_pitcher_id"], how="left",
    )
    df = df.merge(
        game_level.rename(columns={"pitcher": "home_pitcher_id", "team_vs_pitcher_avg": "away_team_vs_home_pitcher_avg"}),
        on=["game_pk", "home_pitcher_id"], how="left",
    )

    df["home_team_vs_away_pitcher_avg"] = df["home_team_vs_away_pitcher_avg"].fillna(0.250)
    df["away_team_vs_home_pitcher_avg"] = df["away_team_vs_home_pitcher_avg"].fillna(0.250)

    return df.drop(columns=["home_pitcher_id", "away_pitcher_id"])


if __name__ == "__main__":
    paths = ["data/statcast_2024.csv", "data/statcast_2025.csv", "data/statcast_2026.csv"]
    matchup_history = build_matchup_history(paths)

    games = pd.read_csv("data/games_all_seasons.csv")
    pitchers = pd.read_csv("data/starting_pitchers_all_seasons.csv")

    result = add_matchup_history_feature(games, matchup_history, pitchers)

    print(f"\nTotal games: {len(result)}")
    cols = ["date", "home_team", "away_team", "home_team_vs_away_pitcher_avg", "away_team_vs_home_pitcher_avg"]
    print(f"\nLast 10 games:\n{result[cols].tail(10).to_string(index=False)}")
    print(f"\nMissing values:\n{result[['home_team_vs_away_pitcher_avg', 'away_team_vs_home_pitcher_avg']].isnull().sum()}")