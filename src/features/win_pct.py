import pandas as pd


def add_pregame_win_pct(games_df):
    """
    Adds two new columns to games_df:
      - home_team_pre_game_win_pct
      - away_team_pre_game_win_pct

    Each value is that team's win percentage calculated using ONLY
    games that happened strictly before the current game (no leakage).
    Doubleheader games on the same date are ordered using game_number
    so game 1's result can never leak into game 2's pre-game number.
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

    long_df["pre_game_win_pct"] = (
        long_df.groupby("team")["win"]
        .transform(lambda x: x.shift(1).expanding().mean())
    )
    long_df["pre_game_win_pct"] = long_df["pre_game_win_pct"].fillna(0.5)

    df = df.merge(
        long_df[["game_id", "team", "pre_game_win_pct"]],
        left_on=["game_id", "home_team"],
        right_on=["game_id", "team"],
        how="left",
    ).rename(columns={"pre_game_win_pct": "home_team_pre_game_win_pct"}).drop(columns="team")

    df = df.merge(
        long_df[["game_id", "team", "pre_game_win_pct"]],
        left_on=["game_id", "away_team"],
        right_on=["game_id", "team"],
        how="left",
    ).rename(columns={"pre_game_win_pct": "away_team_pre_game_win_pct"}).drop(columns="team")

    return df.drop(columns="game_id")