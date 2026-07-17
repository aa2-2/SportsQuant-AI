"""
Pulls completed MLB game results from the MLB Stats API.
"""
import calendar

import pandas as pd

from config import DATA_DIR
from mlb_api import fetch_schedule


def fetch_games(start_date, end_date):
    """
    Pulls final MLB game results between two dates (inclusive).
    Dates must be strings in 'YYYY-MM-DD' format.
    Returns a pandas DataFrame with one row per completed game.
    """
    data = fetch_schedule(start_date=start_date, end_date=end_date)

    games = []
    for day in data["dates"]:
        for game in day["games"]:
            if game["status"]["detailedState"] != "Final":
                continue

            home = game["teams"]["home"]
            away = game["teams"]["away"]

            games.append({
                "game_pk": game["gamePk"],
                "date": day["date"],
                "game_number": game["gameNumber"],
                "home_team": home["team"]["name"],
                "away_team": away["team"]["name"],
                "home_score": home["score"],
                "away_score": away["score"],
                "home_win": home["score"] > away["score"],
            })

    return pd.DataFrame(games)


def fetch_season_games(year, first_month=3, last_month=10):
    """
    Pulls all completed games for a given MLB season, one month at a
    time (the API doesn't reliably return a full season in one call),
    and combines them. Drops duplicate games that appear twice due to
    date-range boundaries (e.g. a game delayed from one day to the
    next can show up in both months' results).
    """
    all_months = []

    for month in range(first_month, last_month + 1):
        last_day = calendar.monthrange(year, month)[1]
        start = f"{year}-{month:02d}-01"
        end = f"{year}-{month:02d}-{last_day:02d}"
        print(f"Fetching {start} to {end}...")
        all_months.append(fetch_games(start, end))

    full_season = pd.concat(all_months, ignore_index=True)

    before_count = len(full_season)
    full_season = full_season.drop_duplicates(subset="game_pk", keep="first")
    removed = before_count - len(full_season)
    if removed:
        print(f"Removed {removed} duplicate game(s) by game_pk")

    return full_season


if __name__ == "__main__":
    df = fetch_season_games(2026)
    print(df)
    print(f"\nTotal games collected: {len(df)}")
    output_path = DATA_DIR / "games_2026.csv"
    df.to_csv(output_path, index=False)
    print(f"Saved to {output_path}")
