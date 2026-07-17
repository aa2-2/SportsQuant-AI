"""
Pulls current MLB moneyline odds from The Odds API.

Requires the ODDS_API_KEY environment variable (see src/api_key.py).
"""
import requests
import pandas as pd

from api_key import get_odds_api_key
from config import DATA_DIR

ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds"


def fetch_mlb_odds():
    """
    Returns one row per (game, bookmaker) with home/away American odds.
    """
    # NOTE: quota cost = markets x regions per call. Requesting all
    # three markets costs 3 credits instead of 1 (free tier: 500/month,
    # so a daily pull of all three uses ~90/month — comfortably fine).
    params = {
        "apiKey": get_odds_api_key(),
        "regions": "us",
        "markets": "h2h,spreads,totals",
        "oddsFormat": "american",
    }

    response = requests.get(ODDS_API_URL, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()

    print(f"API requests remaining this period: {response.headers.get('x-requests-remaining')}")

    rows = []
    for game in data:
        home_team = game["home_team"]
        away_team = game["away_team"]

        for bookmaker in game.get("bookmakers", []):
            row = {
                "home_team": home_team,
                "away_team": away_team,
                "commence_time": game["commence_time"],
                "bookmaker": bookmaker["title"],
                "home_odds": None, "away_odds": None,
                "home_spread": None, "home_spread_odds": None,
                "away_spread": None, "away_spread_odds": None,
                "total_points": None, "over_odds": None, "under_odds": None,
            }
            for market in bookmaker.get("markets", []):
                if market["key"] == "h2h":
                    for outcome in market["outcomes"]:
                        if outcome["name"] == home_team:
                            row["home_odds"] = outcome["price"]
                        elif outcome["name"] == away_team:
                            row["away_odds"] = outcome["price"]
                elif market["key"] == "spreads":
                    for outcome in market["outcomes"]:
                        if outcome["name"] == home_team:
                            row["home_spread"] = outcome.get("point")
                            row["home_spread_odds"] = outcome["price"]
                        elif outcome["name"] == away_team:
                            row["away_spread"] = outcome.get("point")
                            row["away_spread_odds"] = outcome["price"]
                elif market["key"] == "totals":
                    for outcome in market["outcomes"]:
                        if outcome["name"] == "Over":
                            row["total_points"] = outcome.get("point")
                            row["over_odds"] = outcome["price"]
                        elif outcome["name"] == "Under":
                            row["under_odds"] = outcome["price"]
            if row["home_odds"] is not None:
                rows.append(row)

    return pd.DataFrame(rows)


if __name__ == "__main__":
    odds_df = fetch_mlb_odds()
    print(f"\nFetched odds for {odds_df['home_team'].nunique()} unique home teams, "
          f"{len(odds_df)} total (game, bookmaker) rows")
    print(odds_df.head(20).to_string(index=False))
    output_path = DATA_DIR / "mlb_odds.csv"
    odds_df.to_csv(output_path, index=False)
    print(f"\nSaved to {output_path}")
