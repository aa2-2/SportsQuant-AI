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


def build_batter_game_stats(statcast_df):
    """
    Aggregates pitch-level Statcast data into one row per batter per game:
    plate appearances, home runs, average exit velocity, and barrel rate.
    """
    df = statcast_df.copy()

    df["is_barrel"] = df["launch_speed_angle"] == 6
    df["is_home_run"] = df["events"] == "home_run"

    pa_rows = df[df["events"].notna()].copy()
    balls_in_play = df[df["launch_speed"].notna()]

    pa_stats = pa_rows.groupby(["game_pk", "game_date", "batter"]).agg(
        plate_appearances=("events", "count"),
        home_runs=("is_home_run", "sum"),
    ).reset_index()

    contact_stats = balls_in_play.groupby(["game_pk", "batter"]).agg(
        avg_exit_velo=("launch_speed", "mean"),
        barrels=("is_barrel", "sum"),
        balls_in_play_count=("launch_speed", "count"),
    ).reset_index()

    batter_stats = pa_stats.merge(contact_stats, on=["game_pk", "batter"], how="left")
    batter_stats["barrel_rate"] = batter_stats["barrels"] / batter_stats["balls_in_play_count"]

    return batter_stats


def add_batter_power(games_df, statcast_df, window=10, top_n=4):
    """
    Adds team-level 'top power hitters' columns to games_df, using each
    team's top_n batters by recent rolling exit velocity — a proxy for
    lineup power, since a team's output is often driven disproportionately
    by its best few hitters. Same leakage-safe shift(1)+rolling pattern
    as every other feature.
    """
    df = games_df.copy()
    df["date"] = pd.to_datetime(df["date"])

    batter_stats = build_batter_game_stats(statcast_df)
    batter_stats = batter_stats[batter_stats["game_pk"].isin(df["game_pk"])]
    batter_stats["game_date"] = pd.to_datetime(batter_stats["game_date"])
    batter_stats = batter_stats.sort_values(
        ["batter", "game_date", "game_pk"], kind="mergesort"
    ).reset_index(drop=True)

    for col in ["avg_exit_velo", "barrel_rate"]:
        batter_stats[f"rolling_{col}"] = (
            batter_stats.groupby("batter")[col]
            .transform(lambda x: x.shift(1).rolling(window=window, min_periods=1).mean())
        )
    batter_stats["rolling_hr_rate"] = (
        batter_stats.groupby("batter")["home_runs"]
        .transform(lambda x: x.shift(1).rolling(window=window, min_periods=1).mean())
    )
    batter_stats["rolling_avg_exit_velo"] = batter_stats["rolling_avg_exit_velo"].fillna(88.0)
    batter_stats["rolling_hr_rate"] = batter_stats["rolling_hr_rate"].fillna(0.03)

    statcast_teams = statcast_df[["game_pk", "batter", "inning_topbot", "home_team", "away_team"]].drop_duplicates(
        subset=["game_pk", "batter"]
    )
    statcast_teams["team_abbr"] = statcast_teams.apply(
        lambda row: row["home_team"] if row["inning_topbot"] == "Bot" else row["away_team"], axis=1
    )
    statcast_teams["team"] = statcast_teams["team_abbr"].map(TEAM_ABBR_TO_NAME)

    batter_stats = batter_stats.merge(
        statcast_teams[["game_pk", "batter", "team"]], on=["game_pk", "batter"], how="left"
    )

    def compute_team_game_power(group):
        top = group.nlargest(top_n, "rolling_avg_exit_velo")
        return pd.Series({
            "top_power_exit_velo": top["rolling_avg_exit_velo"].mean(),
            "top_power_hr_rate": top["rolling_hr_rate"].mean(),
        })

    team_game_power = (
        batter_stats.groupby(["game_pk", "team"])
        .apply(compute_team_game_power, include_groups=False)
        .reset_index()
    )

    neutral_defaults = {"top_power_exit_velo": 88.0, "top_power_hr_rate": 0.03}
    for col, default in neutral_defaults.items():
        team_game_power[col] = team_game_power[col].fillna(default)

    df = df.merge(
        team_game_power.rename(columns={
            "team": "home_team",
            "top_power_exit_velo": "home_team_top_power_exit_velo",
            "top_power_hr_rate": "home_team_top_power_hr_rate",
        }),
        on=["game_pk", "home_team"], how="left",
    )

    df = df.merge(
        team_game_power.rename(columns={
            "team": "away_team",
            "top_power_exit_velo": "away_team_top_power_exit_velo",
            "top_power_hr_rate": "away_team_top_power_hr_rate",
        }),
        on=["game_pk", "away_team"], how="left",
    )

    for col, default in [
        ("home_team_top_power_exit_velo", 88.0), ("away_team_top_power_exit_velo", 88.0),
        ("home_team_top_power_hr_rate", 0.03), ("away_team_top_power_hr_rate", 0.03),
    ]:
        df[col] = df[col].fillna(default)

    return df


if __name__ == "__main__":
    statcast = pd.read_csv("data/statcast_2026.csv")
    batter_stats = build_batter_game_stats(statcast)

    print(f"Batter-game rows created: {len(batter_stats)}")
    print(f"\nSample:\n{batter_stats.head(10).to_string(index=False)}")
    print(f"\nSanity check - avg_exit_velo stats:")
    print(batter_stats['avg_exit_velo'].describe())
    print(f"\nSanity check - home_runs per batter-game:")
    print(batter_stats['home_runs'].value_counts().sort_index())