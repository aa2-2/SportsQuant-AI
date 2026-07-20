#!/usr/bin/env python3
"""
Update batter barrel rates in the database.
Calculates barrel rates for different time windows:
- season (2026)
- last 10 games
- last 5 games
- last 10 days
- vs LHB
- vs RHB
"""

import sqlite3
import os
from datetime import datetime, timedelta
from pathlib import Path

DATABASE_PATH = "data/sportsquant_ai.db"

def get_season_start(year):
    """Get approximate start date for MLB season"""
    return f"{year}-03-01"  # Approximate start of season

def populate_batters_table(conn):
    """Populate batters table with unique batter IDs from statcast data"""
    cursor = conn.cursor()

    # Get distinct batter IDs from statcast
    cursor.execute("""
        SELECT DISTINCT batter_id
        FROM statcast
        WHERE batter_id IS NOT NULL
    """)
    batter_ids = [row[0] for row in cursor.fetchall()]

    print(f"Found {len(batter_ids)} unique batters in statcast data")

    # Insert each batter into the batters table
    # Using INSERT OR IGNORE to handle duplicates
    inserted = 0
    for batter_id in batter_ids:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO batters (mlbam_id)
                VALUES (?)
            """, (batter_id,))
            if cursor.rowcount > 0:
                inserted += 1
        except Exception as e:
            print(f"Error inserting batter {batter_id}: {e}")

    print(f"Inserted {inserted} new batters into batters table")
    conn.commit()

def get_ball_in_play_condition():
    """Return SQL condition for ball in play"""
    return """
        (launch_speed IS NOT NULL AND launch_angle IS NOT NULL)
        AND events NOT IN ('walk', 'strikeout', 'hit_by_pitch', 'intentional_walk',
                          'sacrifice_bunt', 'sacrifice_fly')
    """

def calculate_batter_barrel_rates(conn):
    """Calculate barrel rates for each batter and update the database"""
    cursor = conn.cursor()

    # Get all batters
    cursor.execute("SELECT id, mlbam_id FROM batters")
    batters = cursor.fetchall()

    print(f"Calculating barrel rates for {len(batters)} batters...")

    updated = 0
    for batter_id, mlbam_id in batters:
        try:
            # Get barrel rates for this batter
            rates = calculate_rates_for_batter(conn, mlbam_id)

            # Update the batter record
            cursor.execute("""
                UPDATE batters SET
                    barrel_pct_season = ?,
                    barrel_pct_last_10 = ?,
                    barrel_pct_last_5 = ?,
                    barrel_pct_last_10d = ?,
                    vs_lhb_barrel_pct = ?,
                    vs_rhb_barrel_pct = ?
                WHERE id = ?
            """, (
                rates['season'],
                rates['last_10_games'],
                rates['last_5_games'],
                rates['last_10_days'],
                rates['vs_lhb'],
                rates['vs_rhb'],
                batter_id
            ))

            if cursor.rowcount > 0:
                updated += 1

        except Exception as e:
            print(f"Error calculating rates for batter {mlbam_id}: {e}")

    print(f"Updated {updated} batter records")
    conn.commit()

def calculate_rates_for_batter(conn, mlbam_id):
    """Calculate all barrel rates for a specific batter"""
    cursor = conn.cursor()

    ball_in_play = get_ball_in_play_condition()

    # Get today's date for reference (use max date in DB as "today")
    cursor.execute("SELECT MAX(game_date) FROM statcast")
    today_result = cursor.fetchone()
    today = today_result[0] if today_result and today_result[0] else '2026-07-19'  # Use current date

    # Define time windows
    season_start = get_season_start(2026)  # 2026 season start
    ten_days_ago = (datetime.strptime(today, '%Y-%m-%d') - timedelta(days=10)).strftime('%Y-%m-%d')

    rates = {}

    # 1. Season barrel rate (2026 season)
    cursor.execute(f"""
        SELECT
            COUNT(*) as total_bip,
            SUM(CASE WHEN launch_speed >= 98 AND launch_angle BETWEEN 26 AND 30 THEN 1 ELSE 0 END) as barrels
        FROM statcast
        WHERE batter_id = ?
        AND game_date >= ?
        AND game_date <= ?
        AND {ball_in_play}
    """, (mlbam_id, season_start, today))

    result = cursor.fetchone()
    total_bip, barrels = result
    rates['season'] = barrels / total_bip if total_bip > 0 else 0.0

    # 2. Last 10 games
    # First get the last 10 game dates for this batter
    cursor.execute("""
        SELECT DISTINCT game_date
        FROM statcast
        WHERE batter_id = ?
        AND game_date IS NOT NULL
        ORDER BY game_date DESC
        LIMIT 10
    """, (mlbam_id,))

    last_10_dates = [row[0] for row in cursor.fetchall()]
    if last_10_dates:
        earliest_date = min(last_10_dates)
        cursor.execute(f"""
            SELECT
                COUNT(*) as total_bip,
                SUM(CASE WHEN launch_speed >= 98 AND launch_angle BETWEEN 26 AND 30 THEN 1 ELSE 0 END) as barrels
            FROM statcast
            WHERE batter_id = ?
            AND game_date >= ?
            AND game_date <= ?
            AND {ball_in_play}
        """, (mlbam_id, earliest_date, today))

        result = cursor.fetchone()
        total_bip, barrels = result
        rates['last_10_games'] = barrels / total_bip if total_bip > 0 else 0.0
    else:
        rates['last_10_games'] = 0.0

    # 3. Last 5 games
    cursor.execute("""
        SELECT DISTINCT game_date
        FROM statcast
        WHERE batter_id = ?
        AND game_date IS NOT NULL
        ORDER BY game_date DESC
        LIMIT 5
    """, (mlbam_id,))

    last_5_dates = [row[0] for row in cursor.fetchall()]
    if last_5_dates:
        earliest_date = min(last_5_dates)
        cursor.execute(f"""
            SELECT
                COUNT(*) as total_bip,
                SUM(CASE WHEN launch_speed >= 98 AND launch_angle BETWEEN 26 AND 30 THEN 1 ELSE 0 END) as barrels
            FROM statcast
            WHERE batter_id = ?
            AND game_date >= ?
            AND game_date <= ?
            AND {ball_in_play}
        """, (mlbam_id, earliest_date, today))

        result = cursor.fetchone()
        total_bip, barrels = result
        rates['last_5_games'] = barrels / total_bip if total_bip > 0 else 0.0
    else:
        rates['last_5_games'] = 0.0

    # 4. Last 10 days
    cursor.execute(f"""
        SELECT
            COUNT(*) as total_bip,
            SUM(CASE WHEN launch_speed >= 98 AND launch_angle BETWEEN 26 AND 30 THEN 1 ELSE 0 END) as barrels
        FROM statcast
        WHERE batter_id = ?
        AND game_date >= ?
        AND game_date <= ?
        AND {ball_in_play}
    """, (mlbam_id, ten_days_ago, today))

    result = cursor.fetchone()
    total_bip, barrels = result
    rates['last_10_days'] = barrels / total_bip if total_bip > 0 else 0.0

    # 5. vs LHB (left-handed pitchers) - approximation using overall rate
    # Note: We don't have pitcher handedness data, so we'll approximate with overall rate
    rates['vs_lhb'] = rates['season']  # Placeholder

    # 6. vs RHB (right-handed pitchers) - approximation using overall rate
    rates['vs_rhb'] = rates['season']  # Placeholder

    return rates

def verify_results(conn):
    """Verify the results by showing some sample data"""
    cursor = conn.cursor()

    print("\n=== Verification ===")

    # Show some sample batter rates
    cursor.execute("""
        SELECT mlbam_id, barrel_pct_season, barrel_pct_last_10, barrel_pct_last_5, barrel_pct_last_10d
        FROM batters
        WHERE barrel_pct_season > 0
        ORDER BY barrel_pct_season DESC
        LIMIT 10
    """)

    print("\nTop 10 batters by season barrel rate:")
    print("MLBAM_ID    Sea%    10G%    5G%    10D%")
    print("-" * 40)
    for row in cursor.fetchall():
        mlbam_id, sea, g10, g5, d10 = row
        print(f"{mlbam_id:<11} {sea*100:5.2f}% {g10*100:5.2f}% {g5*100:5.2f}% {d10*100:5.2f}%")

    # Show overall stats
    cursor.execute("""
        SELECT
            COUNT(*) as total_batters,
            COUNT(CASE WHEN barrel_pct_season > 0 THEN 1 END) as with_data,
            AVG(barrel_pct_season) as avg_season_rate,
            MAX(barrel_pct_season) as max_season_rate
        FROM batters
    """)

    result = cursor.fetchone()
    total, with_data, avg_rate, max_rate = result
    print(f"\nStatistics:")
    print(f"  Total batters in DB: {total}")
    print(f"  Batters with barrel data: {with_data}")
    print(f"  Average season barrel rate: {avg_rate*100:.2f}%")
    print(f"  Maximum season barrel rate: {max_rate*100:.2f}%")

def main():
    """Main function"""
    print("Starting barrel rate calculation...")

    # Connect to database
    conn = sqlite3.connect(DATABASE_PATH)
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        # Step 1: Populate batters table
        print("\n1. Populating batters table...")
        populate_batters_table(conn)

        # Step 2: Calculate and update barrel rates
        print("\n2. Calculating barrel rates...")
        calculate_batter_barrel_rates(conn)

        # Step 3: Verify results
        print("\n3. Verifying results...")
        verify_results(conn)

        print("\n[SUCCESS] Barrel rate update completed successfully!")

    except Exception as e:
        print(f"\n[ERROR] Error: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    main()