#!/usr/bin/env python3
"""
Fetch current weather data for MLB games using OpenWeatherMap API
"""
import requests
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import time

# Import our secure API key handler
from openweather_api_key import get_openweather_api_key

# API Configuration
OPENWEATHER_API_KEY = get_openweather_api_key()
BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

# ... (continues)


<tool_call>
<function=Write>
<parameter=content>
#!/usr/bin/env python3
"""
Fetch current weather data for MLB games using OpenWeatherMap API
"""
import requests
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import time

# Import our secure API key handler
from openweather_api_key import get_openweather_api_key

# API Configuration
OPENWEATHER_API_KEY = get_openweather_api_key()
BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

# Ballpark coordinates (latitude, longitude) for MLB stadiums
# Key: team abbreviation, Value: (lat, lon)
BALLPARK_COORDINATES = {
    # American League East
    "NYY": (40.8296, -73.9262),  # Yankee Stadium
    "BOS": (42.3467, -71.0972),  # Fenway Park
    "TBR": (27.7683, -82.6534),  # Tropicana Field
    "TOR": (43.6414, -79.3894),  # Rogers Centre
    "BAL": (39.2838, -76.6217),  # Oriole Park at Camden Yards

    # American League Central
    "CLE": (41.4962, -81.6852),  # Progressive Field
    "DET": (42.3390, -83.0485),  # Comerica Park
    "KCR": (39.0517, -94.4803),  # Kauffman Stadium
    "MIN": (44.9815, -93.2776),  # Target Field
    "CHW": (41.8299, -87.6338),  # Guaranteed Rate Field

    # American League West
    "HOU": (29.7572, -95.3554),  # Minute Maid Park
    "LAA": (33.8003, -117.8827), # Angel Stadium
    "OAK": (37.7516, -122.2005), # Oakland Coliseum
    "SEA": (47.5914, -122.3325), # T-Mobile Park
    "TEX": (32.7514, -97.0828),  # Globe Life Field

    # National League East
    "ATL": (33.8906, -84.4677),  # Truist Park
    "MIA": (25.7781, -80.2197),  # LoanDepot Park
    "NYM": (40.7571, -73.8458),  # Citi Field
    "PHI": (39.9061, -75.1665),  # Citizens Bank Park
    "WSN": (38.8730, -77.0074),  # Nationals Park

    # National League Central
    "CHC": (41.9484, -87.6553),  # Wrigley Field
    "CIN": (39.0976, -84.5061),  # Great American Ball Park
    "MIL": (43.0286, -87.9712),  # American Family Field
    "PIT": (40.4469, -80.0158),  # PNC Park
    "STL": (38.6226, -90.1928),  # Busch Stadium

    # National League West
    "ARI": (33.4455, -112.0667), # Chase Field
    "COL": (39.7562, -104.9942), # Coors Field
    "LAD": (34.0731, -118.2400), # Dodger Stadium
    "SDG": (32.7073, -117.1566), # Petco Park
    "SFG": (37.7786, -122.3893), # Oracle Park
}

# Team name to abbreviation mapping (for games data)
TEAM_ABBREVIATIONS = {
    "New York Yankees": "NYY",
    "Boston Red Sox": "BOS",
    "Tampa Bay Rays": "TBR",
    "Toronto Blue Jays": "TOR",
    "Baltimore Orioles": "BAL",
    "Cleveland Guardians": "CLE",
    "Detroit Tigers": "DET",
    "Kansas City Royals": "KCR",
    "Minnesota Twins": "MIN",
    "Chicago White Sox": "CHW",
    "Houston Astros": "HOU",
    "Los Angeles Angels": "LAA",
    "Oakland Athletics": "OAK",
    "Seattle Mariners": "SEA",
    "Texas Rangers": "TEX",
    "Atlanta Braves": "ATL",
    "Miami Marlins": "MIA",
    "New York Mets": "NYM",
    "Philadelphia Phillies": "PHI",
    "Washington Nationals": "WSN",
    "Chicago Cubs": "CHC",
    "Cincinnati Reds": "CIN",
    "Milwaukee Brewers": "MIL",
    "Pittsburgh Pirates": "PIT",
    "St. Louis Cardinals": "STL",
    "Arizona Diamondbacks": "ARI",
    "Colorado Rockies": "COL",
    "Los Angeles Dodgers": "LAD",
    "San Diego Padres": "SDG",
    "San Francisco Giants": "SFG"
}

def kelvin_to_fahrenheit(kelvin):
    """Convert Kelvin to Fahrenheit."""
    return (kelvin - 273.15) * 9/5 + 32

def meters_per_sec_to_mph(mps):
    """Convert meters per second to miles per hour."""
    return mps * 2.23694

def get_team_abbreviation(team_name):
    """Convert full team name to abbreviation."""
    return TEAM_ABBREVIATIONS.get(team_name, team_name[:3].upper())  # Fallback to first 3 letters

