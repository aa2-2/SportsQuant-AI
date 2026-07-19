"""
Enhanced game data fetcher - writes to championship SQLite database
Integrates with MLB Stats API for schedule and game data
"""
import sqlite3
import requests
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import sys
import time

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))
from config import DATA_DIR

DATABASE_PATH = DATA_DIR / "sportsquant_ai.db"

def get_db_connection():
    """Get database connection with foreign keys enabled"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def fetch_and_store_games(start_date, end_date):
    """
    Fetch games from MLB Stats API and store in database
    Args:
        start_date: YYYY-MM-DD string
        end_date: YYYY-MM-DD string
    """
    print(f"Fetching games from {start_date} to {end_date}...")

    # MLB Stats API endpoint for schedule
    url = "https://statsapi.mlb.com/api/v1/schedule"
    params = {
        "startDate": start_date,
        "endDate": end_date,
        "sportId": 1,  # MLB
        "hydrate": "team,linescore,probablePitcher,venue,weather"
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Error fetching schedule: {e}")
        return 0

    games_added = 0
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        for date in data.get("dates", []):
            for game in date.get("games", []):
                game_pk = game["gamePk"]
                game_date = game["gameDate"][:10]  # YYYY-MM-DD

                # Extract teams
                away_team = game["teams"]["away"]["team"]["teamName"]
                home_team = game["teams"]["home"]["team"]["teamName"]

                # Extract scores (if game is finished)
                away_score = game["teams"]["away"].get("score")
                home_score = game["teams"]["home"].get("score")

                # Extract venue info
                venue_id = game.get("venue", {}).get("id")

                # Extract weather if available
                weather = game.get("weather", {})
                temperature = weather.get("temp")
                wind_speed = weather.get("wind")
                wind_direction = weather.get("windDesc")

                # First pitch time (UTC)
                first_pitch_utc = game.get("gameDate")

                # Normalize status to match database constraints
                status_raw = game["status"]["detailedState"]
                status_lower = status_raw.lower()
                if status_lower in ['final', 'game over', 'completed']:
                    status = 'final'
                elif status_lower in ['in progress', 'inprogress', 'live']:
                    status = 'in_progress'
                elif status_lower in ['scheduled', 'pre-game', 'pregame', 'preseason']:
                    status = 'scheduled'
                elif status_lower in ['delayed', 'postponed', 'suspended', 'delay']:
                    status = 'delayed'
                else:
                    # Default to scheduled for unknown statuses
                    print(f"[WARN] Unknown status '{status_raw}' for game {game_pk}, defaulting to 'scheduled'")
                    status = 'scheduled'

                # Insert or update game
                try:
                    cursor.execute("""
                    INSERT OR REPLACE INTO games (
                        game_pk, date, home_team, away_team, home_score, away_score,
                        venue_id, temperature, wind_speed, wind_direction,
                        status, first_pitch_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        game_pk, game_date, home_team, away_team, home_score, away_score,
                        venue_id, temperature, wind_speed, wind_direction,
                        status, first_pitch_utc
                    ))

                    games_added += 1

                    # Process probable pitchers if available
                    process_probable_pitchers(cursor, game, game_pk)
                except Exception as e:
                    print(f"[ERROR] Failed to insert game {game_pk}: {e}")
                    continue  # skip to next game

        conn.commit()
        print(f"[OK] Successfully stored {games_added} games")
        return games_added

    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Error storing games: {e}")
        # Don't raise, just return what we have so far
        return games_added
    finally:
        conn.close()

def process_probable_pitchers(cursor, game, game_pk):
    """Extract and store probable pitcher data"""
    away_probable = game["teams"]["away"].get("probablePitcher")
    home_probable = game["teams"]["home"].get("probablePitcher")

    if away_probable:
        insert_pitcher(
            cursor, game_pk,
            away_probable["id"],
            game["teams"]["away"]["team"]["teamName"],
            away_probable
        )

    if home_probable:
        insert_pitcher(
            cursor, game_pk,
            home_probable["id"],
            game["teams"]["home"]["team"]["teamName"],
            home_probable
        )


def insert_pitcher(cursor, game_pk, mlbam_id, team, pitcher_data):
    """Insert or update pitcher data"""
    # Check if pitcher already exists for this game
    cursor.execute(
        "SELECT id FROM pitchers WHERE game_pk = ? AND mlbam_id = ?",
        (game_pk, mlbam_id)
    )
    existing = cursor.fetchone()

    # Extract available stats (may be None for probable pitchers)
    # In a real implementation, we'd fetch seasonal stats here
    # For now, we'll store what we have and update later with actual game data

    if not existing:
        cursor.execute("""
        INSERT INTO pitchers (
            game_pk, mlbam_id, team
        ) VALUES (?, ?, ?)
        """, (game_pk, mlbam_id, team))
    else:
        # Update existing record
        cursor.execute("""
        UPDATE pitchers SET team = ? WHERE id = ?
        """, (team, existing[0]))

def main():
    """Main execution function"""
    # Default to fetching last 7 days and next 7 days
    today = datetime.now().date()
    start_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    end_date = (today + timedelta(days=7)).strftime("%Y-%m-%d")

    # Override with command line arguments if provided
    if len(sys.argv) > 2:
        start_date = sys.argv[1]
        end_date = sys.argv[2]

    print(f"[START] Starting championship-grade data ingestion...")
    print(f"[DATE] Date range: {start_date} to {end_date}")

    # Ensure database exists
    if not DATABASE_PATH.exists():
        print("[SETUP] Initializing database...")
        from init_db import create_database
        create_database()

    # Fetch and store games
    games_count = fetch_and_store_games(start_date, end_date)

    print(f"[TARGET] Mission accomplished: {games_count} games processed")
    print(f"[DISK] Data stored in: {DATABASE_PATH}")

if __name__ == "__main__":
    main()