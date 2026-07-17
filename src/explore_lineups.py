import requests
from datetime import date

today = date.today().isoformat()

url = "https://statsapi.mlb.com/api/v1/schedule"
params = {
    "sportId": 1,
    "gameType": "R",
    "date": today,
    "hydrate": "lineups,probablePitcher",
}

response = requests.get(url, params=params)
response.raise_for_status()
data = response.json()

for day in data["dates"]:
    for game in day["games"]:
        home = game["teams"]["home"]["team"]["name"]
        away = game["teams"]["away"]["team"]["name"]

        print(f"\n{away} @ {home}")

        lineups = game.get("lineups")
        if not lineups:
            print("  No lineup data available yet")
            continue

        home_lineup = lineups.get("homePlayers", [])
        away_lineup = lineups.get("awayPlayers", [])

        print(f"  Home lineup confirmed: {len(home_lineup) > 0} ({len(home_lineup)} players)")
        print(f"  Away lineup confirmed: {len(away_lineup) > 0} ({len(away_lineup)} players)")

        if home_lineup:
            first_batter = home_lineup[0]
            print(f"  Home leadoff hitter: {first_batter.get('fullName', first_batter)}")