def calculate_field_relative_wind(wind_speed_mph, wind_direction_deg, home_team_abbr):
    """
    Convert meteorological wind direction to baseball field-relative components.

    Args:
        wind_speed_mph: Wind speed in miles per hour
        wind_direction_deg: Wind direction in degrees meteorological (0=N, 90=E)
        home_team_abbr: Home team abbreviation to get park orientation

    Returns:
        tuple: (wind_in_cf, wind_side_to_side) in mph
            wind_in_cf: Positive = wind blowing IN to center field (helps hitters)
            wind_side_to_side: Positive = wind blowing from 3B to 1B (helps pull hitters)
    """
    if home_team_abbr not in BALLPARK_COORDINATES:
        # Default to 0 orientation if park not found (assumes home plate to CF is due north)
        home_plate_to_cf_angle = 0  # degrees from north
    else:
        # For now, we'll use a simplified approach
        # In reality, each park has a specific orientation
        # This would need to be enhanced with actual park orientation data
        home_plate_to_cf_angle = 0  # Placeholder

    # Convert meteorological to math angle (0°=east, 90°=north)
    # Meteorological: 0°=N, 90°=E
    # Math: 0°=E, 90°=N
    math_angle = 90 - wind_direction_deg

    # Convert to radians
    import math
    math_rad = math.radians(math_angle)
    home_plate_to_cf_rad = math.radians(home_plate_to_cf_angle)

    # Wind vector components
    wind_east = wind_speed_mph * math.cos(math_rad)
    wind_north = wind_speed_mph * math.sin(math_rad)

    # Project onto field axes
    # Assuming home plate to CF is the y-axis (positive = toward CF)
    # And 3B to 1B is the x-axis (positive = toward 1B from 3B)
    wind_in_cf = wind_north * math.cos(home_plate_to_cf_rad) + wind_east * math.sin(home_plate_to_cf_rad)
    wind_side_to_side = -wind_north * math.sin(home_plate_to_cf_rad) + wind_east * math.cos(home_plate_to_cf_rad)

    return wind_in_cf, wind_side_to_side

def calculate_hr_weather_adjustment(temp_f, wind_speed_mph, humidity, pressure_hpa):
    """
    Calculate home run weather adjustment based on atmospheric conditions.

    Based on research: https://www.hardballtimes.com/how-weather-affects-home-run-runs-scored/

    Returns percentage adjustment to home run probability (positive = helps HRs)
    """
    # Base adjustment
    adjustment = 0.0

    # Temperature effect: warmer air is less dense = more carry
    # Every 10°F above 50°F adds ~0.5% to HR rate
    if temp_f > 50:
        adjustment += (temp_f - 50) * 0.05
    elif temp_f < 50:
        adjustment -= (50 - temp_f) * 0.05

    # Wind effect: already handled in field_relative_wind calculation
    # This function focuses on atmospheric density effects

    # Humidity effect: humid air is less dense = slightly more carry
    # But the effect is small compared to temperature
    if humidity > 50:
        adjustment += (humidity - 50) * 0.01
    else:
        adjustment -= (50 - humidity) * 0.01

    # Pressure effect: lower pressure = less dense = more carry
    # Standard pressure is ~1013 hPa
    pressure_effect = (1013 - pressure_hpa) * 0.02
    adjustment += pressure_effect

    return adjustment

