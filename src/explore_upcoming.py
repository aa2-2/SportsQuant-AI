import requests

url = "https://statsapi.mlb.com/api/v1/schedule"
params = {
    "sportId": 1,
    "gameType": "R",
    "date": "2026-07-17",
    "hydrate": "probablePitcher",
}

response = requests.get(url, params=params)
response.raise_for_status()
data = response.json()

for day in data["dates"]:
    for game in day["games"]:
        home = game["teams"]["home"]
        away = game["teams"]["away"]
        print(f"{away['team']['name']} @ {home['team']['name']}")
        print(f"  Home probable pitcher: {home.get('probablePitcher', {}).get('fullName', 'TBD')}")
        print(f"  Away probable pitcher: {away.get('probablePitcher', {}).get('fullName', 'TBD')}")