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


def build_team_game_batting(statcast_df, valid_game_pks=None):
    df = statcast_df.copy()

    if valid_game_pks is not None:
        df = df[df["game_pk"].isin(valid_game_pks)]

    df["batting_team_abbr"] = df.apply(
        lambda row: row["home_team"] if row["inning_topbot"] == "Bot" else row["away_team"],
        axis=1
    )
    df["batting_team"] = df["batting_team_abbr"].map(TEAM_ABBR_TO_NAME)

    pa_rows = df[df["events"].notna()].copy()

    pa_rows["is_hit"] = pa_rows["events"].isin(["single", "double", "triple", "home_run"])
    pa_rows["is_home_run"] = pa_rows["events"] == "home_run"
    pa_rows["is_walk"] = pa_rows["events"].isin(["walk", "intent_walk"])
    pa_rows["is_strikeout"] = pa_rows["events"] == "strikeout"

    team_game_stats = pa_rows.groupby(["game_pk", "game_date", "batting_team"]).agg(
        plate_appearances=("events", "count"),
        hits=("is_hit", "sum"),
        home_runs=("is_home_run", "sum"),
        walks=("is_walk", "sum"),
        strikeouts=("is_strikeout", "sum"),
        avg_exit_velo=("launch_speed", "mean"),
    ).reset_index()

    return team_game_stats


def add_batting_strength(games_df, statcast_df, window=10):
    df = games_df.copy()
    df["date"] = pd.to_datetime(df["date"])

    team_batting = build_team_game_batting(statcast_df, valid_game_pks=df["game_pk"])
    team_batting["game_date"] = pd.to_datetime(team_batting["game_date"])
    team_batting = team_batting.sort_values(
        ["batting_team", "game_date", "game_pk"], kind="mergesort"
    ).reset_index(drop=True)

    team_batting["hr_rate"] = team_batting["home_runs"] / team_batting["plate_appearances"]
    team_batting["k_rate"] = team_batting["strikeouts"] / team_batting["plate_appearances"]

    for col in ["avg_exit_velo", "hr_rate", "k_rate"]:
        team_batting[f"rolling_{col}"] = (
            team_batting.groupby("batting_team")[col]
            .transform(lambda x: x.shift(1).rolling(window=window, min_periods=1).mean())
        )

    neutral_defaults = {"rolling_avg_exit_velo": 88.0, "rolling_hr_rate": 0.03, "rolling_k_rate": 0.22}
    for col, default in neutral_defaults.items():
        team_batting[col] = team_batting[col].fillna(default)

    rolling_cols = team_batting[["game_pk", "batting_team", "rolling_avg_exit_velo", "rolling_hr_rate", "rolling_k_rate"]]

    df = df.merge(
        rolling_cols.rename(columns={
            "batting_team": "home_team",
            "rolling_avg_exit_velo": "home_team_avg_exit_velo",
            "rolling_hr_rate": "home_team_hr_rate",
            "rolling_k_rate": "home_team_k_rate",
        }),
        on=["game_pk", "home_team"], how="left",
    )

    df = df.merge(
        rolling_cols.rename(columns={
            "batting_team": "away_team",
            "rolling_avg_exit_velo": "away_team_avg_exit_velo",
            "rolling_hr_rate": "away_team_hr_rate",
            "rolling_k_rate": "away_team_k_rate",
        }),
        on=["game_pk", "away_team"], how="left",
    )

    # Games where NO team-batting row was found at all (e.g. a Statcast/
    # boxscore match failure for that specific game) would otherwise
    # leave these columns as NaN, which breaks logistic regression.
    final_defaults = {
        "home_team_avg_exit_velo": 88.0, "away_team_avg_exit_velo": 88.0,
        "home_team_hr_rate": 0.03, "away_team_hr_rate": 0.03,
        "home_team_k_rate": 0.22, "away_team_k_rate": 0.22,
    }
    for col, default in final_defaults.items():
        df[col] = df[col].fillna(default)

    return df


if __name__ == "__main__":
    statcast = pd.read_csv("data/statcast_2026.csv")
    games = pd.read_csv("data/games_2026.csv")

    team_batting = build_team_game_batting(statcast, valid_game_pks=games["game_pk"])

    print(f"Team-game rows created: {len(team_batting)}")
    print(f"Expected (games x 2): {len(games) * 2}")
    print(f"\nAny unmapped team names (should be empty)?")
    print(team_batting[team_batting["batting_team"].isna()])
    print(f"\nSample:\n{team_batting.head(10).to_string(index=False)}")