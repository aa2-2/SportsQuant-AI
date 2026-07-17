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


def format_game_time(iso_utc):
    """
    '2026-07-16T22:10:00Z' -> '6:10 PM ET'.
    Formatted manually: strftime's no-leading-zero codes are platform-
    specific (%-I is Linux-only, %#I is Windows-only) — the old version
    silently returned "" on Windows, which is why the site showed no
    game times.
    """
    if not iso_utc:
        return ""
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        dt = datetime.fromisoformat(str(iso_utc).replace("Z", "+00:00"))
        local = dt.astimezone(ZoneInfo("America/New_York"))
        hour12 = local.hour % 12 or 12
        ampm = "AM" if local.hour < 12 else "PM"
        return f"{hour12}:{local.minute:02d} {ampm} ET"
    except Exception:
        return ""

