"""
Builds the full training feature set across all fetched seasons.

Team-history features (win %, Elo, pitcher ERA, etc.) use the full
2021-2026 game history. Statcast- and weather-based features only
exist for 2024-2026, so the final saved dataset is restricted to
those seasons.
"""
import pandas as pd

from config import DATA_DIR
from features.win_pct import add_pregame_win_pct
from features.recent_form import add_recent_form
from features.run_differential import add_run_differential
from features.rest_days import add_rest_days
from features.pitcher_era import add_pitcher_era
from features.ballpark import add_ballpark_factor, add_hr_park_factor
from features.weather import add_weather
from features.batting_strength import add_batting_strength
from features.pitcher_quality import add_pitcher_quality
from features.batter_power import add_batter_power
from features.pitcher_vs_team import add_pitcher_vs_team_era
from features.batter_vs_pitcher import build_matchup_history, add_matchup_history_feature
from features.elo_rating import add_elo_ratings
from features.bullpen_fatigue import add_bullpen_fatigue

STATCAST_SEASONS = [2024, 2025, 2026]

if __name__ == "__main__":
    games_full = pd.read_csv(DATA_DIR / "games_all_seasons.csv")
    pitchers_full = pd.read_csv(DATA_DIR / "starting_pitchers_all_seasons.csv")

    print(f"Full history: {len(games_full)} games (2021-2026)")

    print("Building win_pct, recent_form, run_diff, rest_days, pitcher_era, park_factor...")
    games_full = add_pregame_win_pct(games_full)
    games_full = add_recent_form(games_full)
    games_full = add_run_differential(games_full)
    games_full = add_rest_days(games_full)
    games_full = add_pitcher_era(games_full, pitchers_full)
    games_full = add_ballpark_factor(games_full)

    print("Building pitcher-vs-team history (uses full 2021-2026 pitcher history)...")
    games_full = add_pitcher_vs_team_era(games_full, pitchers_full)

    print("Building Elo ratings (uses full 2021-2026 game history)...")
    games_full = add_elo_ratings(games_full)

    subset = games_full[games_full["season"].isin(STATCAST_SEASONS)].copy()
    print(f"\nRestricting to {STATCAST_SEASONS[0]}-{STATCAST_SEASONS[-1]} "
          f"for Statcast/weather features: {len(subset)} games")

    # Each season's Statcast CSV is large — load each ONE time and
    # reuse (the old version read every file twice: once for the
    # combined frame, once again for per-season bullpen fatigue).
    print("Loading Statcast data...")
    statcast_by_season = {
        year: pd.read_csv(DATA_DIR / f"statcast_{year}.csv") for year in STATCAST_SEASONS
    }
    statcast = pd.concat(statcast_by_season.values(), ignore_index=True)

    weather = pd.read_csv(DATA_DIR / "weather_all_seasons.csv")

    print("Building hr_park_factor, weather, batting_strength, pitcher_quality, batter_power...")
    subset = add_hr_park_factor(subset, statcast)
    subset = add_weather(subset, weather)
    subset = add_batting_strength(subset, statcast)
    subset = add_pitcher_quality(subset, statcast, pitchers_full)
    subset = add_batter_power(subset, statcast)

    print("Building bullpen fatigue (per season, uses Statcast)...")
    fatigue_columns = ["game_pk", "home_team_bullpen_fatigue", "away_team_bullpen_fatigue"]
    fatigue_frames = [
        add_bullpen_fatigue(
            subset[subset["season"] == year], statcast_by_season[year], pitchers_full
        )[fatigue_columns]
        for year in STATCAST_SEASONS
    ]
    fatigue_all = pd.concat(fatigue_frames, ignore_index=True)

    subset = subset.merge(fatigue_all, on="game_pk", how="left")
    subset["home_team_bullpen_fatigue"] = subset["home_team_bullpen_fatigue"].fillna(0)
    subset["away_team_bullpen_fatigue"] = subset["away_team_bullpen_fatigue"].fillna(0)

    print("Building batter-vs-pitcher matchup history (this takes a while)...")
    matchup_history = build_matchup_history(
        [DATA_DIR / f"statcast_{year}.csv" for year in STATCAST_SEASONS]
    )
    subset = add_matchup_history_feature(subset, matchup_history, pitchers_full)

    output_path = DATA_DIR / "games_with_features_all_seasons.csv"
    subset.to_csv(output_path, index=False)
    print(f"\nSaved {len(subset)} games with full features to {output_path}")
