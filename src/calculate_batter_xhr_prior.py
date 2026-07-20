#!/usr/bin/env python3
"""
Calculate barrel-based xHR (expected home run) prior for MLB prediction model
Phase 5.2: Barrel-based xHR prior implementation
"""
import sqlite3
import os
from pathlib import Path
from datetime import datetime, timedelta

DATABASE_PATH = "data/sportsquant_ai.db"

def add_xhr_columns():
    """Add xHR-related columns to batters table if they don't exist"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Check if columns exist
    cursor.execute("PRAGMA table_info(batters)")
    columns = [column[1] for column in cursor.fetchall()]

    # Add xHR columns if they don't exist
    xhr_columns = [
        ('xhr_pct_season', 'REAL DEFAULT 0'),
        ('xhr_pct_last_10', 'REAL DEFAULT 0'),
        ('xhr_pct_last_5', 'REAL DEFAULT 0'),
        ('xhr_pct_last_10d', 'REAL DEFAULT 0'),
        ('xhr_pct_vs_lhb', 'REAL DEFAULT 0'),
        ('xhr_pct_vs_rhb', 'REAL DEFAULT 0')
    ]

    for col_name, col_def in xhr_columns:
        if col_name not in columns:
            try:
                cursor.execute(f"ALTER TABLE batters ADD COLUMN {col_name} {col_def}")
                print(f"Added column {col_name} to batters table")
            except Exception as e:
                print(f"Error adding column {col_name}: {e}")

    conn.commit()
    conn.close()

def calculate_league_hr_per_barrel_rate(conn):
    """
    Calculate league HR per barrel rate (home runs / barrels)
    This is the league average HR rate for batted balls that are barrels
    """
    cursor = conn.cursor()

    # Count total barrels and total home runs in the league
    cursor.execute("""
        SELECT
            SUM(CASE WHEN launch_speed >= 98 AND launch_angle BETWEEN 26 AND 30 THEN 1 ELSE 0 END) as total_barrels,
            SUM(CASE WHEN events = 'home_run' THEN 1 ELSE 0 END) as total_hrs
        FROM statcast
        WHERE launch_speed IS NOT NULL AND launch_angle IS NOT NULL
          AND events NOT IN ('walk', 'strikeout', 'hit_by_pitch', 'intentional_walk',
                           'sacrifice_bunt', 'sacrifice_fly')
    """)

    result = cursor.fetchone()
    total_barrels, total_hrs = result

    if total_barrels > 0:
        league_hr_per_barrel = total_hrs / total_barrels
        print(f"League HR per barrel rate: {total_hrs} HRs / {total_barrels} barrels = {league_hr_per_barrel:.4f}")
        return league_hr_per_barrel
    else:
        print("No barrels found in data")
        return 0.0

def calculate_batter_xhr_rates(conn, league_hr_per_barrel):
    """
    Calculate xHR rate for each batter:
    xHR rate = league HR per barrel rate * batter barrel rate
    """
    cursor = conn.cursor()

    # Get all batters
    cursor.execute("SELECT id, mlbam_id FROM batters")
    batters = cursor.fetchall()

    print(f"Calculating xHR rates for {len(batters)} batters...")

    updated = 0
    for batter_id, mlbam_id in batters:
        try:
            # Get batter's barrel rates for different time windows
            ball_in_play = """
                (launch_speed IS NOT NULL AND launch_angle IS NOT NULL)
                AND events NOT IN ('walk', 'strikeout', 'hit_by_pitch', 'intentional_walk',
                                  'sacrifice_bunt', 'sacrifice_fly')
            """

            # Get today's date for reference (use max date in DB as "today")
            cursor.execute("SELECT MAX(game_date) FROM statcast")
            today_result = cursor.fetchone()
            today = today_result[0] if today_result and today_result[0] else '2026-03-01'

            # Define time windows
            season_start = '2026-03-01'  # Approximate start of season
            ten_days_ago = (datetime.strptime(today, '%Y-%m-%d') - timedelta(days=10)).strftime('%Y-%m-%d')

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
            barrel_pct_season = barrels / total_bip if total_bip > 0 else 0.0
            xhr_pct_season = league_hr_per_barrel * barrel_pct_season

            # 2. Last 10 games
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
                barrel_pct_last_10 = barrels / total_bip if total_bip > 0 else 0.0
                xhr_pct_last_10 = league_hr_per_barrel * barrel_pct_last_10
            else:
                barrel_pct_last_10 = 0.0
                xhr_pct_last_10 = 0.0

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
                barrel_pct_last_5 = barrels / total_bip if total_bip > 0 else 0.0
                xhr_pct_last_5 = league_hr_per_barrel * barrel_pct_last_5
            else:
                barrel_pct_last_5 = 0.0
                xhr_pct_last_5 = 0.0

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
            barrel_pct_last_10d = barrels / total_bip if total_bip > 0 else 0.0
            xhr_pct_last_10d = league_hr_per_barrel * barrel_pct_last_10d

            # 5. vs LHB (left-handed pitchers) - approximation using overall rate
            # Note: We don't have pitcher handedness data, so we'll approximate
            barrel_pct_vs_lhb = barrel_pct_season  # Placeholder
            xhr_pct_vs_lhb = league_hr_per_barrel * barrel_pct_vs_lhb

            # 6. vs RHB (right-handed pitchers) - approximation using overall rate
            barrel_pct_vs_rhb = barrel_pct_season  # Placeholder
            xhr_pct_vs_rhb = league_hr_per_barrel * barrel_pct_vs_rhb

            # Update the batter record with xHR rates
            cursor.execute("""
                UPDATE batters SET
                    xhr_pct_season = ?,
                    xhr_pct_last_10 = ?,
                    xhr_pct_last_5 = ?,
                    xhr_pct_last_10d = ?,
                    xhr_pct_vs_lhb = ?,
                    xhr_pct_vs_rhb = ?
                WHERE id = ?
            """, (
                xhr_pct_season,
                xhr_pct_last_10,
                xhr_pct_last_5,
                xhr_pct_last_10d,
                xhr_pct_vs_lhb,
                xhr_pct_vs_rhb,
                batter_id
            ))

            if cursor.rowcount > 0:
                updated += 1

        except Exception as e:
            print(f"Error calculating xHR rates for batter {mlbam_id}: {e}")

    print(f"Updated {updated} batter records with xHR rates")
    conn.commit()

def verify_results(conn):
    """Verify the results by showing some sample data"""
    cursor = conn.cursor()

    print("\n=== Verification ===")

    # Show some sample batter xHR rates
    cursor.execute("""
        SELECT mlbam_id, barrel_pct_season, xhr_pct_season
        FROM batters
        WHERE barrel_pct_season > 0
        ORDER BY xhr_pct_season DESC
        LIMIT 10
    """)

    print("\nTop 10 batters by xHR rate (season):")
    print("MLBAM_ID    Barrel%    xHR%")
    print("-" * 30)
    for row in cursor.fetchall():
        mlbam_id, barrel_pct, xhr_pct = row
        print(f"{mlbam_id:<11} {barrel_pct*100:5.2f}% {xhr_pct*100:5.2f}%")

    # Show overall stats
    cursor.execute("""
        SELECT
            COUNT(*) as total_batters,
            COUNT(CASE WHEN barrel_pct_season > 0 THEN 1 END) as with_barrel_data,
            COUNT(CASE WHEN xhr_pct_season > 0 THEN 1 END) as with_xhr_data,
            AVG(barrel_pct_season) as avg_barrel_rate,
            AVG(xhr_pct_season) as avg_xhr_rate,
            MAX(xhr_pct_season) as max_xhr_rate
        FROM batters
    """)

    result = cursor.fetchone()
    total, with_barrel, with_xhr, avg_barrel, avg_xhr, max_xhr = result
    print(f"\nStatistics:")
    print(f"  Total batters in DB: {total}")
    print(f"  Batters with barrel data: {with_barrel}")
    print(f"  Batters with xHR data: {with_xhr}")
    print(f"  Average barrel rate: {avg_barrel*100:.2f}%")
    print(f"  Average xHR rate: {avg_xhr*100:.2f}%")
    print(f"  Maximum xHR rate: {max_xhr*100:.2f}%")

def main():
    """Main function"""
    print("Starting barrel-based xHR prior calculation...")

    # Connect to database
    conn = sqlite3.connect(DATABASE_PATH)
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        # Step 1: Add xHR columns to batters table if they don't exist
        print("\n1. Adding xHR columns to batters table...")
        add_xhr_columns()

        # Step 2: Calculate league HR per barrel rate
        print("\n2. Calculating league HR per barrel rate...")
        league_hr_per_barrel = calculate_league_hr_per_barrel_rate(conn)

        # Step 3: Calculate and update xHR rates for each batter
        print("\n3. Calculating xHR rates for batters...")
        calculate_batter_xhr_rates(conn, league_hr_per_barrel)

        # Step 4: Verify results
        print("\n4. Verifying results...")
        verify_results(conn)

        print("\n[SUCCESS] Barrel-based xHR prior calculation completed successfully!")

    except Exception as e:
        print(f"\n[ERROR] Error: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    main()