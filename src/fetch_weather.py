import time
import requests
import pandas as pd


def fetch_weather(game_pk):
    """
    Given a game_pk, returns that game's recorded weather conditions.
    """
    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()

    weather = data["gameData"].get("weather", {})

    return {
        "game_pk": game_pk,
        "condition": weather.get("condition"),
        "temp": weather.get("temp"),
        "wind": weather.get("wind"),
    }


if __name__ == "__main__":
    games = pd.read_csv("data/games_2026.csv")

    all_weather = []

    for i, game_pk in enumerate(games["game_pk"]):
        if i % 100 == 0:
            print(f"Processed {i} of {len(games)} games...")

        try:
            weather = fetch_weather(game_pk)
            all_weather.append(weather)
        except Exception as e:
            print(f"  Failed on game_pk {game_pk}: {e}")

        time.sleep(0.1)

    weather_df = pd.DataFrame(all_weather)
    weather_df.to_csv("data/weather.csv", index=False)
    print(f"\nSaved {len(weather_df)} games with weather info")