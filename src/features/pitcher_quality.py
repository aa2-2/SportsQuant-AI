import pandas as pd


def build_pitcher_game_stats(statcast_df):
    """
    Aggregates pitch-level Statcast data into one row per pitcher per game:
    average exit velocity allowed, barrel rate allowed, and whiff rate.
    """
    df = statcast_df.copy()

    df["is_barrel"] = df["launch_speed_angle"] == 6

    df["is_whiff"] = df["description"].isin(["swinging_strike", "swinging_strike_blocked"])
    df["is_swing"] = df["description"].isin([
        "swinging_strike", "swinging_strike_blocked", "foul", "hit_into_play",
        "foul_tip", "foul_bunt",
    ])

    balls_in_play = df[df["launch_speed"].notna()]

    game_stats = df.groupby(["game_pk", "game_date", "pitcher"]).agg(
        pitches=("pitch_type", "count"),
        whiffs=("is_whiff", "sum"),
        swings=("is_swing", "sum"),
    ).reset_index()

    contact_stats = balls_in_play.groupby(["game_pk", "pitcher"]).agg(
        avg_exit_velo_allowed=("launch_speed", "mean"),
        barrels_allowed=("is_barrel", "sum"),
        balls_in_play_count=("launch_speed", "count"),
    ).reset_index()

    game_stats = game_stats.merge(contact_stats, on=["game_pk", "pitcher"], how="left")

    game_stats["whiff_rate"] = game_stats["whiffs"] / game_stats["swings"]
    game_stats["barrel_rate_allowed"] = game_stats["barrels_allowed"] / game_stats["balls_in_play_count"]

    return game_stats


def add_pitcher_quality(games_df, statcast_df, pitchers_df, window=5):
    """
    Adds Statcast-based pitcher quality columns to games_df:
      - home_pitcher_exit_velo_allowed, away_pitcher_exit_velo_allowed
      - home_pitcher_barrel_rate_allowed, away_pitcher_barrel_rate_allowed
      - home_pitcher_whiff_rate, away_pitcher_whiff_rate

    Each is that starting pitcher's average over their last `window`
    starts, using ONLY starts strictly before the current game (no
    leakage) — same pattern as pitcher_era, but based on quality of
    contact allowed rather than runs allowed.
    """
    df = games_df.copy()
    df["date"] = pd.to_datetime(df["date"])

    pitcher_game_stats = build_pitcher_game_stats(statcast_df)

    starters_long = pd.concat([
        pitchers_df[["game_pk", "home_pitcher_id"]].rename(columns={"home_pitcher_id": "pitcher"}),
        pitchers_df[["game_pk", "away_pitcher_id"]].rename(columns={"away_pitcher_id": "pitcher"}),
    ], ignore_index=True)

    starter_stats = pitcher_game_stats.merge(starters_long, on=["game_pk", "pitcher"], how="inner")
    starter_stats["game_date"] = pd.to_datetime(starter_stats["game_date"])
    starter_stats = starter_stats.sort_values(
        ["pitcher", "game_date", "game_pk"], kind="mergesort"
    ).reset_index(drop=True)

    for col in ["avg_exit_velo_allowed", "barrel_rate_allowed", "whiff_rate"]:
        starter_stats[f"rolling_{col}"] = (
            starter_stats.groupby("pitcher")[col]
            .transform(lambda x: x.shift(1).rolling(window=window, min_periods=1).mean())
        )

    neutral_defaults = {
        "rolling_avg_exit_velo_allowed": 88.0,
        "rolling_barrel_rate_allowed": 0.08,
        "rolling_whiff_rate": 0.25,
    }
    for col, default in neutral_defaults.items():
        starter_stats[col] = starter_stats[col].fillna(default)

    rolling_cols = starter_stats[[
        "game_pk", "pitcher", "rolling_avg_exit_velo_allowed",
        "rolling_barrel_rate_allowed", "rolling_whiff_rate",
    ]]

    # home_pitcher_id/away_pitcher_id may already exist if add_pitcher_era
    # ran earlier in the pipeline (it also merges pitchers_df) — only add
    # them here if they're missing, to avoid a duplicate-column collision.
    if "home_pitcher_id" not in df.columns or "away_pitcher_id" not in df.columns:
        df = df.merge(
            pitchers_df[["game_pk", "home_pitcher_id", "away_pitcher_id"]],
            on="game_pk", how="left",
        )

    df = df.merge(
        rolling_cols.rename(columns={
            "pitcher": "home_pitcher_id",
            "rolling_avg_exit_velo_allowed": "home_pitcher_exit_velo_allowed",
            "rolling_barrel_rate_allowed": "home_pitcher_barrel_rate_allowed",
            "rolling_whiff_rate": "home_pitcher_whiff_rate",
        }),
        on=["game_pk", "home_pitcher_id"], how="left",
    )

    df = df.merge(
        rolling_cols.rename(columns={
            "pitcher": "away_pitcher_id",
            "rolling_avg_exit_velo_allowed": "away_pitcher_exit_velo_allowed",
            "rolling_barrel_rate_allowed": "away_pitcher_barrel_rate_allowed",
            "rolling_whiff_rate": "away_pitcher_whiff_rate",
        }),
        on=["game_pk", "away_pitcher_id"], how="left",
    )

    for col, default in [
        ("home_pitcher_exit_velo_allowed", 88.0), ("away_pitcher_exit_velo_allowed", 88.0),
        ("home_pitcher_barrel_rate_allowed", 0.08), ("away_pitcher_barrel_rate_allowed", 0.08),
        ("home_pitcher_whiff_rate", 0.25), ("away_pitcher_whiff_rate", 0.25),
    ]:
        df[col] = df[col].fillna(default)

    return df.drop(columns=["home_pitcher_id", "away_pitcher_id"])


if __name__ == "__main__":
    statcast = pd.read_csv("data/statcast_2026.csv")
    pitcher_stats = build_pitcher_game_stats(statcast)

    print(f"Pitcher-game rows created: {len(pitcher_stats)}")
    print(f"\nSample:\n{pitcher_stats.head(10).to_string(index=False)}")
    print(f"\nSanity check - avg_exit_velo_allowed stats:")
    print(pitcher_stats['avg_exit_velo_allowed'].describe())