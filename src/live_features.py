"""
Shared helpers for building a model-ready feature row for an UPCOMING
game (as opposed to src/features/, which builds features for
historical training data).

This module exists because predict_upcoming.py and calculate_edge.py
previously each contained their own near-identical copies of these
functions (~200 duplicated lines). Any bug fix had to be made twice —
now it's made once.

Key design points:
  - prepare_pitcher_starts() reshapes the wide home/away pitcher CSV
    into one long "one row per start" table ONCE. The old code
    re-merged pitchers_df with games_df inside every single ERA
    lookup, which was both slow and repetitive.
  - build_feature_row() produces a row matching config.FEATURE_COLUMNS
    exactly, so the training features and prediction features can
    never silently drift apart.
"""
import pandas as pd

from config import FEATURE_COLUMNS, TOTALS_FEATURE_COLUMNS
from features.pitcher_era import convert_innings_pitched
from features.weather import calculate_signed_wind, parse_wind_effect, parse_wind_speed
from mlb_api import fetch_live_feed, fetch_schedule

LEAGUE_AVG_ERA = 4.00

# Neutral defaults used when live information isn't available yet
# (e.g. lineups not posted, pitcher with no tracked history).
# IMPORTANT: a "neutral" placeholder must be the TRAINING MEAN of the
# feature, because in a standardized model the mean contributes exactly
# zero — missing data then says nothing. Hand-picked values that sit
# away from the mean inject systematic bias: the original top-power
# placeholder (88 mph — an average batter, not a top-3 power hitter)
# made every team without a posted lineup look weak-hitting, which
# once pushed EVERY flag on a full slate to the away side.
# calibrate_placeholders() overwrites these defaults with real training
# means; load_prediction_context() calls it automatically.
PLACEHOLDER_TEMP = 78.0
PLACEHOLDER_SIGNED_WIND = 0.0
PLACEHOLDER_WHIFF_RATE = 0.25
PLACEHOLDER_TOP_POWER_EXIT_VELO = 91.0
PLACEHOLDER_TOP_POWER_HR_RATE = 0.06
PLACEHOLDER_EXIT_VELO = 88.0      # per unknown batter inside a KNOWN lineup
PLACEHOLDER_HR_RATE = 0.03
PLACEHOLDER_MATCHUP_AVG = 0.250
PLACEHOLDER_BULLPEN_FATIGUE = 0.0
PLACEHOLDER_ELO = 1500.0
PLACEHOLDER_HR_PARK_FACTOR = 1.0


def calibrate_placeholders(features_df):
    """
    Replaces the hand-picked placeholder defaults with the actual
    training means, so a missing input contributes ~zero to a
    standardized model instead of a hidden systematic lean.
    """
    global PLACEHOLDER_TEMP, PLACEHOLDER_SIGNED_WIND, PLACEHOLDER_WHIFF_RATE
    global PLACEHOLDER_TOP_POWER_EXIT_VELO, PLACEHOLDER_TOP_POWER_HR_RATE
    global PLACEHOLDER_MATCHUP_AVG

    def pair_mean(stem):
        return float(pd.concat([
            features_df[f"home_{stem}"], features_df[f"away_{stem}"]
        ]).mean())

    PLACEHOLDER_TOP_POWER_EXIT_VELO = pair_mean("team_top_power_exit_velo")
    PLACEHOLDER_TOP_POWER_HR_RATE = pair_mean("team_top_power_hr_rate")
    PLACEHOLDER_WHIFF_RATE = pair_mean("pitcher_whiff_rate")
    PLACEHOLDER_MATCHUP_AVG = float(pd.concat([
        features_df["home_team_vs_away_pitcher_avg"],
        features_df["away_team_vs_home_pitcher_avg"],
    ]).mean())
    PLACEHOLDER_TEMP = float(features_df["temp"].mean())
    if "signed_wind" in features_df.columns:
        PLACEHOLDER_SIGNED_WIND = float(features_df["signed_wind"].mean())
    return {
        "top_power_exit_velo": PLACEHOLDER_TOP_POWER_EXIT_VELO,
        "top_power_hr_rate": PLACEHOLDER_TOP_POWER_HR_RATE,
        "whiff_rate": PLACEHOLDER_WHIFF_RATE,
        "matchup_avg": PLACEHOLDER_MATCHUP_AVG,
        "temp": PLACEHOLDER_TEMP,
        "signed_wind": PLACEHOLDER_SIGNED_WIND,
    }


