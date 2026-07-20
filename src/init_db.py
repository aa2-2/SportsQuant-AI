import sqlite3
import os
from pathlib import Path

DATABASE_PATH = "data/sportsquant_ai.db"

def create_database():
    """Initialize the baseball analytics database with championship-grade schema"""
    # Ensure data directory exists
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

    # For use with existing database, comment out the removal above
    # if os.path.exists(DATABASE_PATH):
    #     os.remove(DATABASE_PATH)
    #     print(f"Removed existing database: {DATABASE_PATH}")

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Enable foreign key constraints
    cursor.execute("PRAGMA foreign_keys = ON;")

    print("Building championship database schema...")

    # ===== GAMES TABLE =====
    cursor.execute("""
    CREATE TABLE games (
        game_pk INTEGER PRIMARY KEY,
        date DATE NOT NULL,
        home_team TEXT NOT NULL,
        away_team TEXT NOT NULL,
        home_score INTEGER,
        away_score INTEGER,
        venue_id INTEGER,
        temperature REAL,
        wind_speed REAL,
        wind_direction TEXT,
        status TEXT NOT NULL DEFAULT 'scheduled',
        first_pitch_utc TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT chk_status CHECK (status IN ('scheduled', 'in_progress', 'final', 'delayed'))
    );
    """)

    # ===== PITCHERS TABLE =====
    cursor.execute("""
    CREATE TABLE pitchers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_pk INTEGER NOT NULL,
        mlbam_id INTEGER NOT NULL,
        team TEXT NOT NULL,

        -- Arsenal usage percentages
        fastball_usage REAL DEFAULT 0,
        slider_usage REAL DEFAULT 0,
        curveball_usage REAL DEFAULT 0,
        changeup_usage REAL DEFAULT 0,
        splitter_usage REAL DEFAULT 0,
        knuckleball_usage REAL DEFAULT 0,

        -- Velocity vs handedness
        fb_velo_vs_lhb REAL,
        fb_velo_vs_rhb REAL,

        -- Whiff rates vs handedness
        slider_whiff_vs_lhb REAL,
        slider_whiff_vs_rhb REAL,
        curve_whiff_vs_lhb REAL,
        curve_whiff_vs_rhb REAL,

        -- Advanced pitching metrics
        barrel_allowed_pct REAL DEFAULT 0,
        hard_hit_allowed_pct REAL DEFAULT 0,
        fly_ball_rate REAL DEFAULT 0,
        ground_ball_rate REAL DEFAULT 0,
        line_drive_rate REAL DEFAULT 0,
        k_percent REAL DEFAULT 0,
        bb_percent REAL DEFAULT 0,
        hr_per_nine REAL DEFAULT 0,
        whip REAL DEFAULT 0,

        -- League percentile ranks (computed post-process)
        fb_velo_percentile INTEGER,
        spin_rate_percentile INTEGER,
        barb_percentile INTEGER,

        FOREIGN KEY (game_pk) REFERENCES games(game_pk) ON DELETE CASCADE
    );
    """)

    # ===== BATTERS TABLE =====
    cursor.execute("""
    CREATE TABLE batters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mlbam_id INTEGER NOT NULL UNIQUE,

        -- Core power metrics (season aggregates)
        barrel_pct_season REAL DEFAULT 0,
        barrel_pct_last_10 REAL DEFAULT 0,
        barrel_pct_last_5 REAL DEFAULT 0,
        barrel_pct_last_10d REAL DEFAULT 0,

        hh_pct_season REAL DEFAULT 0,      -- Hard hit %
        hh_pct_last_10 REAL DEFAULT 0,
        hh_pct_last_5 REAL DEFAULT 0,

        ev_avg_season REAL DEFAULT 0,      -- Avg exit velocity
        ev_avg_last_10 REAL DEFAULT 0,
        la_avg_season REAL DEFAULT 0,      -- Avg launch angle
        la_avg_last_10 REAL DEFAULT 0,

        pull_pct_season REAL DEFAULT 0,
        pull_pct_last_10 REAL DEFAULT 0,
        air_pull_pct_season REAL DEFAULT 0,
        air_pull_pct_last_10 REAL DEFAULT 0,

        xslg_season REAL DEFAULT 0,
        xslg_last_10 REAL DEFAULT 0,
        iso_season REAL DEFAULT 0,
        iso_last_10 REAL DEFAULT 0,

        hr_bbe_season REAL DEFAULT 0,      -- HR per batted ball event
        hr_bbe_last_10 REAL DEFAULT 0,

        -- Plate discipline
        walk_rate REAL DEFAULT 0,
        strikeout_rate REAL DEFAULT 0,
        chase_rate REAL DEFAULT 0,
        zone_contact REAL DEFAULT 0,

        -- Splits vs handedness
        vs_lhb_barrel_pct REAL DEFAULT 0,
        vs_rhb_barrel_pct REAL DEFAULT 0,
        vs_lhb_hh_pct REAL DEFAULT 0,
        vs_rhb_hh_pct REAL DEFAULT 0,
        vs_lhb_xslg REAL DEFAULT 0,
        vs_rhb_xslg REAL DEFAULT 0
    );
    """)

    # ===== STATCAST TABLE (PITCH-LEVEL GRANULARITY) =====
    cursor.execute("""
    CREATE TABLE statcast (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_pk INTEGER NOT NULL,

        -- At-bat context
        inning INTEGER NOT NULL,
        half_inning TEXT NOT NULL CHECK (half_inning IN ('TOP', 'BOT')),
        balls INTEGER NOT NULL,
        strikes INTEGER NOT NULL,
        outs_when_up INTEGER NOT NULL,
        batter_id INTEGER NOT NULL,
        pitcher_id INTEGER NOT NULL,

        -- PITCH DATA
        pitch_type TEXT NOT NULL,           -- FF, SL, CH, CU, FC, FS, etc.
        pitch_number INTEGER NOT NULL,
        release_speed REAL NOT NULL,        -- Velocity (mph)
        release_pos_x REAL,                 -- Release point x
        release_pos_y REAL,                 -- Release point y
        release_pos_z REAL,                 -- Release point z
        release_spin_rate REAL,             -- RPM
        release_spin_dir INTEGER,           -- Spin direction

        -- BATTED BALL EVENTS
        launch_speed REAL,                  -- Exit velocity (mph)
        launch_angle REAL,                  -- Launch angle (degrees)
        launch_direction REAL,              -- Spray angle (degrees, -45=left line, 0=2B, 45=right line)
        bb_type TEXT,                       -- fly_ball, ground_ball, line_drive, popup, sac_fly
        events TEXT,                        -- single, double, triple, home_run, strikeout, walk, etc.

        -- ELITE METRICS (your secret sauce)
        is_barrel INTEGER DEFAULT 0,        -- MLB Barrel: exit_velocity >= 98 AND launch_angle BETWEEN 26 AND 30
        solid_contact INTEGER DEFAULT 0,    -- Sweet spot: exit_velocity >= 95 AND launch_angle BETWEEN 8 AND 50
        burned_contact INTEGER DEFAULT 0,   -- Flare/burner: exit_velocity >= 95 AND launch_angle NOT BETWEEN 8 AND 50
        flare_burner INTEGER DEFAULT 0,     -- Flare/burner: exit_velocity BETWEEN 89 AND 91 AND launch_angle BETWEEN 24 AND 30

        -- Outcomes
        babip REAL,                         -- Batting average on balls in play
        slg REAL,                           -- Slugging on contact
        woba_value REAL,                    -- wOBA value of event
        woba_denom REAL,                    -- wOBA denominator

        -- Timing
        game_date DATE,
        inning_topbot TEXT,                 -- TOP/BOT for clarity

        FOREIGN KEY (game_pk) REFERENCES games(game_pk) ON DELETE CASCADE,
        FOREIGN KEY (batter_id) REFERENCES batters(id),
        FOREIGN KEY (pitcher_id) REFERENCES pitchers(id)
    );
    """)

    # ===== WEATHER TABLE (WITH FIELD-ORIENTED WIND) =====
    cursor.execute("""
    CREATE TABLE weather (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_pk INTEGER NOT NULL,

        -- Raw API data
        temperature REAL,                   -- In Fahrenheit
        feels_like REAL,
        temp_min REAL,
        temp_max REAL,
        pressure REAL,                      -- hPa
        humidity REAL,                      -- Percentage
        wind_speed REAL,                    -- mph
        wind_deg INTEGER,                   -- Meteorological direction (0=N, 90=E)
        wind_gust REAL,
        weather_main TEXT,                  -- Clear, Clouds, Rain, etc.
        weather_description TEXT,
        clouds INTEGER,                     -- Percentage

        -- YOUR SPEC: Wind relative to field orientation
        -- Requires park orientation data (we'll join with parks table)
        wind_in_cf REAL,                    -- Component FROM center field (negative = OUT to CF)
        wind_side_to_side REAL,             -- Component from 3B to 1B (negative = towards 3B)
        hr_weather_adjustment REAL,         -- Calculated HR impact multiplier

        -- Field conditions
        precipitation REAL DEFAULT 0,       -- Inches
        visibility REAL DEFAULT 10,         -- Miles

        game_date DATE,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (game_pk) REFERENCES games(game_pk) ON DELETE CASCADE
    );
    """)

    # ===== ODDS SNAPSHOTS TABLE (LINE MOVEMENT TRACKING) =====
    cursor.execute("""
    CREATE TABLE odds_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_pk INTEGER NOT NULL,
        sportsbook TEXT NOT NULL,           -- FanDuel, DraftKings, BetMGM, etc.

        -- Player props (we'll expand to other markets later)
        player_mlbam_id INTEGER NOT NULL,
        prop_type TEXT NOT NULL DEFAULT 'home_runs', -- home_runs, hits, strikeouts, etc.
        line_value REAL NOT NULL,           -- e.g., 1.5 for HR
        over_odds INTEGER NOT NULL,         -- American odds
        under_odds INTEGER NOT NULL,

        -- Derived fields for efficiency
        implied_prob_over REAL,             -- Calculated from over_odds
        implied_prob_under REAL,            -- Calculated from under_odds
        vig REAL,                           -- Vigorish on this market

        timestamp TIMESTAMP NOT NULL,       -- When this snapshot was taken
        retrieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (game_pk) REFERENCES games(game_pk) ON DELETE CASCADE,
        FOREIGN KEY (player_mlbam_id) REFERENCES batters(mlbam_id)
    );
    """)

    # ===== PARK FACTORS TABLE (FOR WEATHER CALCULATIONS) =====
    cursor.execute("""
    CREATE TABLE parks (
        park_id INTEGER PRIMARY KEY,
        park_name TEXT NOT NULL,
        team TEXT NOT NULL,
        -- Orientation: degrees from true north to center field line
        cf_orientation REAL NOT NULL,       -- 0 = CF points north, 90 = CF points east
        -- Park factors (multiplicative, 1.0 = league average)
        hr_factor REAL DEFAULT 1.0,
        hr_factor_lhh REAL DEFAULT 1.0,
        hr_factor_rhh REAL DEFAULT 1.0,
        singles_factor REAL DEFAULT 1.0,
        doubles_factor REAL DEFAULT 1.0,
        triples_factor REAL DEFAULT 1.0,
        sb_factor REAL DEFAULT 1.0,
        cs_factor REAL DEFAULT 1.0,
        -- Altitude for air density calculations
        elevation_feet INTEGER DEFAULT 0
    );
    """)

    # ===== CREATE INDICES FOR LIGHTNING FAST QUERIES =====
    print("Creating performance indexes...")

    # Statcast queries (by batter/pitcher/date)
    cursor.execute("CREATE INDEX idx_sc_batter_game ON statcast(batter_id, game_pk);")
    cursor.execute("CREATE INDEX idx_sc_pitcher_game ON statcast(pitcher_id, game_pk);")
    cursor.execute("CREATE INDEX idx_sc_game_date ON statcast(game_date);")
    cursor.execute("CREATE INDEX idx_sc_bbtype ON statcast(bb_type);")
    cursor.execute("CREATE INDEX idx_sc_events ON statcast(events);")
    cursor.execute("CREATE INDEX idx_sc_is_barrel ON statcast(is_barrel);")

    # Odds queries
    cursor.execute("CREATE INDEX idx_odds_game_time ON odds_snapshots(game_pk, timestamp);")
    cursor.execute("CREATE INDEX idx_odds_player_time ON odds_snapshots(player_mlbam_id, timestamp);")
    cursor.execute("CREATE INDEX idx_odds_sportsbook ON odds_snapshots(sportsbook);")

    # Weather queries
    cursor.execute("CREATE INDEX idx_weather_game ON weather(game_pk);")

    # Games queries
    cursor.execute("CREATE INDEX idx_games_date ON games(date);")
    cursor.execute("CREATE INDEX idx_games_status ON games(status);")
    cursor.execute("CREATE INDEX idx_games_teams ON games(home_team, away_team);")

    # Commit and verify
    conn.commit()

    # Quick verification
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"Created {len(tables)} tables: {[t[0] for t in tables]}")

    conn.close()
    print(f"[SUCCESS] Championship database initialized at {DATABASE_PATH}")
    return DATABASE_PATH

if __name__ == "__main__":
    create_database()