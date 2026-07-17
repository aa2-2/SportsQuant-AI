import pandas as pd

pd.set_option("display.max_columns", None)
pd.set_option("display.width", None)

df = pd.read_csv("data/starting_pitchers.csv")
print(df[["home_pitcher_name", "home_pitcher_innings_pitched", "home_pitcher_earned_runs"]].head(10).to_string(index=False))