import pandas as pd


def build_bullpen_game_stats(statcast_df, starting_pitchers_df):
    """
    Aggregates pitch-level Statcast data into one row per team per game,
    covering ONLY relief pitchers (excludes that game's starters, using
    the same starting_pitchers_all_seasons.csv already built).
    """
    df = statcast_df.copy()

    df["batting_team_abbr"] = df.apply(
        lambda row: row["home_team"] if row["inning_topbot"] == "Bot" else row["away_team"],
        axis=1
    )
    df["pitching_team_abbr"] = df.apply(
        lambda row: row["away_team"] if row["inning_topbot"] == "Bot" else row["home_team"],
        axis=1
    )

    starter_ids = pd.concat([
        starting_pitchers_df[["game_pk", "home_pitcher_id"]].rename(columns={"home_pitcher_id": "pitcher"}),
        starting_pitchers_df[["game_pk", "away_pitcher_id"]].rename(columns={"away_pitcher_id": "pitcher"}),
    ])
    starter_ids["is_starter"] = True

    df = df.merge(starter_ids, on=["game_pk", "pitcher"], how="left")
    df["is_starter"] = df["is_starter"].fillna(False).astype(bool)

    bullpen_rows = df[~df["is_starter"]].copy()

    bullpen_rows["is_barrel"] = bullpen_rows["launch_speed_angle"] == 6
    balls_in_play = bullpen_rows[bullpen_rows["launch_speed"].notna()]

    team_bullpen_stats = balls_in_play.groupby(["game_pk", "game_date", "pitching_team_abbr"]).agg(
        avg_exit_velo_allowed=("launch_speed", "mean"),
        barrels_allowed=("is_barrel", "sum"),
        balls_in_play_count=("launch_speed", "count"),
    ).reset_index()

    team_bullpen_stats["barrel_rate_allowed"] = (
        team_bullpen_stats["barrels_allowed"] / team_bullpen_stats["balls_in_play_count"]
    )

    return team_bullpen_stats


def add_bullpen_strength(games_df, statcast_df, starting_pitchers_df, window=10):
    """
    Adds rolling, leakage-safe bullpen strength columns to games_df:
      - home_team_bullpen_exit_velo, away_team_bullpen_exit_velo
      - home_team_bullpen_barrel_rate, away_team_bullpen_barrel_rate

    Each value uses only that team's last `window` games' bullpen
    performance, calculated strictly BEFORE the current game (same
    shift(1) leakage guard as every other feature).
    """
    from features.batting_strength import TEAM_ABBR_TO_NAME

    df = games_df.copy()
    df["date"] = pd.to_datetime(df["date"])

    bullpen_stats = build_bullpen_game_stats(statcast_df, starting_pitchers_df)
    bullpen_stats = bullpen_stats[bullpen_stats["game_pk"].isin(df["game_pk"])]
    bullpen_stats["game_date"] = pd.to_datetime(bullpen_stats["game_date"])
    bullpen_stats["team"] = bullpen_stats["pitching_team_abbr"].map(TEAM_ABBR_TO_NAME)

    bullpen_stats = bullpen_stats.sort_values(
        ["team", "game_date", "game_pk"], kind="mergesort"
    ).reset_index(drop=True)

    for col in ["avg_exit_velo_allowed", "barrel_rate_allowed"]:
        bullpen_stats[f"rolling_{col}"] = (
            bullpen_stats.groupby("team")[col]
            .transform(lambda x: x.shift(1).rolling(window=window, min_periods=1).mean())
        )

    neutral_defaults = {"rolling_avg_exit_velo_allowed": 88.0, "rolling_barrel_rate_allowed": 0.08}
    for col, default in neutral_defaults.items():
        bullpen_stats[col] = bullpen_stats[col].fillna(default)

    rolling_cols = bullpen_stats[["game_pk", "team", "rolling_avg_exit_velo_allowed", "rolling_barrel_rate_allowed"]]

    df = df.merge(
        rolling_cols.rename(columns={
            "team": "home_team",
            "rolling_avg_exit_velo_allowed": "home_team_bullpen_exit_velo",
            "rolling_barrel_rate_allowed": "home_team_bullpen_barrel_rate",
        }),
        on=["game_pk", "home_team"], how="left",
    )

    df = df.merge(
        rolling_cols.rename(columns={
            "team": "away_team",
            "rolling_avg_exit_velo_allowed": "away_team_bullpen_exit_velo",
            "rolling_barrel_rate_allowed": "away_team_bullpen_barrel_rate",
        }),
        on=["game_pk", "away_team"], how="left",
    )

    final_defaults = {
        "home_team_bullpen_exit_velo": 88.0, "away_team_bullpen_exit_velo": 88.0,
        "home_team_bullpen_barrel_rate": 0.08, "away_team_bullpen_barrel_rate": 0.08,
    }
    for col, default in final_defaults.items():
        df[col] = df[col].fillna(default)

    return df


if __name__ == "__main__":
    statcast = pd.read_csv("data/statcast_2026.csv")
    pitchers = pd.read_csv("data/starting_pitchers.csv")

    bullpen_stats = build_bullpen_game_stats(statcast, pitchers)

    print(f"Team-game bullpen rows created: {len(bullpen_stats)}")
    print(f"\nSample:\n{bullpen_stats.head(10).to_string(index=False)}")
    print(f"\nSanity check - avg_exit_velo_allowed:")
    print(bullpen_stats['avg_exit_velo_allowed'].describe())