import pandas as pd


def add_recent_form(games_df, window=10):
    """
    Adds two new columns to games_df:
      - home_team_recent_form
      - away_team_recent_form

    Each value is that team's win percentage over their last `window` games
    (default 10), using ONLY games strictly before the current game (no leakage).
    """
    df = games_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["date", "game_number"], kind="mergesort").reset_index(drop=True)
    df["game_id"] = df.index

    home_rows = df[["game_id", "date", "game_number", "home_team", "home_win"]].rename(
        columns={"home_team": "team", "home_win": "win"}
    )
    away_rows = df[["game_id", "date", "game_number", "away_team", "home_win"]].rename(
        columns={"away_team": "team"}
    )
    away_rows["win"] = ~away_rows["home_win"]
    away_rows = away_rows.drop(columns="home_win")

    long_df = pd.concat([home_rows, away_rows], ignore_index=True)
    long_df = long_df.sort_values(
        ["team", "date", "game_number", "game_id"], kind="mergesort"
    ).reset_index(drop=True)

    long_df["recent_form"] = (
        long_df.groupby("team")["win"]
        .transform(lambda x: x.shift(1).rolling(window=window, min_periods=1).mean())
    )
    long_df["recent_form"] = long_df["recent_form"].fillna(0.5)

    df = df.merge(
        long_df[["game_id", "team", "recent_form"]],
        left_on=["game_id", "home_team"],
        right_on=["game_id", "team"],
        how="left",
    ).rename(columns={"recent_form": "home_team_recent_form"}).drop(columns="team")

    df = df.merge(
        long_df[["game_id", "team", "recent_form"]],
        left_on=["game_id", "away_team"],
        right_on=["game_id", "team"],
        how="left",
    ).rename(columns={"recent_form": "away_team_recent_form"}).drop(columns="team")

    return df.drop(columns="game_id")