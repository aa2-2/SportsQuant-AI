import pandas as pd

df = pd.read_csv("data/games_with_features_all_seasons.csv")

neutral_defaults = {
    "home_team_avg_exit_velo": 88.0, "away_team_avg_exit_velo": 88.0,
    "home_team_hr_rate": 0.03, "away_team_hr_rate": 0.03,
    "home_team_k_rate": 0.22, "away_team_k_rate": 0.22,
}
for col, default in neutral_defaults.items():
    df[col] = df[col].fillna(default)

df.to_csv("data/games_with_features_all_seasons.csv", index=False)
print("Patched. Remaining missing values:")
print(df[list(neutral_defaults.keys())].isnull().sum())