import pandas as pd

from features.win_pct import add_pregame_win_pct
from features.recent_form import add_recent_form
from features.run_differential import add_run_differential
from features.rest_days import add_rest_days
from features.pitcher_era import add_pitcher_era
from features.ballpark import add_ballpark_factor, add_hr_park_factor
from features.weather import add_weather
from features.batting_strength import add_batting_strength
from features.pitcher_quality import add_pitcher_quality
from features.batter_power import add_batter_power

if __name__ == "__main__":
    games = pd.read_csv("data/games_2026.csv")
    pitchers = pd.read_csv("data/starting_pitchers.csv")
    weather = pd.read_csv("data/weather.csv")
    statcast = pd.read_csv("data/statcast_2026.csv")

    games_with_features = add_pregame_win_pct(games)
    games_with_features = add_recent_form(games_with_features)
    games_with_features = add_run_differential(games_with_features)
    games_with_features = add_rest_days(games_with_features)
    games_with_features = add_pitcher_era(games_with_features, pitchers)
    games_with_features = add_ballpark_factor(games_with_features)
    games_with_features = add_hr_park_factor(games_with_features, statcast)
    games_with_features = add_weather(games_with_features, weather)
    games_with_features = add_batting_strength(games_with_features, statcast)
    games_with_features = add_pitcher_quality(games_with_features, statcast, pitchers)
    games_with_features = add_batter_power(games_with_features, statcast)

    games_with_features.to_csv("data/games_with_features.csv", index=False)
    print(f"Saved {len(games_with_features)} games with features to data/games_with_features.csv")