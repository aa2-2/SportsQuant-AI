import sys
sys.path.append("src")

import time
import pandas as pd
from fetch_weather import fetch_weather

if __name__ == "__main__":
    games = pd.read_csv("data/games_all_seasons.csv")
    games = games[games["season"].isin([2024, 2025])]

    all_weather = []
    for i, game_pk in enumerate(games["game_pk"]):
        if i % 500 == 0:
            print(f"Processed {i} of {len(games)} games...")
        try:
            weather = fetch_weather(game_pk)
            all_weather.append(weather)
        except Exception as e:
            print(f"  Failed on game_pk {game_pk}: {e}")
        time.sleep(0.1)

    weather_df = pd.DataFrame(all_weather)
    weather_df.to_csv("data/weather_2024_2025.csv", index=False)
    print(f"\nSaved {len(weather_df)} games with weather info")