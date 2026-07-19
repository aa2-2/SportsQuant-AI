#!/usr/bin/env python3
"""
Populate statcast table with barrel data from CSV files
Phase 5.2: Barrel-based xHR prior implementation
"""
import sqlite3
import pandas as pd
import os
from pathlib import Path

# Project root is two levels up from this script (src/ -> project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "sportsquant_ai.db"
STATCAST_FILES = [
    DATA_DIR / "statcast_2024.csv",
    DATA_DIR / "statcast_2025.csv",
    DATA_DIR / "statcast_2026.csv"
]

def is_barrel(row):
    """
    Determine if a pitch is a barrel according to MLB definition:
    Exit velocity >= 98 mph AND launch angle between 26-30 degrees
    """
    # Handle missing values
    if pd.isna(row.get('launch_speed')) or pd.isna(row.get('launch_angle')):
        return 0

    exit_velocity = row['launch_speed']  # mph
    launch_angle = row['launch_angle']   # degrees

    # MLB barrel definition: exit_velocity >= 98 AND launch_angle BETWEEN 26 AND 30
    if exit_velocity >= 98 and 26 <= launch_angle <= 30:
        return 1
    return 0

def is_solid_contact(row):
    """
    Sweet spot: exit_velocity >= 95 AND launch_angle BETWEEN 8 AND 50
    """
    if pd.isna(row.get('launch_speed')) or pd.isna(row.get('launch_angle')):
        return 0

    exit_velocity = row['launch_speed']
    launch_angle = row['launch_angle']

    if exit_velocity >= 95 and 8 <= launch_angle <= 50:
        return 1
    return 0

def is_burned_contact(row):
    """
    Flare/burner: exit_velocity >= 95 AND launch_angle NOT BETWEEN 8 AND 50
    """
    if pd.isna(row.get('launch_speed')) or pd.isna(row.get('launch_angle')):
        return 0

    exit_velocity = row['launch_speed']
    launch_angle = row['launch_angle']

    if exit_velocity >= 95 and not (8 <= launch_angle <= 50):
        return 1
    return 0

def is_flare_burner(row):
    """
    Flare/burner: exit_velocity BETWEEN 89 AND 91 AND launch_angle BETWEEN 24 AND 30
    """
    if pd.isna(row.get('launch_speed')) or pd.isna(row.get('launch_angle')):
        return 0

    exit_velocity = row['launch_speed']
    launch_angle = row['launch_angle']

    if 89 <= exit_velocity <= 91 and 24 <= launch_angle <= 30:
        return 1
    return 0

def map_statcast_row_to_db(row):
    """
    Map a row from Statcast CSV to database columns
    """
    # Map column names from CSV to database
    mapped = {
        'game_pk': int(row['game_pk']) if not pd.isna(row['game_pk']) else None,
        'inning': int(row['inning']) if not pd.isna(row['inning']) else None,
        'half_inning': row['inning_topbot'] if not pd.isna(row['inning_topbot']) else None,
        'balls': int(row['balls']) if not pd.isna(row['balls']) else None,
        'strikes': int(row['strikes']) if not pd.isna(row['strikes']) else None,
        'outs_when_up': int(row['outs_when_up']) if not pd.isna(row['outs_when_up']) else None,
        'batter_id': int(row['batter']) if not pd.isna(row['batter']) else None,
        'pitcher_id': int(row['pitcher']) if not pd.isna(row['pitcher']) else None,
        'pitch_type': str(row['pitch_type']) if not pd.isna(row['pitch_type']) else None,
        'pitch_number': int(row['pitch_number']) if not pd.isna(row['pitch_number']) else None,
        'release_speed': float(row['release_speed']) if not pd.isna(row['release_speed']) else None,
        'release_pos_x': float(row['release_pos_x']) if not pd.isna(row['release_pos_x']) else None,
        'release_pos_y': float(row['release_pos_y']) if not pd.isna(row['release_pos_y']) else None,
        'release_pos_z': float(row['release_pos_z']) if not pd.isna(row['release_pos_z']) else None,
        'release_spin_rate': float(row['release_spin_rate']) if not pd.isna(row['release_spin_rate']) else None,
        'release_spin_dir': int(row['spin_dir']) if not pd.isna(row['spin_dir']) else None,
        'launch_speed': float(row['launch_speed']) if not pd.isna(row['launch_speed']) else None,
        'launch_angle': float(row['launch_angle']) if not pd.isna(row['launch_angle']) else None,
        'bb_type': str(row['bb_type']) if not pd.isna(row['bb_type']) else None,
        'events': str(row['events']) if not pd.isna(row['events']) else None,
        'is_barrel': is_barrel(row),
        'solid_contact': is_solid_contact(row),
        'burned_contact': is_burned_contact(row),
        'flare_burner': is_flare_burner(row),
        'babip': float(row['babip_value']) if not pd.isna(row['babip_value']) else None,
        'slg': float(row['slg']) if not pd.isna(row['slg']) else None,
        'woba_value': float(row['woba_value']) if not pd.isna(row['woba_value']) else None,
        'woba_denom': float(row['woba_denom']) if not pd.isna(row['woba_denom']) else None,
        'game_date': str(row['game_date']) if not pd.isna(row['game_date']) else None,
        'inning_topbot': str(row['inning_topbot']) if not pd.isna(row['inning_topbot']) else None
    }

    return mapped

