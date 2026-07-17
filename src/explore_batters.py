import requests
import pandas as pd

games = pd.read_csv("data/games_2026.csv")
sample_game_pk = games.iloc[0]["game_pk"]

print(f"Looking up boxscore for game_pk: {sample_game_pk}\n")

url = f"https://statsapi.mlb.com/api/v1/game/{sample_game_pk}/boxscore"
response = requests.get(url)
response.raise_for_status()
data = response.json()

home_batters = data["teams"]["home"]["batters"]  # list of player IDs who batted
print(f"Number of home team batters: {len(home_batters)}")

# Look at the first batter's stats in detail
first_batter_id = home_batters[0]
player_info = data["teams"]["home"]["players"][f"ID{first_batter_id}"]

print(f"\nFirst batter: {player_info['person']['fullName']}")
print(f"Batting order position: {player_info.get('battingOrder')}")
print(f"\nBatting stats for this game:")
print(player_info["stats"]["batting"])