import pandas as pd

games = pd.read_csv("data/games_2026.csv")
statcast = pd.read_csv("data/statcast_2026.csv")

statcast = statcast[statcast["game_pk"].isin(games["game_pk"])]

home_runs_per_game = (
    statcast[statcast["events"] == "home_run"]
    .groupby("game_pk").size()
    .rename("home_runs_in_game")
)

games_with_hr = games.merge(home_runs_per_game, on="game_pk", how="left")
games_with_hr["home_runs_in_game"] = games_with_hr["home_runs_in_game"].fillna(0)

summary = games_with_hr.groupby("home_team").agg(
    home_games_played=("game_pk", "count"),
    total_home_runs=("home_runs_in_game", "sum"),
    avg_hr_per_game=("home_runs_in_game", "mean"),
).sort_values("avg_hr_per_game", ascending=False)

print(summary.to_string())