def populate_statcast_table():
    """
    Main function to populate the statcast table from CSV files
    """
    print("Starting Statcast data import for barrel-based xHR calculation...")

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Clear existing data (optional - uncomment if you want to refresh)
    # cursor.execute("DELETE FROM statcast")
    # conn.commit()

    # Process each Statcast file
    total_rows_inserted = 0

    for statcast_file in STATCAST_FILES:
        if not statcast_file.exists():
            print(f"Warning: File {statcast_file} not found, skipping...")
            continue

        print(f"\nProcessing {statcast_file.name}...")

        # Read CSV in chunks to handle large files
        chunk_size = 10000
        chunks_processed = 0

        try:
            for chunk in pd.read_csv(statcast_file, chunksize=chunk_size, low_memory=False):
                chunks_processed += 1
                print(f"  Processing chunk {chunks_processed} ({len(chunk)} rows)...")

                # Prepare data for insertion
                rows_to_insert = []
                for _, row in chunk.iterrows():
                    try:
                        mapped_data = map_statcast_row_to_db(row)

                        # Prepare SQL INSERT
                        columns = ', '.join([f'"{col}"' for col in mapped_data.keys()])
                        placeholders = ', '.join(['?' for _ in mapped_data])
                        sql = f"INSERT INTO statcast ({columns}) VALUES ({placeholders})"

                        values = list(mapped_data.values())
                        rows_to_insert.append(values)

                    except Exception as e:
                        # Skip problematic rows but continue processing
                        print(f"    Warning: Skipping row due to error: {e}")
                        continue

                # Insert chunk into database
                if rows_to_insert:
                    # Get columns from first row
                    sample_row = map_statcast_row_to_db(chunk.iloc[0]) if len(chunk) > 0 else {}
                    columns = list(sample_row.keys())
                    placeholders = ', '.join(['?' for _ in columns])
                    sql = f"INSERT INTO statcast ({', '.join(columns)}) VALUES ({placeholders})"
                    cursor.executemany(sql, rows_to_insert)

                    conn.commit()
                    total_rows_inserted += len(rows_to_insert)
                    print(f"    Inserted {len(rows_to_insert)} rows (total: {total_rows_inserted})")

        except Exception as e:
            print(f"Error processing {statcast_file}: {e}")
            continue

    # Get final count
    cursor.execute("SELECT COUNT(*) FROM statcast")
    count = cursor.fetchone()[0]
    print(f"\nStatcast table now contains {count} rows")

    # Show some barrel statistics
    cursor.execute("SELECT COUNT(*) FROM statcast WHERE is_barrel = 1")
    barrel_count = cursor.fetchone()[0]
    print(f"Barrels found: {barrel_count} ({barrel_count/count*100:.2f}% of total)" if count > 0 else "Barrels found: 0")

    cursor.execute("SELECT COUNT(*) FROM statcast WHERE launch_speed IS NOT NULL AND launch_angle IS NOT NULL")
    batted_ball_count = cursor.fetchone()[0]
    print(f"Balls in play with launch data: {batted_ball_count}")

    conn.close()
    print("\nStatcast import completed!")

if __name__ == "__main__":
    populate_statcast_table()