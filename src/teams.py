"""
Shared team name <-> abbreviation mapping for display.
(Same mapping used by the bullpen feature; kept here so display code
doesn't import from a feature module.)
"""
TEAM_ABBR_TO_NAME = {
    "AZ": "Arizona Diamondbacks", "ATH": "Athletics", "ATL": "Atlanta Braves",
    "BAL": "Baltimore Orioles", "BOS": "Boston Red Sox", "CHC": "Chicago Cubs",
    "CWS": "Chicago White Sox", "CIN": "Cincinnati Reds", "CLE": "Cleveland Guardians",
    "COL": "Colorado Rockies", "DET": "Detroit Tigers", "HOU": "Houston Astros",
    "KC": "Kansas City Royals", "LAA": "Los Angeles Angels", "LAD": "Los Angeles Dodgers",
    "MIA": "Miami Marlins", "MIL": "Milwaukee Brewers", "MIN": "Minnesota Twins",
    "NYM": "New York Mets", "NYY": "New York Yankees", "PHI": "Philadelphia Phillies",
    "PIT": "Pittsburgh Pirates", "SD": "San Diego Padres", "SF": "San Francisco Giants",
    "SEA": "Seattle Mariners", "STL": "St. Louis Cardinals", "TB": "Tampa Bay Rays",
    "TEX": "Texas Rangers", "TOR": "Toronto Blue Jays", "WSH": "Washington Nationals",
}

TEAM_NAME_TO_ABBR = {name: abbr for abbr, name in TEAM_ABBR_TO_NAME.items()}


def abbr(team_name):
    """'San Francisco Giants' -> 'SF' (falls back to first 3 letters)."""
    return TEAM_NAME_TO_ABBR.get(team_name, team_name[:3].upper())
