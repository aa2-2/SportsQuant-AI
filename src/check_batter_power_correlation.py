import pandas as pd
from features.batter_power import add_batter_power

games = pd.read_csv("data/games_2026.csv")
statcast = pd.read_csv("data/statcast_2026.csv")
existing_features = pd.read_csv("data/games_with_features.csv")

result = add_batter_power(games, statcast)
result = result.merge(
    existing_features[["game_pk", "home_team_avg_exit_velo", "home_team_hr_rate"]],
    on="game_pk", how="left"
)

print("Correlation: top-4 power hitters' exit velo vs. whole-team exit velo:")
print(result[["home_team_top_power_exit_velo", "home_team_avg_exit_velo"]].corr().iloc[0, 1])

print("\nCorrelation: top-4 power hitters' HR rate vs. whole-team HR rate:")
print(result[["home_team_top_power_hr_rate", "home_team_hr_rate"]].corr().iloc[0, 1])