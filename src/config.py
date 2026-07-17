"""
Shared project configuration: file locations and the model's feature list.

Anchoring DATA_DIR to this file's location (instead of using bare
relative paths like "data/games.csv") means every script works no
matter which directory it's run from.
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

FEATURE_COLUMNS = [
    "home_team_elo",
    "away_team_elo",
    "home_pitcher_era",
    "away_pitcher_era",
    "home_pitcher_whiff_rate",
    "away_pitcher_whiff_rate",
    "hr_park_factor",
    "temp",
    "signed_wind",
    "home_team_avg_exit_velo",
    "away_team_avg_exit_velo",
    "home_team_hr_rate",
    "away_team_hr_rate",
    "home_team_k_rate",
    "away_team_k_rate",
    "home_team_top_power_exit_velo",
    "away_team_top_power_exit_velo",
    "home_team_top_power_hr_rate",
    "away_team_top_power_hr_rate",
    "home_pitcher_vs_opp_era",
    "away_pitcher_vs_opp_era",
    "home_team_vs_away_pitcher_avg",
    "away_team_vs_home_pitcher_avg",
    "home_team_bullpen_fatigue",
    "away_team_bullpen_fatigue",
]

TARGET_COLUMN = "home_win"
