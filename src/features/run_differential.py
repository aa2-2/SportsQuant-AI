import pandas as pd


def add_run_differential(games_df):
    """
    Adds two new columns to games_df:
      - home_team_run_diff
      - away_team_run_diff

    Each value is that team's average run differential per game
    (runs scored minus runs allowed), using ONLY games strictly
    before the current game (no leakage).
    """
    df = games_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["date", "game_number"], kind="mergesort").reset_index(drop=True)
    df["game_id"] = df.index

    home_rows = df[["game_id", "date", "game_number", "home_team"]].copy()
    home_rows["team"] = home_rows["home_team"]
    home_rows["run_diff"] = df["home_score"] - df["away_score"]
    home_rows = home_rows[["game_id", "date", "game_number", "team", "run_diff"]]

    away_rows = df[["game_id", "date", "game_number", "away_team"]].copy()
    away_rows["team"] = away_rows["away_team"]
    away_rows["run_diff"] = df["away_score"] - df["home_score"]
    away_rows = away_rows[["game_id", "date", "game_number", "team", "run_diff"]]

    long_df = pd.concat([home_rows, away_rows], ignore_index=True)
    long_df = long_df.sort_values(
        ["team", "date", "game_number", "game_id"], kind="mergesort"
    ).reset_index(drop=True)

    long_df["avg_run_diff"] = (
        long_df.groupby("team")["run_diff"]
        .transform(lambda x: x.shift(1).expanding().mean())
    )
    # 0.0 is the right neutral default here (not 0.5) — run differential
    # is centered at zero, not at a 50% win rate.
    long_df["avg_run_diff"] = long_df["avg_run_diff"].fillna(0.0)

    df = df.merge(
        long_df[["game_id", "team", "avg_run_diff"]],
        left_on=["game_id", "home_team"],
        right_on=["game_id", "team"],
        how="left",
    ).rename(columns={"avg_run_diff": "home_team_run_diff"}).drop(columns="team")

    df = df.merge(
        long_df[["game_id", "team", "avg_run_diff"]],
        left_on=["game_id", "away_team"],
        right_on=["game_id", "team"],
        how="left",
    ).rename(columns={"avg_run_diff": "away_team_run_diff"}).drop(columns="team")

    return df.drop(columns="game_id")