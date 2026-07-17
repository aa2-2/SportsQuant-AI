"""
Ballpark locations and orientations, used to turn a weather FORECAST
(compass wind direction) into the model's signed_wind (out / in /
cross relative to the park).

cf_bearing = approximate compass bearing (degrees clockwise from
north) from home plate toward center field. These are approximations
(+/- ~15 degrees) — acceptable because they only bucket wind into
three coarse categories, and MLB Rule 1.04's east-northeast guidance
means most parks cluster in a similar range anyway.

roof=True parks are treated as weather-neutral for forecasts (the
roof may be open, but assuming neutral is the conservative default;
the live feed, when it posts, reports actual conditions either way).
"""

BALLPARKS = {
    "Arizona Diamondbacks":  {"lat": 33.4453, "lon": -112.0667, "cf_bearing": 0,   "roof": True},
    "Athletics":             {"lat": 38.5804, "lon": -121.5133, "cf_bearing": 55,  "roof": False},
    "Atlanta Braves":        {"lat": 33.8908, "lon": -84.4678,  "cf_bearing": 135, "roof": False},
    "Baltimore Orioles":     {"lat": 39.2838, "lon": -76.6215,  "cf_bearing": 30,  "roof": False},
    "Boston Red Sox":        {"lat": 42.3467, "lon": -71.0972,  "cf_bearing": 52,  "roof": False},
    "Chicago Cubs":          {"lat": 41.9484, "lon": -87.6553,  "cf_bearing": 35,  "roof": False},
    "Chicago White Sox":     {"lat": 41.8299, "lon": -87.6338,  "cf_bearing": 125, "roof": False},
    "Cincinnati Reds":       {"lat": 39.0975, "lon": -84.5066,  "cf_bearing": 120, "roof": False},
    "Cleveland Guardians":   {"lat": 41.4962, "lon": -81.6852,  "cf_bearing": 0,   "roof": False},
    "Colorado Rockies":      {"lat": 39.7559, "lon": -104.9942, "cf_bearing": 5,   "roof": False},
    "Detroit Tigers":        {"lat": 42.3390, "lon": -83.0485,  "cf_bearing": 150, "roof": False},
    "Houston Astros":        {"lat": 29.7573, "lon": -95.3555,  "cf_bearing": 345, "roof": True},
    "Kansas City Royals":    {"lat": 39.0517, "lon": -94.4803,  "cf_bearing": 45,  "roof": False},
    "Los Angeles Angels":    {"lat": 33.8003, "lon": -117.8827, "cf_bearing": 65,  "roof": False},
    "Los Angeles Dodgers":   {"lat": 34.0739, "lon": -118.2400, "cf_bearing": 25,  "roof": False},
    "Miami Marlins":         {"lat": 25.7781, "lon": -80.2196,  "cf_bearing": 40,  "roof": True},
    "Milwaukee Brewers":     {"lat": 43.0280, "lon": -87.9712,  "cf_bearing": 130, "roof": True},
    "Minnesota Twins":       {"lat": 44.9817, "lon": -93.2778,  "cf_bearing": 90,  "roof": False},
    "New York Mets":         {"lat": 40.7571, "lon": -73.8458,  "cf_bearing": 30,  "roof": False},
    "New York Yankees":      {"lat": 40.8296, "lon": -73.9262,  "cf_bearing": 75,  "roof": False},
    "Philadelphia Phillies": {"lat": 39.9061, "lon": -75.1665,  "cf_bearing": 10,  "roof": False},
    "Pittsburgh Pirates":    {"lat": 40.4469, "lon": -80.0057,  "cf_bearing": 115, "roof": False},
    "San Diego Padres":      {"lat": 32.7076, "lon": -117.1570, "cf_bearing": 0,   "roof": False},
    "San Francisco Giants":  {"lat": 37.7786, "lon": -122.3893, "cf_bearing": 85,  "roof": False},
    "Seattle Mariners":      {"lat": 47.5914, "lon": -122.3325, "cf_bearing": 45,  "roof": True},
    "St. Louis Cardinals":   {"lat": 38.6226, "lon": -90.1928,  "cf_bearing": 60,  "roof": False},
    "Tampa Bay Rays":        {"lat": 27.7683, "lon": -82.6534,  "cf_bearing": 45,  "roof": True},
    "Texas Rangers":         {"lat": 32.7473, "lon": -97.0847,  "cf_bearing": 15,  "roof": True},
    "Toronto Blue Jays":     {"lat": 43.6414, "lon": -79.3894,  "cf_bearing": 15,  "roof": True},
    "Washington Nationals":  {"lat": 38.8730, "lon": -77.0074,  "cf_bearing": 25,  "roof": False},
}


def wind_direction_to_effect(wind_from_deg, cf_bearing):
    """
    Buckets a meteorological wind direction (degrees the wind blows
    FROM) into 'out' / 'in' / 'cross' relative to a park.
    Wind blows TOWARD (from + 180). Within 45 degrees of center field
    -> out; within 45 degrees of home plate -> in; otherwise cross.
    """
    toward = (float(wind_from_deg) + 180.0) % 360.0

    def angle_gap(a, b):
        d = abs(a - b) % 360.0
        return min(d, 360.0 - d)

    if angle_gap(toward, cf_bearing) <= 45.0:
        return "out"
    if angle_gap(toward, (cf_bearing + 180.0) % 360.0) <= 45.0:
        return "in"
    return "cross"