def get_upcoming_schedule(target_date):
    """
    Pulls the schedule for a date, including probable pitchers and
    (if posted) confirmed lineups. Returns one row per game.
    """
    data = fetch_schedule(date=target_date, hydrate="probablePitcher,lineups")

    games = []
    for day in data["dates"]:
        for game in day["games"]:
            home = game["teams"]["home"]
            away = game["teams"]["away"]
            lineups = game.get("lineups", {})
            games.append({
                "game_pk": game["gamePk"],
                "game_time_utc": game.get("gameDate"),
                "venue": game.get("venue", {}).get("name", ""),
                "home_team": home["team"]["name"],
                "away_team": away["team"]["name"],
                "home_pitcher_name": home.get("probablePitcher", {}).get("fullName"),
                "away_pitcher_name": away.get("probablePitcher", {}).get("fullName"),
                "home_lineup": lineups.get("homePlayers", []),
                "away_lineup": lineups.get("awayPlayers", []),
            })
    return pd.DataFrame(games)


def get_live_weather(game_pk):
    """
    Tries to pull REAL weather for an upcoming game from the live game
    feed. MLB records conditions close to game time, so this works for
    same-day predictions run near first pitch and returns None earlier
    in the day. Returns (temp, signed_wind) or None if not yet posted.
    """
    try:
        data = fetch_live_feed(game_pk)
    except Exception:
        return None

    weather = data.get("gameData", {}).get("weather", {})
    temp = pd.to_numeric(weather.get("temp"), errors="coerce")
    wind_text = weather.get("wind")

    if pd.isna(temp) or wind_text is None:
        return None

    signed_wind = calculate_signed_wind(
        parse_wind_speed(wind_text), parse_wind_effect(wind_text)
    )
    return float(temp), signed_wind


def prepare_pitcher_starts(pitchers_df, games_df):
    """
    Reshapes the wide starting-pitchers CSV (home_* and away_* columns)
    into one long table with one row per start:

        pitcher_id | pitcher_name | date | opponent | ip | er

    Innings pitched are converted from MLB's outs notation ("3.2" =
    3 innings + 2 outs) to real decimal innings here, once, instead of
    on every ERA lookup.
    """
    merged = pitchers_df.merge(
        games_df[["game_pk", "date", "home_team", "away_team"]], on="game_pk"
    )
    merged["date"] = pd.to_datetime(merged["date"])

    sides = []
    for side, opponent_side in [("home", "away"), ("away", "home")]:
        view = merged[[
            "date",
            f"{side}_pitcher_id",
            f"{side}_pitcher_name",
            f"{opponent_side}_team",
            f"{side}_pitcher_innings_pitched",
            f"{side}_pitcher_earned_runs",
        ]].rename(columns={
            f"{side}_pitcher_id": "pitcher_id",
            f"{side}_pitcher_name": "pitcher_name",
            f"{opponent_side}_team": "opponent",
            f"{side}_pitcher_innings_pitched": "ip",
            f"{side}_pitcher_earned_runs": "er",
        })
        sides.append(view)

    starts = pd.concat(sides, ignore_index=True).sort_values("date")
    starts["ip"] = starts["ip"].apply(convert_innings_pitched)
    return starts.reset_index(drop=True)


def _era_from_starts(starts):
    total_ip = starts["ip"].sum()
    if total_ip == 0:
        return LEAGUE_AVG_ERA
    return (starts["er"].sum() / total_ip) * 9


def get_pitcher_era(starts, pitcher_name, last_n=5):
    """Rolling ERA over a pitcher's last `last_n` starts."""
    if pitcher_name is None or pd.isna(pitcher_name):
        return LEAGUE_AVG_ERA
    recent = starts[starts["pitcher_name"] == pitcher_name].tail(last_n)
    if len(recent) == 0:
        return LEAGUE_AVG_ERA
    return _era_from_starts(recent)


def get_pitcher_era_vs_opponent(starts, pitcher_name, opponent_team, min_history=2):
    """A pitcher's career ERA specifically against one opponent."""
    if pitcher_name is None or pd.isna(pitcher_name):
        return LEAGUE_AVG_ERA
    history = starts[
        (starts["pitcher_name"] == pitcher_name) & (starts["opponent"] == opponent_team)
    ]
    if len(history) < min_history:
        return LEAGUE_AVG_ERA
    return _era_from_starts(history)


