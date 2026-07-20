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

def map_and_rename_columns(df):
    """
    Rename columns from Statcast CSV to match our database schema and add missing columns.
    Also compute the elite metrics (is_barrel, solid_contact, burned_contact, flare_burner).
    """
    # Create a copy to avoid SettingWithCopyWarning
    df = df.copy()

    # Rename columns to match our expected names
    rename_mapping = {
        'game_pk': 'game_pk',
        'inning': 'inning',
        'inning_topbot': 'half_inning',  # we'll also keep a copy for inning_topbot column
        'batter': 'batter_id',
        'pitcher': 'pitcher_id',
        'pitch_type': 'pitch_type',
        'pitch_number': 'pitch_number',
        'release_speed': 'release_speed',
        'release_pos_x': 'release_pos_x',
        'release_pos_y': 'release_pos_y',
        'release_pos_z': 'release_pos_z',
        'release_spin_rate': 'release_spin_rate',
        'spin_dir': 'release_spin_dir',
        'launch_speed': 'launch_speed',
        'launch_angle': 'launch_angle',
        'bb_type': 'bb_type',
        'events': 'events',
        'babip_value': 'babip',
        'estimated_slg_using_speedangle': 'slg',
        'woba_value': 'woba_value',
        'woba_denom': 'woba_denom',
        'game_date': 'game_date'
    }

    # Rename only the columns that exist
    df_renamed = df.rename(columns={k: v for k, v in rename_mapping.items() if k in df.columns})

    # Ensure we have the inning_topbot column (duplicate of half_inning for our table)
    df_renamed['inning_topbot'] = df_renamed['half_inning']

    # Add missing columns that are not in CSV
    df_renamed['launch_direction'] = None  # Not available in Statcast CSV

    # Ensure half_inning is uppercase for CHECK constraint
    df_renamed['half_inning'] = df_renamed['half_inning'].str.upper()

    # Compute the elite metrics
    df_renamed['is_barrel'] = df_renamed.apply(is_barrel, axis=1)
    df_renamed['solid_contact'] = df_renamed.apply(is_solid_contact, axis=1)
    df_renamed['burned_contact'] = df_renamed.apply(is_burned_contact, axis=1)
    df_renamed['flare_burner'] = df_renamed.apply(is_flare_burner, axis=1)

    return df_renamed

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
    total_rows_skipped = 0

    # Define columns that are NOT NULL in the statcast table
    not_null_columns = [
        'game_pk', 'inning', 'half_inning', 'balls', 'strikes', 'outs_when_up',
        'batter_id', 'pitcher_id', 'pitch_type', 'pitch_number', 'release_speed'
    ]

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

                # Replace empty strings with NaN for consistency
                chunk = chunk.replace(r'^\s*$', pd.NA, regex=True)

                # Rename and map columns
                try:
                    renamed_chunk = map_and_rename_columns(chunk)
                except Exception as e:
                    print(f"    Error renaming columns: {e}")
                    continue

                # Identify rows with missing values in NOT NULL columns
                # Ensure all required columns are present (some may be missing if not in CSV)
                missing_cols = [col for col in not_null_columns if col not in renamed_chunk.columns]
                if missing_cols:
                    print(f"    Warning: Missing columns after rename: {missing_cols}")
                    # If any required column is missing, we cannot process this chunk reliably
                    # We'll skip this chunk for safety
                    total_rows_skipped += len(chunk)
                    continue

                missing_mask = renamed_chunk[not_null_columns].isna().any(axis=1)
                valid_chunk = renamed_chunk[~missing_mask].copy()
                skipped_count = len(chunk) - len(valid_chunk)
                total_rows_skipped += skipped_count
                if skipped_count > 0:
                    print(f"    Skipped {skipped_count} rows due to missing NOT NULL fields")

                # Prepare data for insertion
                if len(valid_chunk) > 0:
                    # Define the columns we want to insert (based on the statcast table schema)
                    # We exclude the 'id' column because it is AUTOINCREMENT
                    insert_columns = [
                        'game_pk', 'inning', 'half_inning', 'balls', 'strikes', 'outs_when_up',
                        'batter_id', 'pitcher_id', 'pitch_type', 'pitch_number', 'release_speed',
                        'release_pos_x', 'release_pos_y', 'release_pos_z', 'release_spin_rate',
                        'release_spin_dir', 'launch_speed', 'launch_angle', 'launch_direction',
                        'bb_type', 'events', 'is_barrel', 'solid_contact', 'burned_contact',
                        'flare_burner', 'babip', 'slg', 'woba_value', 'woba_denom',
                        'game_date', 'inning_topbot'
                    ]

                    # Ensure we only take columns that exist in the valid_chunk (should all exist after mapping)
                    # But to be safe, we'll intersect with the columns of valid_chunk
                    cols_to_insert = [col for col in insert_columns if col in valid_chunk.columns]

                    # Prepare the SQL statement
                    placeholders = ', '.join(['?' for _ in cols_to_insert])
                    sql = f"INSERT INTO statcast ({', '.join(cols_to_insert)}) VALUES ({placeholders})"

                    # Convert DataFrame rows to list of tuples
                    # Replace NaN with None for SQL
                    values_list = []
                    for _, row in valid_chunk[cols_to_insert].iterrows():
                        row_values = []
                        for val in row:
                            if pd.isna(val):
                                row_values.append(None)
                            else:
                                row_values.append(val)
                        values_list.append(tuple(row_values))

                    # Insert the chunk
                    cursor.executemany(sql, values_list)
                    conn.commit()
                    total_rows_inserted += len(values_list)
                    print(f"    Inserted {len(values_list)} rows (total: {total_rows_inserted})")

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

    print(f"\nTotal rows skipped due to missing data: {total_rows_skipped}")

    conn.close()
    print("\nStatcast import completed!")

if __name__ == "__main__":
    populate_statcast_table()