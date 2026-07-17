"""
Pulls multiple full seasons of completed games into one combined CSV.
"""
import pandas as pd

from config import DATA_DIR
from fetch_games import fetch_season_games

SEASONS = [2021, 2022, 2023, 2024, 2025, 2026]


if __name__ == "__main__":
    all_seasons = []

    for year in SEASONS:
        print(f"\nFetching full {year} season...")
        season_df = fetch_season_games(year)
        season_df["season"] = year
        all_seasons.append(season_df)
        print(f"{year}: {len(season_df)} games")

    combined = pd.concat(all_seasons, ignore_index=True)

    before = len(combined)
    combined = combined.drop_duplicates(subset="game_pk", keep="first")
    removed = before - len(combined)
    if removed:
        print(f"\nRemoved {removed} duplicate game(s)")

    output_path = DATA_DIR / "games_all_seasons.csv"
    combined.to_csv(output_path, index=False)
    print(f"\nTotal games across all seasons: {len(combined)}")
    print(combined.groupby("season").size())
