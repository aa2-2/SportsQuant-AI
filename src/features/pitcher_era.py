import pandas as pd


def convert_innings_pitched(ip_value):
    """
    Converts MLB's innings-pitched notation into real decimal innings.
    '5.0' -> 5.0 innings
    '3.2' -> 3 innings + 2 outs -> 3.667 innings
    '4.1' -> 4 innings + 1 out  -> 4.333 innings
    """
    ip_str = str(ip_value)
    if "." not in ip_str:
        return float(ip_str)

    whole, partial_outs = ip_str.split(".")
    whole = float(whole)
    partial_outs = int(partial_outs)
    return whole + (partial_outs / 3)


def add_pitcher_era(games_df, pitchers_df, window=5):
    """
    Adds two new columns to games_df:
      - home_pitcher_era
      - away_pitcher_era

    Each value is that starting pitcher's ERA over their last `window`
    starts (default 5), using ONLY starts strictly before the current
    game (no leakage). A pitcher's first tracked start has no prior
    innings, so it's filled with a neutral league-average-ish ERA of 4.00.
    """
    df = games_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.merge(pitchers_df, on="game_pk", how="left")
    df = df.sort_values(["date", "game_number"], kind="mergesort").reset_index(drop=True)
    df["game_id"] = df.index

    home_rows = df[[
        "game_id", "date", "game_number",
        "home_pitcher_id", "home_pitcher_innings_pitched", "home_pitcher_earned_runs"
    ]].rename(columns={
        "home_pitcher_id": "pitcher_id",
        "home_pitcher_innings_pitched": "innings_pitched",
        "home_pitcher_earned_runs": "earned_runs",
    })

    away_rows = df[[
        "game_id", "date", "game_number",
        "away_pitcher_id", "away_pitcher_innings_pitched", "away_pitcher_earned_runs"
    ]].rename(columns={
        "away_pitcher_id": "pitcher_id",
        "away_pitcher_innings_pitched": "innings_pitched",
        "away_pitcher_earned_runs": "earned_runs",
    })

    long_df = pd.concat([home_rows, away_rows], ignore_index=True)
    long_df["innings_pitched_real"] = long_df["innings_pitched"].apply(convert_innings_pitched)
    long_df = long_df.sort_values(
        ["pitcher_id", "date", "game_number", "game_id"], kind="mergesort"
    ).reset_index(drop=True)

    # shift(1) excludes the CURRENT start, same leakage guard as your
    # other features. rolling(window=5) sums only the last 5 PAST starts.
    long_df["rolling_er"] = (
        long_df.groupby("pitcher_id")["earned_runs"]
        .transform(lambda x: x.shift(1).rolling(window=window, min_periods=1).sum())
    )
    long_df["rolling_ip"] = (
        long_df.groupby("pitcher_id")["innings_pitched_real"]
        .transform(lambda x: x.shift(1).rolling(window=window, min_periods=1).sum())
    )

    # ERA = (earned runs / innings pitched) * 9
    long_df["era"] = (long_df["rolling_er"] / long_df["rolling_ip"]) * 9
    long_df["era"] = long_df["era"].replace([float("inf"), float("-inf")], pd.NA)
    long_df["era"] = long_df["era"].fillna(4.00)

    df = df.merge(
        long_df[["game_id", "pitcher_id", "era"]],
        left_on=["game_id", "home_pitcher_id"],
        right_on=["game_id", "pitcher_id"],
        how="left",
    ).rename(columns={"era": "home_pitcher_era"}).drop(columns="pitcher_id")

    df = df.merge(
        long_df[["game_id", "pitcher_id", "era"]],
        left_on=["game_id", "away_pitcher_id"],
        right_on=["game_id", "pitcher_id"],
        how="left",
    ).rename(columns={"era": "away_pitcher_era"}).drop(columns="pitcher_id")

    return df.drop(columns="game_id")