"""
Pulls starting pitchers for every game across all fetched seasons.
"""
from config import DATA_DIR
from fetch_starting_pitchers import fetch_pitchers_for_games

if __name__ == "__main__":
    fetch_pitchers_for_games(
        DATA_DIR / "games_all_seasons.csv",
        DATA_DIR / "starting_pitchers_all_seasons.csv",
        progress_every=500,
    )
