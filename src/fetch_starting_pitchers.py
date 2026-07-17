"""
Pulls each game's starting pitchers (and their pitching lines) from
the MLB Stats API boxscore endpoint.
"""
import time

import pandas as pd

from config import DATA_DIR
from mlb_api import fetch_boxscore


def fetch_starting_pitchers(game_pk):
    """
    Given a game_pk, returns a dict with the starting pitcher's ID,
    name, and that game's pitching line (innings pitched, earned runs)
    for both the home and away team.
    """
    data = fetch_boxscore(game_pk)

    result = {"game_pk": game_pk}

    for side in ["home", "away"]:
        pitchers = data["teams"][side]["pitchers"]
        starter_id = pitchers[0]
        player_info = data["teams"][side]["players"][f"ID{starter_id}"]

        pitching_stats = player_info["stats"]["pitching"]

        result[f"{side}_pitcher_id"] = starter_id
        result[f"{side}_pitcher_name"] = player_info["person"]["fullName"]
        result[f"{side}_pitcher_innings_pitched"] = pitching_stats.get("inningsPitched", "0.0")
        result[f"{side}_pitcher_earned_runs"] = pitching_stats.get("earnedRuns", 0)

    return result


def fetch_pitchers_for_games(games_csv, output_csv, progress_every=100):
    """
    Fetches starting pitchers for every game in games_csv and saves
    the result to output_csv. Shared by the single-season and
    all-seasons entry points so the loop logic lives in one place.
    """
    games = pd.read_csv(games_csv)
    all_pitchers = []
    failures = []

    for i, game_pk in enumerate(games["game_pk"]):
        if i % progress_every == 0:
            print(f"Processed {i} of {len(games)} games...")

        try:
            all_pitchers.append(fetch_starting_pitchers(game_pk))
        except Exception as e:
            print(f"  Failed on game_pk {game_pk}: {e}")
            failures.append(game_pk)

        time.sleep(0.1)  # be polite to the API

    pitchers_df = pd.DataFrame(all_pitchers)
    pitchers_df.to_csv(output_csv, index=False)
    print(f"\nSaved {len(pitchers_df)} games with starting pitcher info to {output_csv}")
    if failures:
        print(f"WARNING: {len(failures)} game(s) failed and are missing: {failures}")


if __name__ == "__main__":
    fetch_pitchers_for_games(
        DATA_DIR / "games_2026.csv",
        DATA_DIR / "starting_pitchers.csv",
    )
