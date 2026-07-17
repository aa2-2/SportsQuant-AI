import requests
import pandas as pd

url = "https://statsapi.mlb.com/api/v1/standings"

params = {
    "leagueId": "103,104",
    "season": 2026,
    "standingsTypes": "regularSeason"
}

response = requests.get(url, params=params)
response.raise_for_status()

data = response.json()

teams = []

for division in data["records"]:
    for team_record in division["teamRecords"]:

        teams.append({
    "Team": team_record["team"]["name"],
    "Wins": team_record["wins"],
    "Losses": team_record["losses"],
    "Win %": team_record["winningPercentage"],
    "Runs Scored": team_record["runsScored"],
    "Runs Allowed": team_record["runsAllowed"],
    "Run Differential": team_record["runDifferential"]
})

df = pd.DataFrame(teams)


df.to_csv("data/standings.csv", index=False)

print("\n========== MLB ANALYSIS ==========\n")


from src.analysis import analyze_standings

analyze_standings(df)