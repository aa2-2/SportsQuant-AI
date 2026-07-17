import requests
import pandas as pd

games = pd.read_csv("data/games_2026.csv")

# Check several Toronto Blue Jays home games — a retractable-roof team —
# to see if "condition" varies by game (roof open vs closed) rather than
# always being the same value.
blue_jays_games = games[games["home_team"] == "Toronto Blue Jays"].head(5)

for game_pk in blue_jays_games["game_pk"]:
    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    weather = data["gameData"].get("weather", {})
    print(f"game_pk {game_pk}: {weather}")