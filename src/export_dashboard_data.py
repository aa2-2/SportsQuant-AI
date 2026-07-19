#!/usr/bin/env python3
"""
Export dashboard data from championship SQLite database to JSON files
for the MLBQuant website frontend.
Works with the actual database schema we've been using.
"""
import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime, timedelta

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "sportsquant_ai.db"
OUTPUT_DIR = PROJECT_ROOT / "docs" / "data"

# Ensure output directory exists
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def get_db_connection():
    """Create and return a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    return conn

def export_recent_games():
    """Export recent games with weather and basic info."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get games from the last 7 days and next 3 days
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    three_days_ahead = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')

    query = """
    SELECT
        g.game_pk,
        g.date,
        g.home_team,
        g.away_team,
        g.home_score,
        g.away_score,
        g.status,
        g.temperature,
        g.wind_speed,
        g.wind_direction,
        w.hr_weather_adjustment,
        w.wind_in_cf,
        w.wind_side_to_side
    FROM games g
    LEFT JOIN weather w ON g.game_pk = w.game_pk
    WHERE g.date BETWEEN ? AND ?
    ORDER BY g.date DESC
    """

    cursor.execute(query, (seven_days_ago, three_days_ahead))
    rows = cursor.fetchall()

    games = []
    for row in rows:
        game = dict(row)
        # Format date for display
        try:
            game['date_formatted'] = datetime.strptime(game['date'], '%Y-%m-%d').strftime('%b %d')
        except:
            game['date_formatted'] = game['date']

        # Determine game status display
        if game['status'] == 'scheduled':
            game['status_display'] = 'Upcoming'
        elif game['status'] == 'in_progress':
            game['status_display'] = 'Live'
        else:
            game['status_display'] = game['status'].title() if game['status'] else 'Unknown'

        # Format weather data
        game['temp_f'] = f"{game['temperature']}°F" if game['temperature'] is not None else "N/A"
        game['wind_display'] = "Calm"
        if game['wind_speed'] is not None and game['wind_direction'] is not None:
            try:
                wind_speed = float(game['wind_speed'])
                wind_dir = int(float(game['wind_direction']))
                direction = cardinal_direction(wind_dir)
                game['wind_display'] = f"{wind_speed} mph {direction}"
            except:
                game['wind_display'] = f"{game['wind_speed']} mph {game['wind_direction']}"

        game['hr_impact'] = f"{game['hr_weather_adjustment']:+.1f}%" if game['hr_weather_adjustment'] is not None else "0.0%"

        games.append(game)

    conn.close()

    # Write to file
    output_path = OUTPUT_DIR / "recent_games.json"
    with open(output_path, 'w') as f:
        json.dump(games, f, indent=2)

    print(f"Exported {len(games)} recent games to {output_path}")
    return games

