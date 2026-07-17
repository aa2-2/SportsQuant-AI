import pandas as pd

pd.set_option("display.precision", 3)
pd.set_option("display.max_columns", None)
pd.set_option("display.width", None)

df = pd.read_csv("data/games_with_features.csv")

print(f"Total games: {len(df)}")
print(f"Date range: {df['date'].min()} to {df['date'].max()}\n")

latest = df.copy()
latest["home_form_gap"] = (latest["home_team_recent_form"] - latest["home_team_pre_game_win_pct"]).abs()

most_recent_home = (
    latest.sort_values("date")
    .groupby("home_team")
    .tail(1)[["home_team", "home_team_pre_game_win_pct", "home_team_recent_form", "home_form_gap"]]
    .rename(columns={
        "home_team": "team",
        "home_team_pre_game_win_pct": "season_win_pct",
        "home_team_recent_form": "last10_form",
    })
    .sort_values("home_form_gap", ascending=False)
)

print("Teams with the biggest gap between season win % and last-10 form:")
print(most_recent_home.head(10).to_string(index=False))

print("\nTeams with the biggest run differential (last known value):")
run_diff_check = (
    df.sort_values("date")
    .groupby("home_team")
    .tail(1)[["home_team", "home_team_run_diff"]]
    .rename(columns={"home_team": "team", "home_team_run_diff": "avg_run_diff"})
    .sort_values("avg_run_diff", ascending=False)
)
print(run_diff_check.head(10).to_string(index=False))

print("\nRest days sanity check (should mostly be 1, occasional 0 for doubleheaders):")
print(df["home_team_rest_days"].value_counts().sort_index().to_string())

print("\nPitcher ERA sanity check (should mostly be realistic MLB values, roughly 2-6):")
print(df["home_pitcher_era"].describe().to_string())
print("\nSample of home pitcher ERA by game:")
print(df[["date", "home_team", "home_pitcher_era"]].tail(10).to_string(index=False))