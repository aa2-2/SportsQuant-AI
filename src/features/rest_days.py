import pandas as pd


def add_rest_days(games_df, default_rest=4):
    """
    Adds two new columns to games_df:
      - home_team_rest_days
      - away_team_rest_days

    Each value is the number of days since that team's previous game.
    Doubleheader second games correctly show 0 rest days.
    A team's very first game of the season has no previous game to
    compare to, so it's filled with `default_rest` (a neutral typical
    rest value) rather than 0.5 or 0.0, which wouldn't make sense here.
    """
    df = games_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["date", "game_number"], kind="mergesort").reset_index(drop=True)
    df["game_id"] = df.index

    home_rows = df[["game_id", "date", "game_number", "home_team"]].rename(
        columns={"home_team": "team"}
    )
    away_rows = df[["game_id", "date", "game_number", "away_team"]].rename(
        columns={"away_team": "team"}
    )

    long_df = pd.concat([home_rows, away_rows], ignore_index=True)
    long_df = long_df.sort_values(
        ["team", "date", "game_number", "game_id"], kind="mergesort"
    ).reset_index(drop=True)

    # shift(1) gets each team's PREVIOUS game date — the same leakage
    # guard idea as your other features, just applied to a date instead
    # of a win/loss average.
    long_df["prev_date"] = long_df.groupby("team")["date"].shift(1)
    long_df["rest_days"] = (long_df["date"] - long_df["prev_date"]).dt.days

    # A team's first game of the season has no previous game at all.
    long_df["rest_days"] = long_df["rest_days"].fillna(default_rest)

    df = df.merge(
        long_df[["game_id", "team", "rest_days"]],
        left_on=["game_id", "home_team"],
        right_on=["game_id", "team"],
        how="left",
    ).rename(columns={"rest_days": "home_team_rest_days"}).drop(columns="team")

    df = df.merge(
        long_df[["game_id", "team", "rest_days"]],
        left_on=["game_id", "away_team"],
        right_on=["game_id", "team"],
        how="left",
    ).rename(columns={"rest_days": "away_team_rest_days"}).drop(columns="team")

    return df.drop(columns="game_id")