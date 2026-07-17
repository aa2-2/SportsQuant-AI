import pandas as pd

# Stadium roof type per team. Confirmed against arenacapacity.com's
# indoor MLB stadiums list. NOTE: Athletics and Rays have had recent
# stadium situation changes — double check these two against what you
# currently know.
STADIUM_TYPE = {
    "Arizona Diamondbacks": "retractable_roof",
    "Athletics": "open_air",
    "Atlanta Braves": "open_air",
    "Baltimore Orioles": "open_air",
    "Boston Red Sox": "open_air",
    "Chicago Cubs": "open_air",
    "Chicago White Sox": "open_air",
    "Cincinnati Reds": "open_air",
    "Cleveland Guardians": "open_air",
    "Colorado Rockies": "open_air",
    "Detroit Tigers": "open_air",
    "Houston Astros": "retractable_roof",
    "Kansas City Royals": "open_air",
    "Los Angeles Angels": "open_air",
    "Los Angeles Dodgers": "open_air",
    "Miami Marlins": "retractable_roof",
    "Milwaukee Brewers": "retractable_roof",
    "Minnesota Twins": "open_air",
    "New York Mets": "open_air",
    "New York Yankees": "open_air",
    "Philadelphia Phillies": "open_air",
    "Pittsburgh Pirates": "open_air",
    "San Diego Padres": "open_air",
    "San Francisco Giants": "open_air",
    "Seattle Mariners": "retractable_roof",
    "St. Louis Cardinals": "open_air",
    "Tampa Bay Rays": "fixed_dome",
    "Texas Rangers": "retractable_roof",
    "Toronto Blue Jays": "retractable_roof",
    "Washington Nationals": "open_air",
}

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


def add_ballpark_factor(games_df):
    """
    Adds three columns to games_df:
      - stadium_type: "fixed_dome", "retractable_roof", or "open_air"
      - weather_never_applies: True only for fixed_dome (Rays)
      - park_factor: how much more (>1.0) or less (<1.0) GENERAL SCORING
        happens at this home park compared to the league average, using
        ONLY games played there strictly before the current game (no leakage).
    """
    df = games_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["date", "game_number"], kind="mergesort").reset_index(drop=True)
    df["game_id"] = df.index
    df["total_runs"] = df["home_score"] + df["away_score"]

    league_avg = df["total_runs"].shift(1).expanding().mean()
    df["league_avg_runs"] = league_avg.fillna(df["total_runs"].mean())

    park_rows = df[["game_id", "date", "game_number", "home_team", "total_runs"]].copy()
    park_rows = park_rows.sort_values(
        ["home_team", "date", "game_number", "game_id"], kind="mergesort"
    ).reset_index(drop=True)
    park_rows["park_avg_runs"] = (
        park_rows.groupby("home_team")["total_runs"]
        .transform(lambda x: x.shift(1).expanding().mean())
    )

    df = df.merge(
        park_rows[["game_id", "park_avg_runs"]],
        on="game_id",
        how="left",
    )

    df["park_factor"] = df["park_avg_runs"] / df["league_avg_runs"]
    df["park_factor"] = df["park_factor"].fillna(1.0)

    df["stadium_type"] = df["home_team"].map(STADIUM_TYPE)
    df["weather_never_applies"] = df["stadium_type"] == "fixed_dome"

    return df.drop(columns=["game_id", "total_runs", "league_avg_runs", "park_avg_runs"])


def add_hr_park_factor(games_df, statcast_df):
    """
    Adds hr_park_factor: how much more (>1.0) or less (<1.0) HOME RUN
    SPECIFIC scoring happens at this home park compared to the league
    average — different from park_factor above, which measures general
    run scoring. A park can suppress runs overall while still being
    HR-friendly, or vice versa. Uses real home run counts from Statcast
    (games_2026.csv only has final scores, not HR counts), same
    leakage-safe shift(1) pattern as every other feature.
    """
    df = games_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["date", "game_number"], kind="mergesort").reset_index(drop=True)
    df["game_id"] = df.index

    statcast = statcast_df.copy()
    statcast = statcast[statcast["game_pk"].isin(df["game_pk"])]

    # Home runs are tagged with an "events" value, regardless of which
    # team hit them — we just need the TOTAL count per game, not split
    # by team, since this is about the PARK's effect on any home run.
    home_runs_per_game = (
        statcast[statcast["events"] == "home_run"]
        .groupby("game_pk").size()
        .rename("home_runs_in_game")
    )

    df = df.merge(home_runs_per_game, on="game_pk", how="left")
    df["home_runs_in_game"] = df["home_runs_in_game"].fillna(0)

    league_avg_hr = df["home_runs_in_game"].shift(1).expanding().mean()
    df["league_avg_hr"] = league_avg_hr.fillna(df["home_runs_in_game"].mean())

    park_rows = df[["game_id", "date", "game_number", "home_team", "home_runs_in_game"]].copy()
    park_rows = park_rows.sort_values(
        ["home_team", "date", "game_number", "game_id"], kind="mergesort"
    ).reset_index(drop=True)
    park_rows["park_avg_hr"] = (
        park_rows.groupby("home_team")["home_runs_in_game"]
        .transform(lambda x: x.shift(1).expanding().mean())
    )

    df = df.merge(
        park_rows[["game_id", "park_avg_hr"]],
        on="game_id",
        how="left",
    )

    df["hr_park_factor"] = df["park_avg_hr"] / df["league_avg_hr"]
    df["hr_park_factor"] = df["hr_park_factor"].fillna(1.0)

    return df.drop(columns=["game_id", "home_runs_in_game", "league_avg_hr", "park_avg_hr"])