def export_statcast_summary():
    """Export Statcast summary statistics including barrel rates."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get stats for the last 30 days of data
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

    query = """
    SELECT
        COUNT(*) as total_pitches,
        SUM(is_barrel) as total_barrels,
        AVG(launch_speed) as avg_exit_velocity,
        AVG(launch_angle) as avg_launch_angle,
        COUNT(CASE WHEN launch_speed IS NOT NULL AND launch_angle IS NOT NULL THEN 1 END) as batted_balls,
        SUM(CASE WHEN events = 'home_run' THEN 1 ELSE 0 END) as total_home_runs
    FROM statcast
    WHERE game_date >= ?
    """

    cursor.execute(query, (thirty_days_ago,))
    row = cursor.fetchone()

    if row and row['total_pitches'] > 0:
        total_pitches = row['total_pitches']
        total_barrels = row['total_barrels'] or 0
        batted_balls = row['batted_balls'] or 0
        total_hrs = row['total_home_runs'] or 0

        stats = {
            'total_pitches': total_pitches,
            'total_barrels': total_barrels,
            'barrel_percentage': round((total_barrels / total_pitches) * 100, 2),
            'avg_exit_velocity': round(row['avg_exit_velocity'] or 0, 1),
            'avg_launch_angle': round(row['avg_launch_angle'] or 0, 1),
            'batted_balls': batted_balls,
            'total_home_runs': total_hrs,
            'hr_per_batted_ball': round((total_hrs / max(batted_balls, 1)) * 100, 2),
            'solid_contact_rate': 0.0,  # We'll calculate if we have the data
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        # Try to get solid contact data if available
        try:
            solid_query = """
            SELECT
                SUM(solid_contact) as total_solid
            FROM statcast
            WHERE game_date >= ? AND solid_contact IS NOT NULL
            """
            cursor.execute(solid_query, (thirty_days_ago,))
            solid_row = cursor.fetchone()
            if solid_row and solid_row['total_solid'] is not None:
                stats['solid_contact_rate'] = round((solid_row['total_solid'] / max(batted_balls, 1)) * 100, 2)
        except:
            pass  # Keep default 0.0 if column doesn't exist

    else:
        stats = {
            'total_pitches': 0,
            'total_barrels': 0,
            'barrel_percentage': 0.0,
            'avg_exit_velocity': 0.0,
            'avg_launch_angle': 0.0,
            'batted_balls': 0,
            'total_home_runs': 0,
            'hr_per_batted_ball': 0.0,
            'solid_contact_rate': 0.0,
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    conn.close()

    # Write to file
    output_path = OUTPUT_DIR / "statcast_summary.json"
    with open(output_path, 'w') as f:
        json.dump(stats, f, indent=2)

    print(f"Exported Statcast summary to {output_path}")
    return stats

def export_weather_impact():
    """Export weather impact data for upcoming games."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get upcoming games with weather data
    today = datetime.now().strftime('%Y-%m-%d')
    seven_days_ahead = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')

    query = """
    SELECT
        g.game_pk,
        g.date,
        g.home_team,
        g.away_team,
        g.temperature,
        g.wind_speed,
        g.wind_direction,
        w.hr_weather_adjustment,
        w.wind_in_cf,
        w.wind_side_to_side,
        w.weather_main,
        w.weather_description
    FROM games g
    LEFT JOIN weather w ON g.game_pk = w.game_pk
    WHERE g.date BETWEEN ? AND ?
      AND g.status = 'scheduled'
      AND w.hr_weather_adjustment IS NOT NULL
    ORDER BY g.date
    LIMIT 10
    """

    cursor.execute(query, (today, seven_days_ahead))
    rows = cursor.fetchall()

    weather_impacts = []
    for row in rows:
        impact = dict(row)
        # Format for display
        try:
            impact['date_formatted'] = datetime.strptime(impact['date'], '%Y-%m-%d').strftime('%b %d')
        except:
            impact['date_formatted'] = impact['date']

        impact['hr_impact_display'] = f"{impact['hr_weather_adjustment']:+.1f}%" if impact['hr_weather_adjustment'] is not None else "0.0%"

        # Format wind
        if impact['wind_speed'] is not None and impact['wind_direction'] is not None:
            try:
                wind_speed = float(impact['wind_speed'])
                wind_dir = int(float(impact['wind_direction']))
                direction = cardinal_direction(wind_dir)
                impact['wind_display'] = f"{wind_speed} mph {direction}"
            except:
                impact['wind_display'] = f"{impact['wind_speed']} mph {impact['wind_direction']}"
        else:
            impact['wind_display'] = "Calm"

        impact['temp_f'] = f"{impact['temperature']}°F" if impact['temperature'] is not None else "N/A"

        weather_impacts.append(impact)

    conn.close()

    # Write to file
    output_path = OUTPUT_DIR / "weather_impact.json"
    with open(output_path, 'w') as f:
        json.dump(weather_impacts, f, indent=2)

    print(f"Exported {len(weather_impacts)} weather impact records to {output_path}")
    return weather_impacts

def cardinal_direction(degrees):
    """Convert wind degrees to cardinal direction."""
    if degrees is None:
        return "N/A"
    try:
        degrees = float(degrees)
        directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                      "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
        index = round(degrees / 22.5) % 16
        return directions[index]
    except:
        return "N/A"

def main():
    """Main export function."""
    print("Starting dashboard data export from championship database...")
    print(f"Database: {DB_PATH}")
    print(f"Output directory: {OUTPUT_DIR}")
    print("-" * 50)

    try:
        # Export all data sets
        export_recent_games()
        export_statcast_summary()
        export_weather_impact()

        print("-" * 50)
        print("SUCCESS: All data exported successfully!")
        print(f"OUTPUT: JSON files available in: {OUTPUT_DIR}")
        print("\nGenerated files:")
        for file in os.listdir(OUTPUT_DIR):
            print(f"  * {file}")

    except Exception as e:
        print(f"ERROR: Error during export: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    main()