def get_pitcher_id_by_name(starts, pitcher_name):
    """Most recent pitcher_id seen for a name (None if never seen)."""
    if pitcher_name is None or pd.isna(pitcher_name):
        return None
    matches = starts[starts["pitcher_name"] == pitcher_name]["pitcher_id"]
    return matches.iloc[-1] if len(matches) > 0 else None


def get_latest_team_stats(features_df):
    """
    Returns each team's most recent pregame feature values (Elo,
    batting-strength metrics, bullpen fatigue), indexed by team name.
    These are the best available "as of right now" estimates for an
    upcoming game.
    """
    features_df = features_df.copy()
    features_df["date"] = pd.to_datetime(features_df["date"])

    stat_map = {
        "runs_scored_avg": "team_runs_scored_avg",
        "runs_allowed_avg": "team_runs_allowed_avg",
        "elo": "team_elo",
        "avg_exit_velo": "team_avg_exit_velo",
        "hr_rate": "team_hr_rate",
        "k_rate": "team_k_rate",
        "bullpen_fatigue": "team_bullpen_fatigue",
    }

    available = {t: s for t, s in stat_map.items()
                 if f"home_{s}" in features_df.columns and f"away_{s}" in features_df.columns}

    views = []
    for side in ["home", "away"]:
        columns = {f"{side}_team": "team"}
        columns.update({f"{side}_{source}": target for target, source in available.items()})
        view = features_df[["date"] + list(columns.keys())].rename(columns=columns)
        views.append(view)

    all_views = pd.concat(views, ignore_index=True)
    return all_views.sort_values("date").groupby("team").tail(1).set_index("team")


def get_hr_park_factor(features_df, home_team):
    """Most recent HR park factor for a team's home park."""
    features_df = features_df.copy()
    features_df["date"] = pd.to_datetime(features_df["date"])
    team_home_games = features_df[features_df["home_team"] == home_team].sort_values("date")
    if len(team_home_games) == 0:
        return PLACEHOLDER_HR_PARK_FACTOR
    return team_home_games["hr_park_factor"].iloc[-1]


def get_lineup_power(lineup_players, batter_stats, last_n=10):
    """
    Average exit velocity and HR rate for a confirmed lineup, based on
    each batter's last `last_n` games. `batter_stats` should be the
    output of build_batter_game_stats(), computed ONCE by the caller —
    the old code rebuilt it from raw Statcast for every lineup, which
    made predictions painfully slow.
    """
    if not lineup_players:
        return PLACEHOLDER_TOP_POWER_EXIT_VELO, PLACEHOLDER_TOP_POWER_HR_RATE

    exit_velos, hr_rates = [], []
    for player in lineup_players:
        player_games = batter_stats[batter_stats["batter"] == player["id"]].tail(last_n)
        if len(player_games) == 0:
            exit_velos.append(PLACEHOLDER_EXIT_VELO)
            hr_rates.append(PLACEHOLDER_HR_RATE)
        else:
            exit_velos.append(player_games["avg_exit_velo"].mean())
            hr_rates.append(player_games["home_runs"].mean())

    return pd.Series(exit_velos).mean(), pd.Series(hr_rates).mean()


def get_team_vs_pitcher_avg(lineup_players, pitcher_id, matchup_history, min_history=3):
    """Confirmed lineup's average batting average vs a specific starter."""
    if not lineup_players or pitcher_id is None or pd.isna(pitcher_id):
        return PLACEHOLDER_MATCHUP_AVG

    averages = []
    for player in lineup_players:
        pair_history = matchup_history[
            (matchup_history["batter"] == player["id"])
            & (matchup_history["pitcher"] == pitcher_id)
        ]
        if len(pair_history) < min_history:
            averages.append(PLACEHOLDER_MATCHUP_AVG)
        else:
            averages.append(pair_history["is_hit"].mean())

    return pd.Series(averages).mean()


