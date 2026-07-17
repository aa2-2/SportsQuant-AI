import pandas as pd
def convert_innings_pitched(ip_value):
    """
    Converts MLB's innings-pitched notation into real decimal innings.
    '5.0' -> 5.0 innings, '3.2' -> 3 innings + 2 outs -> 3.667 innings.
    """
    ip_str = str(ip_value)
    if "." not in ip_str:
        return float(ip_str)
    whole, partial_outs = ip_str.split(".")
    return float(whole) + (int(partial_outs) / 3)


def build_pitcher_vs_team_history(games_df, pitchers_df):
    """
    Builds one row per (pitcher, game), recording which team they faced
    that game, their runs allowed, and whether they were the HOME or
    AWAY starter that game (kept explicitly so we can cleanly split rows
    back apart later, rather than re-matching by pitcher ID).
    """
    df = games_df.copy()
    df["date"] = pd.to_datetime(df["date"])

    merged = pitchers_df.merge(df[["game_pk", "date", "home_team", "away_team"]], on="game_pk")

    home_pitcher_rows = merged[[
        "game_pk", "date", "home_pitcher_id", "away_team",
        "home_pitcher_earned_runs", "home_pitcher_innings_pitched",
    ]].rename(columns={
        "home_pitcher_id": "pitcher",
        "away_team": "opponent",
        "home_pitcher_earned_runs": "earned_runs",
        "home_pitcher_innings_pitched": "innings_pitched",
    })
    home_pitcher_rows["role"] = "home"

    away_pitcher_rows = merged[[
        "game_pk", "date", "away_pitcher_id", "home_team",
        "away_pitcher_earned_runs", "away_pitcher_innings_pitched",
    ]].rename(columns={
        "away_pitcher_id": "pitcher",
        "home_team": "opponent",
        "away_pitcher_earned_runs": "earned_runs",
        "away_pitcher_innings_pitched": "innings_pitched",
    })
    away_pitcher_rows["role"] = "away"

    return pd.concat([home_pitcher_rows, away_pitcher_rows], ignore_index=True)


def add_pitcher_vs_team_era(games_df, pitchers_df, min_history=2):
    """
    Adds home_pitcher_vs_opp_era / away_pitcher_vs_opp_era: each starting
    pitcher's ERA specifically against the exact team they're facing
    today, using ONLY starts against that team strictly BEFORE the
    current game (leakage-safe). Requires at least `min_history` prior
    starts against that specific opponent before trusting the number;
    otherwise falls back to league-average ERA (4.00), since 1 start
    against a team is too noisy a sample to trust as real "history."
    """
    df = games_df.copy()
    df["date"] = pd.to_datetime(df["date"])

    history = build_pitcher_vs_team_history(games_df, pitchers_df)
    history["date"] = pd.to_datetime(history["date"])
    history = history.sort_values(["pitcher", "opponent", "date"], kind="mergesort").reset_index(drop=True)
    history["innings_pitched_real"] = history["innings_pitched"].apply(convert_innings_pitched)

    history["prior_er"] = (
        history.groupby(["pitcher", "opponent"])["earned_runs"]
        .transform(lambda x: x.shift(1).expanding().sum())
    )
    history["prior_ip"] = (
        history.groupby(["pitcher", "opponent"])["innings_pitched_real"]
        .transform(lambda x: x.shift(1).expanding().sum())
    )
    history["prior_starts"] = history.groupby(["pitcher", "opponent"]).cumcount()

    history["vs_opp_era"] = (history["prior_er"] / history["prior_ip"]) * 9
    history["vs_opp_era"] = history["vs_opp_era"].replace([float("inf"), float("-inf")], pd.NA)
    history.loc[history["prior_starts"] < min_history, "vs_opp_era"] = pd.NA
    history["vs_opp_era"] = history["vs_opp_era"].fillna(4.00)

    # Each game_pk has exactly one "home"-role row and one "away"-role
    # row in history — splitting by role (not by pitcher ID) is enough
    # to merge each back to the correct side cleanly.
    home_side = history[history["role"] == "home"][["game_pk", "vs_opp_era"]].rename(
        columns={"vs_opp_era": "home_pitcher_vs_opp_era"}
    )
    away_side = history[history["role"] == "away"][["game_pk", "vs_opp_era"]].rename(
        columns={"vs_opp_era": "away_pitcher_vs_opp_era"}
    )

    df = df.merge(home_side, on="game_pk", how="left")
    df = df.merge(away_side, on="game_pk", how="left")

    df["home_pitcher_vs_opp_era"] = df["home_pitcher_vs_opp_era"].fillna(4.00)
    df["away_pitcher_vs_opp_era"] = df["away_pitcher_vs_opp_era"].fillna(4.00)

    return df


if __name__ == "__main__":
    games = pd.read_csv("data/games_all_seasons.csv")
    pitchers = pd.read_csv("data/starting_pitchers_all_seasons.csv")

    result = add_pitcher_vs_team_era(games, pitchers)

    print(f"Total games: {len(result)}")
    cols = ["date", "home_team", "away_team", "home_pitcher_vs_opp_era", "away_pitcher_vs_opp_era"]
    print(f"\nLast 10 games:\n{result[cols].tail(10).to_string(index=False)}")
    print(f"\nMissing values:\n{result[['home_pitcher_vs_opp_era', 'away_pitcher_vs_opp_era']].isnull().sum()}")