import pandas as pd
import re


def parse_wind_speed(wind_text):
    """
    Extracts the numeric wind speed (in mph) from text like
    '19 mph, Out To CF'. Returns 0 if no number is found (e.g. domes).
    """
    if pd.isna(wind_text):
        return 0.0
    match = re.search(r"(\d+)\s*mph", str(wind_text))
    return float(match.group(1)) if match else 0.0


def parse_wind_effect(wind_text):
    """
    Categorizes wind direction into a simple effect on scoring:
      'out'     -> blowing toward the outfield, helps hitters (more HRs)
      'in'      -> blowing in from the outfield, helps pitchers
      'cross'   -> blowing left-to-right or right-to-left, minor/unclear effect
      'none'    -> calm, dome, or unrecognized text
    """
    if pd.isna(wind_text):
        return "none"

    text = str(wind_text).lower()

    if "out to" in text:
        return "out"
    if "in from" in text:
        return "in"
    if "l to r" in text or "r to l" in text:
        return "cross"
    return "none"


WIND_EFFECT_SIGN = {"out": 1.0, "in": -1.0, "cross": 0.0, "none": 0.0}


def calculate_signed_wind(wind_speed, wind_effect):
    """
    Combines wind speed and direction into ONE number the model can
    actually learn from:
      +15.0 -> 15 mph blowing OUT (helps hitters, more HRs)
      -15.0 -> 15 mph blowing IN  (helps pitchers)
       0.0  -> crosswind, calm, or dome
    Raw wind_speed alone treats those first two cases as identical,
    which is why it carried almost no signal in the model.
    """
    return wind_speed * WIND_EFFECT_SIGN.get(wind_effect, 0.0)


def add_weather(games_df, weather_df):
    """
    Adds weather-related columns to games_df:
      - temp: temperature in degrees F for that game
      - wind_speed: numeric wind speed in mph
      - wind_effect: 'out', 'in', 'cross', or 'none'
      - is_dome_game: True if the game was played with a closed/fixed roof
        (based on the API's own reported condition for that specific game)

    NOTE: weather is a fact about the game itself, not a "past" value like
    the other features, so no shift(1) leakage guard is needed here.
    """
    df = games_df.copy()
    weather = weather_df.copy()

    weather["temp"] = pd.to_numeric(weather["temp"], errors="coerce")
    weather["wind_speed"] = weather["wind"].apply(parse_wind_speed)
    weather["wind_effect"] = weather["wind"].apply(parse_wind_effect)
    weather["is_dome_game"] = weather["condition"].isin(["Dome", "Roof Closed"])
    weather["signed_wind"] = weather.apply(
        lambda row: calculate_signed_wind(row["wind_speed"], row["wind_effect"]), axis=1
    )

    df = df.merge(
        weather[["game_pk", "temp", "wind_speed", "signed_wind", "wind_effect", "is_dome_game"]],
        on="game_pk",
        how="left",
    )

    return df

#if __name__ == "__main__":
    games = pd.read_csv("data/games_2026.csv")
    weather = pd.read_csv("data/weather.csv")

    result = add_weather(games, weather)

    print(result["wind_effect"].value_counts())
    print(f"\nDome games: {result['is_dome_game'].sum()} of {len(result)}")
    print(f"\nSample:\n{result[['home_team', 'temp', 'wind_speed', 'wind_effect', 'is_dome_game']].head(10).to_string(index=False)}")