def build_feature_row(
    home_team,
    away_team,
    latest_stats,
    starts,
    features_df,
    home_pitcher_name=None,
    away_pitcher_name=None,
    home_lineup_power=None,
    away_lineup_power=None,
    home_vs_away_pitcher=None,
    away_vs_home_pitcher=None,
    live_weather=None,
):
    """
    Builds a single-row DataFrame matching config.FEATURE_COLUMNS.

    Anything not provided falls back to a neutral placeholder, so this
    works both for full predictions (with lineups and matchup history)
    and for quicker odds-comparison runs.

    Raises KeyError if a team name isn't in latest_stats (usually an
    API-vs-CSV name mismatch) — callers should handle that per game.
    """
    home_stats = latest_stats.loc[home_team]
    away_stats = latest_stats.loc[away_team]

    temp, signed_wind = live_weather or (PLACEHOLDER_TEMP, PLACEHOLDER_SIGNED_WIND)

    home_power_velo, home_power_hr = home_lineup_power or (
        PLACEHOLDER_TOP_POWER_EXIT_VELO, PLACEHOLDER_TOP_POWER_HR_RATE)
    away_power_velo, away_power_hr = away_lineup_power or (
        PLACEHOLDER_TOP_POWER_EXIT_VELO, PLACEHOLDER_TOP_POWER_HR_RATE)

    row = pd.DataFrame([{
        "home_team_elo": home_stats.get("elo", PLACEHOLDER_ELO),
        "away_team_elo": away_stats.get("elo", PLACEHOLDER_ELO),
        "home_pitcher_era": get_pitcher_era(starts, home_pitcher_name),
        "away_pitcher_era": get_pitcher_era(starts, away_pitcher_name),
        "home_pitcher_whiff_rate": PLACEHOLDER_WHIFF_RATE,
        "away_pitcher_whiff_rate": PLACEHOLDER_WHIFF_RATE,
        "hr_park_factor": get_hr_park_factor(features_df, home_team),
        "temp": temp,
        "signed_wind": signed_wind,
        "home_team_avg_exit_velo": home_stats["avg_exit_velo"],
        "away_team_avg_exit_velo": away_stats["avg_exit_velo"],
        "home_team_hr_rate": home_stats["hr_rate"],
        "away_team_hr_rate": away_stats["hr_rate"],
        "home_team_k_rate": home_stats["k_rate"],
        "away_team_k_rate": away_stats["k_rate"],
        "home_team_top_power_exit_velo": home_power_velo,
        "away_team_top_power_exit_velo": away_power_velo,
        "home_team_top_power_hr_rate": home_power_hr,
        "away_team_top_power_hr_rate": away_power_hr,
        "home_pitcher_vs_opp_era": get_pitcher_era_vs_opponent(starts, home_pitcher_name, away_team),
        "away_pitcher_vs_opp_era": get_pitcher_era_vs_opponent(starts, away_pitcher_name, home_team),
        "home_team_vs_away_pitcher_avg": (
            home_vs_away_pitcher if home_vs_away_pitcher is not None else PLACEHOLDER_MATCHUP_AVG
        ),
        "away_team_vs_home_pitcher_avg": (
            away_vs_home_pitcher if away_vs_home_pitcher is not None else PLACEHOLDER_MATCHUP_AVG
        ),
        "home_team_bullpen_fatigue": home_stats.get("bullpen_fatigue", PLACEHOLDER_BULLPEN_FATIGUE),
        "away_team_bullpen_fatigue": away_stats.get("bullpen_fatigue", PLACEHOLDER_BULLPEN_FATIGUE),
    }])

    return row[FEATURE_COLUMNS]

def load_prediction_context(data_dir):
    """
    Loads EVERYTHING needed to build full-featured rows for upcoming
    games — historical features, pitcher starts, Statcast batter stats,
    and matchup history — once per run.

    Both predict_upcoming.py and calculate_edge.py use this, so there
    is exactly ONE model probability per game. (Previously the edge
    script skipped the slow lineup/matchup inputs and quietly produced
    a different, weaker probability than the prediction script.)
    """
    import joblib
    from features.batter_power import build_batter_game_stats
    from features.batter_vs_pitcher import build_matchup_history

    print("Loading historical data...")
    features_df = pd.read_csv(data_dir / "games_with_features_all_seasons.csv")
    games_df = pd.read_csv(data_dir / "games_all_seasons.csv")
    pitchers_df = pd.read_csv(data_dir / "starting_pitchers_all_seasons.csv")

    print("Loading Statcast batter stats...")
    statcast_current = pd.read_csv(data_dir / "statcast_2026.csv")
    batter_stats = build_batter_game_stats(statcast_current).sort_values("game_date")

    print("Loading matchup history (this may take a moment)...")
    matchup_history = build_matchup_history([
        data_dir / "statcast_2024.csv",
        data_dir / "statcast_2025.csv",
        data_dir / "statcast_2026.csv",
    ])

    return {
        "features_df": features_df,
        "starts": prepare_pitcher_starts(pitchers_df, games_df),
        "latest_stats": get_latest_team_stats(features_df),
        "batter_stats": batter_stats,
        "matchup_history": matchup_history,
        "model": joblib.load(data_dir / "calibrated_model.joblib"),
        "scaler": joblib.load(data_dir / "feature_scaler.joblib"),
    }


