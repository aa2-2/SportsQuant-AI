import requests
import pandas as pd

# Grab one real game_pk from your existing data to test with
games = pd.read_csv("data/games_2026.csv")
sample_game_pk = games.iloc[0]["game_pk"]

print(f"Looking up boxscore for game_pk: {sample_game_pk}\n")

url = f"https://statsapi.mlb.com/api/v1/game/{sample_game_pk}/boxscore"
response = requests.get(url)
response.raise_for_status()
data = response.json()

for side in ["home", "away"]:
    team_name = data["teams"][side]["team"]["name"]
    pitchers = data["teams"][side]["pitchers"]  # list of player IDs who pitched
    starter_id = pitchers[0]  # the first pitcher listed started the game

    player_info = data["teams"][side]["players"][f"ID{starter_id}"]
    starter_name = player_info["person"]["fullName"]

    print(f"{side.upper()} team: {team_name}")
    print(f"  Starting pitcher: {starter_name} (ID: {starter_id})")