def fetch_weather_for_team(team_abbr, game_date=None):
    """
    Fetch weather data for a specific team's ballpark.

    Args:
        team_abbr: Team abbreviation (e.g., 'NYY')
        game_date: Optional date for historical forecast (defaults to today)

    Returns:
        dict: Weather data or None if failed
    """
    if team_abbr not in BALLPARK_COORDINATES:
        print(f"Warning: No coordinates found for team {team_abbr}")
        return None

    lat, lon = BALLPARK_COORDINATES[team_abbr]

    params = {
        'lat': lat,
        'lon': lon,
        'appid': OPENWEATHER_API_KEY,
        'units': 'metric'  # Get temp in Celsius, we'll convert
    }

    try:
        response = requests.get(BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Extract relevant data
        temp_k = data['main']['temp']
        temp_f = kelvin_to_fahrenheit(temp_k)
        feels_like_k = data['main']['feels_like']
        feels_like_f = kelvin_to_fahrenheit(feels_like_k)
        temp_min_k = data['main']['temp_min']
        temp_min_f = kelvin_to_fahrenheit(temp_min_k)
        temp_max_k = data['main']['temp_max']
        temp_max_f = kelvin_to_fahrenheit(temp_max_k)
        pressure_hpa = data['main']['pressure']
        humidity = data['main']['humidity']
        wind_speed_mps = data['wind'].get('speed', 0)
        wind_deg = data['wind'].get('deg', 0)
        wind_speed_mph = meters_per_sec_to_mph(wind_speed_mps)

        weather_main = data['weather'][0]['main'] if data['weather'] else 'Clear'
        weather_description = data['weather'][0]['description'] if data['weather'] else 'clear sky'
        clouds = data['clouds']['all'] if 'clouds' in data else 0

        # Calculate wind components relative to field
        wind_in_cf, wind_side_to_side = calculate_field_relative_wind(
            wind_speed_mph, wind_deg, team_abbr
        )

        # Calculate HR weather adjustment
        hr_weather_adjustment = calculate_hr_weather_adjustment(
            temp_f, wind_speed_mph, humidity, pressure_hpa
        )

        return {
            'team': team_abbr,
            'temperature': round(temp_f, 1),
            'feels_like': round(feels_like_f, 1),
            'temp_min': round(temp_min_f, 1),
            'temp_max': round(temp_max_f, 1),
            'pressure': pressure_hpa,
            'humidity': humidity,
            'wind_speed': round(wind_speed_mph, 1),
            'wind_direction': wind_deg,
            'wind_speed_mps': round(wind_speed_mps, 2),
            'weather_main': weather_main,
            'weather_description': weather_description,
            'clouds': clouds,
            'wind_in_cf': round(wind_in_cf, 2),
            'wind_side_to_side': round(wind_side_to_side, 2),
            'hr_weather_adjustment': round(hr_weather_adjustment, 2),
            'timestamp': datetime.now().isoformat(),
            'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    except requests.exceptions.RequestException as e:
        print(f"Error fetching weather for {team_abbr}: {e}")
        return None
    except KeyError as e:
        print(f"Error parsing weather data for {team_abbr}: Missing key {e}")
        return None

def update_weather_for_games(games_data):
    """
    Update weather information for a list of games.

    Args:
        games_data: List of game dictionaries with home_team/away_team fields

    Returns:
        dict: Mapping of team abbreviations to their weather data
    """
    weather_cache = {}  # Avoid fetching same team multiple times
    updated_games = []

    for game in games_data:
        # Get home team abbreviation
        home_team_name = game.get('home_team', '')
        home_team_abbr = get_team_abbreviation(home_team_name)

        # Get away team abbreviation
        away_team_name = game.get('away_team', '')
        away_team_abbr = get_team_abbreviation(away_team_name)

        # Fetch weather for home team (where the game is played)
        if home_team_abbr not in weather_cache:
            weather_cache[home_team_abbr] = fetch_weather_for_team(home_team_abbr)

        # Add weather data to game
        game['weather'] = weather_cache.get(home_team_abbr)

        # If we have weather data, calculate field-specific values
        if game['weather']:
            home_abbr = game['weather']['team']
            wind_speed = game['weather']['wind_speed']
            wind_direction = game['weather']['wind_direction']

            wind_in_cf, wind_side_to_side = calculate_field_relative_wind(
                wind_speed, wind_direction, home_abbr
            )

            game['weather']['wind_in_cf'] = round(wind_in_cf, 2)
            game['weather']['wind_side_to_side'] = round(wind_side_to_side, 2)

            # Recalculate HR adjustment with field-specific winds
            game['weather']['hr_weather_adjustment'] = round(
                calculate_hr_weather_adjustment(
                    game['weather']['temperature'],
                    wind_speed,
                    game['weather']['humidity'],
                    game['weather']['pressure']
                ), 2
            )

        updated_games.append(game)

    return updated_games, weather_cache

def save_weather_data(weather_data, filename=None):
    """Save weather data to JSON file."""
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"weather_data_{timestamp}.json"

    filepath = Path("data") / "weather" / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, 'w') as f:
        json.dump(weather_data, f, indent=2)

    print(f"Weather data saved to {filepath}")
    return filepath

def main():
    """Main function for testing weather fetching."""
    print("Fetching weather data for all MLB teams...")

    all_teams = list(BALLPARK_COORDINATES.keys())
    weather_data = []

    for team in all_teams[:5]:  # Test with first 5 teams
        print(f"Fetching {team}...")
        weather = fetch_weather_for_team(team)
        if weather:
            weather_data.append(weather)
            print(f"  {team}: {weather['temperature']}°F, {weather['weather_main']}")
        else:
            print(f"  {team}: Failed to fetch")
        time.sleep(1)  # Be nice to the API

    if weather_data:
        filepath = save_weather_data(weather_data)
        print(f"\nSaved {len(weather_data)} weather records to {filepath}")

        # Show summary
        print("\nWeather Summary:")
        for w in weather_data:
            print(f"  {w['team']}: {w['temperature']}°F, {w['weather_main']}, "
                  f"Wind: {w['wind_speed']} mph {w['wind_direction']}° "
                  f"(CF: {w['wind_in_cf']:+.1f}, SS: {w['wind_side_to_side']:+.1f}) "
                  f"HR Adj: {w['hr_weather_adjustment']:+.1f}%")

if __name__ == "__main__":
    main()