def build_game_feature_row(game, ctx):
    """
    Builds the FULL feature row for one schedule row (with lineups,
    matchup history, and live weather when available).

    Returns (row, live_weather) — live_weather is None when the feed
    hasn't posted conditions yet, so callers can report data quality.
    Raises KeyError when a team name isn't in the historical data.
    """
    live_weather = get_live_weather(game["game_pk"])

    home_pitcher_id = get_pitcher_id_by_name(ctx["starts"], game["home_pitcher_name"])
    away_pitcher_id = get_pitcher_id_by_name(ctx["starts"], game["away_pitcher_name"])

    row = build_feature_row(
        game["home_team"],
        game["away_team"],
        latest_stats=ctx["latest_stats"],
        starts=ctx["starts"],
        features_df=ctx["features_df"],
        home_pitcher_name=game["home_pitcher_name"],
        away_pitcher_name=game["away_pitcher_name"],
        home_lineup_power=get_lineup_power(game["home_lineup"], ctx["batter_stats"]),
        away_lineup_power=get_lineup_power(game["away_lineup"], ctx["batter_stats"]),
        home_vs_away_pitcher=get_team_vs_pitcher_avg(
            game["home_lineup"], away_pitcher_id, ctx["matchup_history"]
        ),
        away_vs_home_pitcher=get_team_vs_pitcher_avg(
            game["away_lineup"], home_pitcher_id, ctx["matchup_history"]
        ),
        live_weather=live_weather,
    )
    return row, live_weather


def get_park_run_factor(features_df, home_team):
    """Most recent park run factor for a team's home park (1.0 if unknown)."""
    if "park_run_factor" not in features_df.columns:
        return 1.0
    home_games = features_df[features_df["home_team"] == home_team]
    if len(home_games) == 0:
        return 1.0
    home_games = home_games.copy()
    home_games["date"] = pd.to_datetime(home_games["date"])
    return float(home_games.sort_values("date")["park_run_factor"].iloc[-1])


def build_totals_row(win_row, home_team, away_team, latest_stats, features_df):
    """
    Feature row for the TOTALS model. Reuses everything the win row
    already computed (pitcher ERAs, weather, park HR factor, team
    HR/K rates) and adds the run-environment inputs.
    """
    win = win_row.iloc[0]
    home_stats = latest_stats.loc[home_team]
    away_stats = latest_stats.loc[away_team]

    league_runs = 4.45  # fallback only, used when run-env stats absent
    row = pd.DataFrame([{
        "home_team_runs_scored_avg": home_stats.get("runs_scored_avg", league_runs),
        "home_team_runs_allowed_avg": home_stats.get("runs_allowed_avg", league_runs),
        "away_team_runs_scored_avg": away_stats.get("runs_scored_avg", league_runs),
        "away_team_runs_allowed_avg": away_stats.get("runs_allowed_avg", league_runs),
        "park_run_factor": get_park_run_factor(features_df, home_team),
        "home_pitcher_era": win["home_pitcher_era"],
        "away_pitcher_era": win["away_pitcher_era"],
        "hr_park_factor": win["hr_park_factor"],
        "temp": win["temp"],
        "signed_wind": win["signed_wind"],
        "home_team_hr_rate": win["home_team_hr_rate"],
        "away_team_hr_rate": win["away_team_hr_rate"],
        "home_team_k_rate": win["home_team_k_rate"],
        "away_team_k_rate": win["away_team_k_rate"],
    }])
    return row[TOTALS_FEATURE_COLUMNS]


def weather_impact(model, scaler, feature_row):
    """
    How much the ACTUAL weather is moving this game's home win
    probability, computed as a counterfactual: predict with the real
    weather, predict again with weather set to neutral (the calibrated
    training means), and return the difference in probability points.
    Positive -> current conditions favor the HOME team.
    """
    real_prob = model.predict_proba(scaler.transform(feature_row))[0][1]

    neutral_row = feature_row.copy()
    neutral_row["temp"] = PLACEHOLDER_TEMP
    neutral_row["signed_wind"] = PLACEHOLDER_SIGNED_WIND
    neutral_prob = model.predict_proba(scaler.transform(neutral_row))[0][1]

    return float(real_prob - neutral_prob)

