import pandas as pd

TEAM_ABBR_TO_NAME = {
    "AZ": "Arizona Diamondbacks", "ATH": "Athletics", "ATL": "Atlanta Braves",
    "BAL": "Baltimore Orioles", "BOS": "Boston Red Sox", "CHC": "Chicago Cubs",
    "CWS": "Chicago White Sox", "CIN": "Cincinnati Reds", "CLE": "Cleveland Guardians",
    "COL": "Colorado Rockies", "DET": "Detroit Tigers", "HOU": "Houston Astros",
    "KC": "Kansas City Royals", "LAA": "Los Angeles Angels", "LAD": "Los Angeles Dodgers",
    "MIA": "Miami Marlins", "MIL": "Milwaukee Brewers", "MIN": "Minnesota Twins",
    "NYM": "New York Mets", "NYY": "New York Yankees", "PHI": "Philadelphia Phillies",
    "PIT": "Pittsburgh Pirates", "SD": "San Diego Padres", "SF": "San Francisco Giants",
    "SEA": "Seattle Mariners", "STL": "St. Louis Cardinals", "TB": "Tampa Bay Rays",
    "TEX": "Texas Rangers", "TOR": "Toronto Blue Jays", "WSH": "Washington Nationals",
}


def calculate_bullpen_innings_per_game(statcast_df, starting_pitchers_df):
    df = statcast_df.copy()

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

    outs_events = ["strikeout", "field_out", "force_out", "grounded_into_double_play",
                   "double_play", "sac_fly", "sac_bunt", "fielders_choice_out"]

    bullpen_rows["outs_recorded"] = bullpen_rows["events"].apply(
        lambda e: 2 if e in ["grounded_into_double_play", "double_play"] else (1 if e in outs_events else 0)
    )

    team_game_outs = bullpen_rows.groupby(["game_pk", "game_date", "pitching_team_abbr"]).agg(
        bullpen_outs=("outs_recorded", "sum")
    ).reset_index()

    team_game_outs["bullpen_innings"] = team_game_outs["bullpen_outs"] / 3

    return team_game_outs


def add_bullpen_fatigue(games_df, statcast_df, starting_pitchers_df, lookback_days=2):
    df = games_df.copy()
    df["date"] = pd.to_datetime(df["date"])

    team_game_outs = calculate_bullpen_innings_per_game(statcast_df, starting_pitchers_df)
    team_game_outs = team_game_outs[team_game_outs["game_pk"].isin(df["game_pk"])]
    team_game_outs["game_date"] = pd.to_datetime(team_game_outs["game_date"])
    team_game_outs["team"] = team_game_outs["pitching_team_abbr"].map(TEAM_ABBR_TO_NAME)

    fatigue_lookup = team_game_outs[["team", "game_date", "bullpen_innings"]].copy()

    def get_fatigue(team, game_date):
        window_start = game_date - pd.Timedelta(days=lookback_days)
        recent = fatigue_lookup[
            (fatigue_lookup["team"] == team)
            & (fatigue_lookup["game_date"] < game_date)
            & (fatigue_lookup["game_date"] >= window_start)
        ]
        return recent["bullpen_innings"].sum()

    df["home_team_bullpen_fatigue"] = df.apply(lambda row: get_fatigue(row["home_team"], row["date"]), axis=1)
    df["away_team_bullpen_fatigue"] = df.apply(lambda row: get_fatigue(row["away_team"], row["date"]), axis=1)

    return df


if __name__ == "__main__":
    games = pd.read_csv("data/games_2026.csv")
    statcast = pd.read_csv("data/statcast_2026.csv")
    pitchers = pd.read_csv("data/starting_pitchers.csv")

    result = add_bullpen_fatigue(games, statcast, pitchers)

    print(f"Total games: {len(result)}")
    cols = ["date", "home_team", "home_team_bullpen_fatigue", "away_team", "away_team_bullpen_fatigue"]
    print(f"\nLast 15 games:\n{result[cols].tail(15).to_string(index=False)}")
    print(f"\nFatigue stats:")
    print(result[["home_team_bullpen_fatigue", "away_team_bullpen_fatigue"]].describe())