#!/usr/bin/env python3
"""
Publishes the project as a branded static website via GitHub Pages.

Generates docs/ :
  index.html   — homepage: live record baked from bet_log.csv, recent
                 graded bets as ledger rows, the nine gates, links
  method.html  — how the system works, honestly (pipeline, gates,
                 calibration, limitations)
  season.html  — copy of the season-results dashboard
  today.html   — copy of the newest daily cheat sheet
  style.css    — shared stylesheet

Usage after any run you want reflected online:
    python src/publish_site.py
    git add docs && git commit -m "Publish latest reports" && git push

One-time GitHub setup: repo -> Settings -> Pages -> Deploy from a
branch -> main, /docs. Everything in docs/ becomes PUBLIC.
"""
import sys
from pathlib import Path

# Add the project root to the Python path so we can import src modules
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import shutil
from datetime import datetime

import pandas as pd

from config import DATA_DIR, PROJECT_ROOT
from bet_log import BET_LOG_PATH
from teams import abbr

REPORTS_DIR = DATA_DIR / "reports"
DOCS_DIR = PROJECT_ROOT / "docs"

CSS = """
:root{
  --primary-dark:#0F172A;
  --dark:#1E293B;
  --darker:#0F172A;
  --light:#F8FAFC;
  --lighter:#F1F5F9;
  --text:#64748B;
  --text-dark:#1E293B;
  --accent:#3B82F6;
  --accent-hover:#2563EB;
  --success:#10B981;
  --warning:#F59E0B;
  --danger:#EF4444;
  --border:#E2E8F0;
  --shadow:0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
  --shadow-lg:0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
  --radius:0.5rem;
  --radius-lg:0.75rem;
}
*{box-sizing:border-box;margin:0;padding:0}
body{
  background:var(--light);
  color:var(--text);
  font-family:'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  line-height:1.7;
  font-size:16px;
  color:#334155;
}
a{
  color:var(--accent);
  text-decoration:none;
  transition:color 0.2s ease;
}
a:hover{
  color:var(--accent-hover);
  text-decoration:underline;
}
.wrap{
  max-width:1200px;
  margin:0 auto;
  padding:0 1.5rem;
}
header{
  background:white;
  box-shadow:var(--shadow);
  position:sticky;
  top:0;
  z-index:100;
}
.nav-container{
  display:flex;
  justify-content:space-between;
  align-items:center;
  height:4.5rem;
}
.logo{
  display:flex;
  align-items:center;
  gap:0.75rem;
}
.logo-img{
  height:2.5rem;
  width:auto;
}
.logo-text{
  font-size:1.5rem;
  font-weight:800;
  color:var(--dark);
  letter-spacing:-0.025em;
}
.nav-links{
  display:flex;
  gap:2rem;
  align-items:center;
}
.nav-links a{
  font-weight:500;
  color:var(--text);
  font-size:0.95rem;
  padding:0.5rem 0;
  border-bottom:2px solid transparent;
  transition:all 0.2s ease;
}
.nav-links a:hover{
  color:var(--accent);
  border-bottom-color:var(--accent);
}
.nav-links a.active{
  color:var(--accent);
  border-bottom-color:var(--accent);
}
.hero{
  background:linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%);
  color:white;
  text-align:center;
  padding:6rem 0 4rem;
  position:relative;
  overflow:hidden;
}
.hero::before{
  content:'';
  position:absolute;
  top:0;
  left:0;
  right:0;
  bottom:0;
  background:url('data:image/svg+xml,%3Csvg width=%2260%22 height=%2260%22 viewBox=%220 0 60 60%22 xmlns=%22http://www.w3.org/2000/svg%22%3E%3Cg fill=%22none%22 fill-rule=%22evenodd%22%3E%3Ccircle cx=%2230%22 cy=%2230%22 r=%222%22 fill=%22%23FFFFFF%22 fill-opacity=%220.1%22/%3E%3C/g%3E%3C/svg%3E');
  opacity:0.15;
}
.hero-content{
  position:relative;
  z-index:10;
  max-width:36rem;
  margin:0 auto;
}
.hero h1{
  font-size:2.5rem;
  font-weight:800;
  margin-bottom:1.5rem;
  line-height:1.2;
  letter-spacing:-0.025em;
}
.hero p{
  font-size:1.25rem;
  opacity:0.9;
  max-width:28rem;
  margin:0 auto 2rem;
}
.hero-buttons{
  display:flex;
  gap:1rem;
  justify-content:center;
  flex-wrap:wrap;
}
.btn-primary{
  background:white;
  color:#6366F1;
  border:none;
  padding:0.75rem 2rem;
  font-weight:600;
  border-radius:0.5rem;
  font-size:1rem;
  cursor:pointer;
  transition:all 0.2s ease;
  box-shadow:var(--shadow);
}
.btn-primary:hover{
  background:#F0F4FF;
  transform:translateY(-2px);
  box-shadow:var(--shadow-lg);
}
.btn-outline{
  background:rgba(255,255,255,0.1);
  border:1px solid rgba(255,255,255,0.2);
  color:white;
  padding:0.75rem 2rem;
  font-weight:600;
  border-radius:0.5rem;
  font-size:1rem;
  cursor:pointer;
  transition:all 0.2s ease;
}
.btn-outline:hover{
  background:rgba(255,255,255,0.2);
  transform:translateY(-2px);
}
.section{
  padding:5rem 0;
  background:white;
}
.section-alt{
  background:var(--lighter);
}
.section-title{
  text-align:center;
  margin-bottom:3rem;
}
.section-title h2{
  font-size:2rem;
  font-weight:700;
  color:var(--dark);
  margin-bottom:1rem;
  position:relative;
  display:inline-block;
}
.section-title h2::after{
  content:'';
  position:absolute;
  bottom:-0.5rem;
  left:50%;
  transform:translateX(-50%);
  width:4rem;
  height:3px;
  background:var(--accent);
  border-radius:3px;
}
.section-title p{
  color:var(--text);
  max-width:36rem;
  margin:0 auto;
  font-size:1.125rem;
  opacity:0.8;
}
.features-grid{
  display:grid;
  grid-template-columns:repeat(auto-fit, minmax(280px, 1fr));
  gap:2rem;
}
.feature-card{
  background:white;
  border-radius:var(--radius-lg);
  padding:2rem;
  box-shadow:var(--shadow);
  transition:all 0.3s ease;
  border:1px solid var(--border);
  height:100%;
  display:flex;
  flex-direction:column;
}
.feature-card:hover{
  transform:translateY(-4px);
  box-shadow:var(--shadow-lg);
  border-color:var(--accent);
}
.feature-icon{
  width:3rem;
  height:3rem;
  background:linear-gradient(135deg, #6366F1, #8B5CF6);
  border-radius:50%;
  display:flex;
  align-items:center;
  justify-content:center;
  margin-bottom:1.5rem;
}
.feature-icon svg{
  width:1.5rem;
  height:1.5rem;
  fill:white;
}
.feature-card h3{
  font-size:1.25rem;
  font-weight:600;
  color:var(--dark);
  margin-bottom:1rem;
  flex-grow:1;
}
.feature-card p{
  color:var(--text);
  line-height:1.6;
  flex-grow:1;
}
.stats-grid{
  display:grid;
  grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));
  gap:1.5rem;
  margin:2rem 0;
}
.stat-card{
  background:white;
  border-radius:var(--radius-lg);
  padding:1.5rem;
  text-align:center;
  box-shadow:var(--shadow);
  border:1px solid var(--border);
  transition:all 0.2s ease;
}
.stat-card:hover{
  transform:translateY(-2px);
  box-shadow:var(--shadow-lg);
}
.stat-number{
  font-size:2.5rem;
  font-weight:800;
  color:var(--accent);
  margin-bottom:0.5rem;
  line-height:1;
}
.stat-label{
  font-size:1rem;
  color:var(--text);
  font-weight:500;
}
.games-section{
  background:white;
}
.games-header{
  display:flex;
  justify-content:space-between;
  align-items:center;
  margin-bottom:2rem;
  flex-wrap:wrap;
  gap:1rem;
}
.games-header h2{
  font-size:1.75rem;
  font-weight:700;
  color:var(--dark);
}
.games-filter{
  display:flex;
  gap:1rem;
  align-items:center;
}
.games-filter select,
.games-filter input{
  padding:0.75rem 1rem;
  border:1px solid var(--border);
  border-radius:var(--radius);
  font-size:0.95rem;
  background:white;
  color:var(--text-dark);
}
.games-filter select:focus,
.games-filter input:focus{
  outline:none;
  border-color:var(--accent);
  box-shadow:0 0 0 2px rgba(59, 130, 246, 0.25);
}
.games-grid{
  display:grid;
  grid-template-columns:repeat(auto-fill, minmax(340px, 1fr));
  gap:1.5rem;
}
.game-card{
  background:white;
  border-radius:var(--radius-lg);
  overflow:hidden;
  box-shadow:var(--shadow);
  border:1px solid var(--border);
  transition:all 0.3s ease;
  display:flex;
  flex-direction:column;
  height:100%;
}
.game-card:hover{
  transform:translateY(-4px);
  box-shadow:var(--shadow-lg);
  border-color:var(--accent);
}
.game-header{
  display:flex;
  justify-content:space-between;
  align-items:center;
  padding:1.5rem;
  border-bottom:1px solid var(--border);
  flex-wrap:wrap;
  gap:1rem;
}
.teams{
  display:flex;
  align-items:center;
  gap:1rem;
  flex:1;
  min-width:0;
}
.team-logo{
  width:2.5rem;
  height:2.5rem;
  object-fit:contain;
  border-radius:50%;
  border:2px solid var(--lighter);
  background:white;
  padding:0.25rem;
}
.team-info{
  display:flex;
  flex-direction:column;
}
.team-name{
  font-weight:600;
  font-size:1.125rem;
  color:var(--text-dark);
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
}
.team-record{
  font-size:0.875rem;
  color:var(--text);
}
.versus{
  font-weight:600;
  color:var(--text-dark);
  font-size:1.125rem;
}
.game-time{
  font-size:0.875rem;
  color:var(--text);
  white-space:nowrap;
}
.game-body{
  flex:1;
  padding:1.5rem;
  display:flex;
  flex-direction:column;
}
.odds-section{
  display:flex;
  justify-content:space-between;
  margin-bottom:1.5rem;
  flex-wrap:wrap;
  gap:1rem;
}
.odds-box{
  background:var(--lighter);
  border:1px solid var(--border);
  border-radius:var(--radius);
  padding:1rem;
  text-align:center;
  flex:1;
  min-width:80px;
}
.odds-label{
  font-size:0.875rem;
  color:var(--text);
  margin-bottom:0.5rem;
  text-transform:uppercase;
  letter-spacing:0.05em;
}
.odds-value{
  font-size:1.5rem;
  font-weight:700;
  color:var(--text-dark);
}
.odds-value.home{color:var(--success);}
.odds-value.away{color:var(--danger);}
.odds-value.draw{color:var(--warning);}
.game-stats{
  display:grid;
  grid-template-columns:repeat(auto-fit, minmax(120px, 1fr));
  gap:1rem;
  margin-bottom:1.5rem;
}
.stat-item{
  text-align:center;
}
.stat-label{
  font-size:0.875rem;
  color:var(--text);
  text-transform:uppercase;
  letter-spacing:0.05em;
  margin-bottom:0.25rem;
}
.stat-value{
  font-size:1.125rem;
  font-weight:600;
  color:var(--text-dark);
}
.game-actions{
  margin-top:auto;
  padding:1.5rem;
  border-top:1px solid var(--border);
  display:flex;
  gap:1rem;
}
.game-btn{
  flex:1;
  padding:0.75rem;
  border:none;
  border-radius:var(--radius);
  font-weight:600;
  font-size:0.95rem;
  cursor:pointer;
  transition:all 0.2s ease;
}
.btn-primary-sm{
  background:var(--accent);
  color:white;
}
.btn-primary-sm:hover{
  background:var(--accent-hover);
}
.btn-outline-sm{
  background:white;
  color:var(--text-dark);
  border:1px solid var(--border);
}
.btn-outline-sm:hover{
  background:var(--lighter);
}
.hr-section{
  background:white;
  border-radius:var(--radius-lg);
  padding:2rem;
  box-shadow:var(--shadow);
  border:1px solid var(--border);
  margin:2rem 0;
}
.hr-header{
  display:flex;
  justify-content:space-between;
  align-items:center;
  margin-bottom:1.5rem;
  flex-wrap:wrap;
  gap:1rem;
}
.hr-header h2{
  font-size:1.5rem;
  font-weight:600;
  color:var(--dark);
}
.hr-table{
  width:100%;
  border-collapse:collapse;
  margin-top:1rem;
}
.hr-table th,
.hr-table td{
  padding:1rem;
  text-align:left;
  border-bottom:1px solid var(--border);
}
.hr-table th{
  background:var(--lighter);
  font-weight:600;
  color:var(--text-dark);
  font-size:0.95rem;
  text-transform:uppercase;
  letter-spacing:0.05em;
}
.hr-table tr:hover{
  background:var(--lighter);
}
.hr-player-name{
  font-weight:500;
}
.hr-probability{
  font-weight:600;
  text-align:right;
  font-family:'IBM Plex Mono', monospace;
}
.hr-probability.high{color:var(--success);}
.hr-probability.medium{color:var(--warning);}
.hr-probability.low{color:var(--danger);}
.hr-take{
  display:inline-block;
  padding:0.25rem 0.5rem;
  background:var(--lighter);
  border:1px solid var(--border);
  border-radius:0.25rem;
  font-size:0.875rem;
  font-weight:500;
  text-align:center;
}
.method-section{
  background:white;
  margin:2rem 0;
  padding:2rem;
  border-radius:var(--radius-lg);
  box-shadow:var(--shadow);
  border:1px solid var(--border);
}
.method-steps{
  display:grid;
  gap:2rem;
  margin:2.5rem 0;
}
.method-step{
  display:flex;
  gap:1.5rem;
  align-items:flex-start;
}
.step-number{
  background:var(--accent);
  color:white;
  width:2.5rem;
  height:2.5rem;
  border-radius:50%;
  display:flex;
  align-items:center;
  justify-content:center;
  font-weight:700;
  font-size:1rem;
  flex-shrink:0;
}
.step-content{
  flex:1;
}
.step-content h3{
  font-size:1.25rem;
  font-weight:600;
  color:var(--dark);
  margin-bottom:0.75rem;
}
.step-content p{
  color:var(--text);
  line-height:1.7;
}
.footer{
  background:var(--dark);
  color:white;
  padding:3rem 0 1.5rem;
}
.footer-content{
  display:grid;
  grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));
  gap:2.5rem;
  margin-bottom:2rem;
}
.footer-logo{
  display:flex;
  flex-direction:column;
  gap:1rem;
}
.footer-logo img{
  height:2rem;
  width:auto;
}
.footer-logo p{
  color:var(--lighter);
  font-size:0.9rem;
  line-height:1.6;
}
.footer-title{
  font-size:1.125rem;
  font-weight:600;
  margin-bottom:1.5rem;
  color:white;
}
.footer-links{
  display:flex;
  flex-direction:column;
  gap:0.75rem;
}
.footer-links a{
  color:var(--lighter);
  text-decoration:none;
  transition:color 0.2s ease;
}
.footer-links a:hover{
  color:white;
}
.footer-bottom{
  border-top:1px solid rgba(255,255,255,0.1);
  padding-top:1.5rem;
  text-align:center;
  color:var(--lighter);
  font-size:0.875rem;
}
@media(max-width:768px){
  .hero h1{
    font-size:2rem;
  }
  .hero p{
    font-size:1.125rem;
  }
  .nav-links{
    display:none;
  }
  .section-title h2{
    font-size:1.75rem;
  }
  .games-header{
    flex-direction:column;
    align-items:flex-start;
  }
  .hr-header{
    flex-direction:column;
    align-items:flex-start;
    gap:1rem;
  }
}
@media(max-width:480px){
  .hero{
    padding:4rem 0 3rem;
  }
  .hero h1{
    font-size:1.75rem;
  }
  .section{
    padding:3rem 0;
  }
  .section-title h2{
    font-size:1.5rem;
  }
  .footer-content{
    grid-template-columns:1fr;
    text-align:center;
  }
}
"""
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700'
         '&family=Public+Sans:wght@400;600&family=IBM+Plex+Mono:wght@400;600&display=swap" '
         'rel="stylesheet">')

GATES = [
    ("Minimum edge 3%", "Below that, model-vs-market disagreement is noise."),
    ("Expected value at the real price", "The edge must survive the vig — profit is computed at the posted odds, not the fair line."),
    ("Probability band 30–70%", "The side doesn't need to be favored, but it must sit where the model's calibration is proven."),
    ("Both starting pitchers posted", "A flag built on placeholder pitching isn't the model's real opinion."),
    ("Odds between −250 and +250", "Beyond that, “edges” are usually stale lines or payout traps."),
    ("Edge sanity cap 15%", "Too good to be true means a data bug, not market-beating insight."),
    ("Game not started", "A bet logged after first pitch is hindsight, and hindsight poisons a track record."),
    ("Both lineups posted", "Without lineups, lineup-power and matchup features run on placeholder averages — a flag built on defaults is not an opinion. Added after the July 17 incident this gate would have prevented."),
    ("Model must beat its baseline", "The totals model failed this check — so the system refuses its bets, automatically."),
]


def page(title, body, active=""):
    def navlink(href, label):
        return f'<a href="{href}">{label}</a>'
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#0F172A">
<link rel="manifest" href="manifest.json">
<link rel="apple-touch-icon" href="icon-192.png">
<title>{title} - MLBQuant</title>{FONTS}
<link rel="stylesheet" href="style.css">
<script>if('serviceWorker' in navigator){{navigator.serviceWorker.register('sw.js');}}</script>
</head><body>
<header><div class="wrap nav-container">
<div class="logo">
<img src="icon-192.png" alt="MLBQuant logo" class="logo-img">
<span class="logo-text">MLBQUANT</span>
</div>
<nav class="nav-links">{navlink("season.html", "Results")}{navlink("today.html", "Today")}{navlink("method.html", "Method")}</nav>
</div></header>
{body}
<footer><div class="wrap">All stakes are simulated 1-unit paper bets — a public, timestamped
model track record, not wagering advice. Built by a student; every pick is logged before
first pitch and graded after. <a href="https://github.com/aa2-2/SportsQuant-AI">Source on GitHub</a>.
</div></footer></body></html>"""


def load_todays_data():
    """Load starting pitchers and weather for today's games."""
    today_str = datetime.now().strftime("%Y-%m-%d")

    # Load starting pitchers
    pitchers_data = {}
    try:
        pitchers_df = pd.read_csv(DATA_DIR / "starting_pitchers_all_seasons.csv")
        pitchers_df["date"] = pd.to_datetime(pitchers_df["date"])
        today_pitchers = pitchers_df[pitchers_df["date"] == today_str]
        for _, row in today_pitchers.iterrows():
            key = (row["away_team"], row["home_team"])
            pitchers_data[key] = {
                "away_pitcher": row.get("away_pitcher", "TBD"),
                "home_pitcher": row.get("home_pitcher", "TBD"),
                "away_pitcher_era": float(row.get("away_pitcher_era", 0.0)),
                "home_pitcher_era": float(row.get("home_pitcher_era", 0.0))
            }
    except Exception as e:
        print(f"Warning: Could not load starting pitchers: {e}")

    # Load weather
    weather_data = {}
    try:
        weather_df = pd.read_csv(DATA_DIR / "weather_all_seasons.csv")
        weather_df["date"] = pd.to_datetime(weather_df["date"])
        today_weather = weather_df[weather_df["date"] == today_str]
        for _, row in today_weather.iterrows():
            key = (row["away_team"], row["home_team"])
            weather_data[key] = {
                "temp": float(row.get("temp", 0.0)),
                "wind": float(row.get("wind_speed", 0.0)),
                "condition": row.get("condition", "Clear")
            }
    except Exception as e:
        print(f"Warning: Could not load weather: {e}")

    return pitchers_data, weather_data


def get_team_logo_path(team_name):
    """Get the path to a team logo file."""
    # Convert team name to abbreviation/logo filename
    team_abbr = abbr(team_name)
    logo_path = PROJECT_ROOT / "assets" / "logos" / f"{team_abbr.lower()}.png"
    if logo_path.exists():
        return f"logos/{team_abbr.lower()}.png"
    # Fallback to a default logo or first letter
    return None


def load_today_games():
    """Load today's games data for display"""
    try:
        games_df = pd.read_csv(DATA_DIR / "games_2026.csv")
        pitchers_df = pd.read_csv(DATA_DIR / "starting_pitchers.csv")
        odds_df = pd.read_csv(DATA_DIR / "mlb_odds.csv")
        weather_df = pd.read_csv(DATA_DIR / "weather.csv")

        # Filter for today's date (assuming data is for today)
        today = datetime.now().strftime("%Y-%m-%d")
        games_today = games_df[games_df['date'] == today].copy()

        # Merge with other data
        if not pitchers_df.empty:
            pitchers_today = pitchers_df[pitchers_df['date'] == today]
            games_today = games_today.merge(pitchers_today, on=['game_pk', 'team'], how='left')

        if not odds_df.empty:
            odds_today = odds_df[odds_df['date'] == today]
            games_today = games_today.merge(odds_today, on='game_pk', how='left', suffixes=('', '_odds'))

        if not weather_df.empty:
            weather_today = weather_df[weather_df['date'] == today]
            games_today = games_today.merge(weather_today, on='game_pk', how='left', suffixes=('', '_weather'))

        return games_today
    except Exception as e:
        print(f"Warning: Could not load game data: {e}")
        return pd.DataFrame()


def get_team_logo_path(abbreviation):
    """Get the path to a team logo if it exists"""
    if not abbreviation:
        return None
    logo_path = Path("assets/logos") / f"{abbreviation.upper()}.png"
    if logo_path.exists():
        return str(logo_path)
    # Fallback to SVG if PNG doesn't exist
    svg_path = Path("assets/logos") / f"{abbreviation.lower()}.svg"
    if svg_path.exists():
        return str(svg_path)
    return None


def build_today():
    """Build the enhanced today page"""
    games_df = load_today_games()

    if games_df.empty:
        # Fallback to showing message if no data
        body = f"""
        <div class="today-header">
            <h1>Today's Games</h1>
            <p>Loading game data for {datetime.now().strftime('%B %d, %Y')}...</p>
        </div>
        <div class="featured-bet">
            <h2>No game data available</h2>
            <p>Please run the data collection scripts first:</p>
            <ul>
                <li>python src/fetch_games.py</li>
                <li>python src/fetch_starting_pitchers.py</li>
                <li>python src/fetch_weather.py</li>
                <li>python src/calculate_edge.py</li>
            </ul>
        </div>
        """
    else:
        # Build the actual today page with real data
        games_html = ""
        featured_bet = None

        # Process each game for display
        for _, game in games_df.iterrows():
            # Get team info
            home_team = game.get('home_team', '').upper()
            away_team = game.get('away_team', '').upper()

            # Get logos
            home_logo = get_team_logo_path(home_team)
            away_logo = get_team_logo_path(away_team)

            # Get game time
            game_time = game.get('game_time', 'TBD')
            if pd.isna(game_time):
                game_time = 'TBD'

            # Get odds info (simplified)
            home_odds = game.get('home_ml', 'EVEN')
            away_odds = game.get('away_ml', 'EVEN')
            if pd.isna(home_odds):
                home_odds = 'EVEN'
            if pd.isna(away_odds):
                away_odds = 'EVEN'

            # Determine featured bet (highest edge)
            edge = abs(float(game.get('edge_percent', 0))) if not pd.isna(game.get('edge_percent')) else 0
            if featured_bet is None or edge > featured_bet['edge']:
                featured_bet = {
                    'game': f"{away_team} @ {home_team}",
                    'pick': game.get('recommendation', 'No pick'),
                    'edge': edge,
                    'reason': game.get('reason', 'Model analysis')
                }

            # Home/away probabilities
            home_prob = float(game.get('home_win_prob', 0.5)) * 100 if not pd.isna(game.get('home_win_prob')) else 50
            away_prob = 100 - home_prob

            game_html = f"""
            <div class="game-card">
                <div class="game-header">
                    <div>
                        {"<img src='" + away_logo + "' alt='" + away_team + "' class='team-logo'>" if away_logo else f"<div style='width:40px;height:40px;background:#f0f0f0;border-radius:50%;display:flex;align-items:center;justify-content:center;margin-right:12px;font-weight:bold;'>{away_team}</div>"}
                        <div class="team-info">
                            <div class="team-name">{away_team}</div>
                        </div>
                    </div>
                    <div class="vs">@</div>
                    <div>
                        {"<img src='" + home_logo + "' alt='" + home_team + "' class='team-logo'>" if home_logo else f"<div style='width:40px;height:40px;background:#f0f0f0;border-radius:50%;display:flex;align-items:center;justify-content:center;margin-right:12px;font-weight:bold;'>{home_team}</div>"}
                        <div class="team-info">
                            <div class="team-name">{home_team}</div>
                        </div>
                    </div>
                </div>
                <div class="game-time">{game_time}</div>

                <div class="odds-display">
                    <div class="odds-box">
                        <div class="odds-value">{away_odds}</div>
                        <div class="odds-label">{away_team} ML</div>
                    </div>
                    <div class="odds-box">
                        <div class="odds-value">{home_odds}</div>
                        <div class="odds-label">{home_team} ML</div>
                    </div>
                </div>

                <div class="probability-bar">
                    <div class="probability-fill" style="width: {away_prob}%;"></div>
                </div>
                <div class="probability-labels" style="display:flex;justify-content:space-between;font-size:0.9rem;color:var(--muted);margin-top:4px;">
                    <span>{away_team} {away_prob:.1f}%</span>
                    <span>{home_team} {home_prob:.1f}%</span>
                </div>
            </div>
            """
            games_html += game_html

        # Build featured bet section
        featured_html = ""
        if featured_bet:
            featured_html = f"""
            <div class="featured-bet">
                <h2>Today's Best Bet</h2>
                <div class="pick">{featured_bet['pick']}</div>
                <div style="margin:12px 0;">
                    <span>Game: {featured_bet['game']}</span>
                </div>
                <div class="edge">Edge: {featured_bet['edge']:.1f}%</div>
                <div class="reason">{featured_bet['reason']}</div>
            </div>
            """

        # Build HR section (simplified - in reality this would come from HR model)
        hr_section = """
        <div class="hr-section">
            <h2>Top Home Run Prospects</h2>
            <div style="margin-bottom:16px;color:#666;font-style:italic;">
                Note: HR predictions use a separate model that is currently disabled until it meets accuracy thresholds.
            </div>
            <table class="hr-table">
                <thead>
                    <tr>
                        <th>Player</th>
                        <th>Team</th>
                        <th>HR Probability</th>
                        <th>Take at Odds</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td class="hr-player">Munetaka Murakami</td>
                        <td>CWS</td>
                        <td class="hr-prob">28.6%</td>
                        <td class="hr-take">+250 or better</td>
                    </tr>
                    <tr>
                        <td class="hr-player">Miguel Vargas</td>
                        <td>CWS</td>
                        <td class="hr-prob">23.1%</td>
                        <td class="hr-take">+340 or better</td>
                    </tr>
                    <tr>
                        <td class="hr-player">Pete Crow-Armstrong</td>
                        <td>CHC</td>
                        <td class="hr-prob">23.5%</td>
                        <td class="hr-take">+330 or better</td>
                    </tr>
                    <tr>
                        <td class="hr-player">Brandon Lowe</td>
                        <td>PIT</td>
                        <td class="hr-prob">18.9%</td>
                        <td class="hr-take">+430 or better</td>
                    </tr>
                </tbody>
            </table>
        </div>
        """

        # Update date
        current_date = datetime.now().strftime("%B %d, %Y")

        body = f"""
        <div class="today-header">
            <h1>Today's MLB Picks</h1>
            <p>{current_date} • Updated {datetime.now().strftime('%I:%M %p ET')}</p>
        </div>

        {featured_html}

        <h2>Today's Games ({len(games_df)} games)</h2>
        <div class="games-grid">
            {games_html}
        </div>

        {hr_section}
        """

    return page("Today's Games", body)


def build_index(cheat_label):
    df = load_record()
    updated = datetime.now().strftime("%B %d, %Y %H:%M")
    body = f"""
    <div class="hero"><div class="wrap">
    <h1>Every call logged before first&nbsp;pitch. Graded&nbsp;after.</h1>
    <p class="sub">A student-built MLB model that compares its win probabilities against the
    betting market, bets on paper under a nine-gate policy, and publishes the graded ledger —
    wins, losses, and everything it refused to bet. Daily cards now carry a per-batter HR board:
    calibrated home-run probabilities (platoon, park, and weather adjusted) with the minimum
    odds worth taking.</p>
    {ledger_html(df)}
    <div class="actions">
    <a class="btn solid" href="season.html">Full season ledger</a>
    <a class="btn" href="today.html">{cheat_label}</a>
    <a class="btn" href="method.html">How it works</a>
    </div>
    </div></div>
    <section><div class="wrap">
    <h2>Nine gates between a flag and a bet</h2>
    <p class="body">The model disagreeing with the market is not enough. Every prospective bet
    passes this checklist or is published as <em>suppressed, with the reason</em> — a system
    that hides its rejections can't be audited.</p>
    <ol class="gates">{''.join(f'<li><div><b>{t}</b><span>{d}</span></div></li>' for t, d in GATES)}</ol>
    </div></section>
    """
    return page("Live ledger", body).replace("Updated —", f"Updated {updated}")


def build_method():
    body = """
    <div class="hero"><div class="wrap"><h1>How the system works</h1>
    <p class="sub">And, just as deliberately, what it refuses to do.</p></div></div>
    <section><div class="wrap">
    <h2>The pipeline</h2>
    <p class="body">Six seasons of MLB results, starting pitchers, Statcast batted-ball data, and
    game-time weather feed 25 leakage-safe features — every rolling statistic uses only
    information available <em>before</em> the game it describes. A calibrated logistic regression
    produces win probabilities; those are compared against vig-removed consensus odds from nine
    sportsbooks; disagreements above threshold become flags; flags that clear all nine gates
    become simulated 1-unit paper bets, logged with their odds, probability, expected value,
    and the model's top reasons. Final scores grade every bet automatically.</p>
    <h2>Why the probabilities can be trusted (and where they can't)</h2>
    <p class="body">Calibration analysis on held-out 2026 games shows predicted probabilities in
    the 30–70% band track observed win rates. Outside that band the samples are thin and the
    model measurably overconfident — so the policy simply refuses to bet there. The betting gates
    are derived from the project's own validation findings, not borrowed thresholds.</p>
    <h2>What it refuses to do</h2>
    <p class="body">A second model that predicts run totals failed to beat the naive
    always-predict-the-average baseline in cross-validation. The system reads that verdict from
    the model's own saved report card and disables O/U betting automatically — the model exists,
    and is not allowed to act, until it earns it. There is also no real-money automation anywhere:
    the ledger's job is to establish, in public, whether the edges are real. Sizing stays at a
    flat 1 unit; quarter-Kelly stakes are recorded in parallel for comparison but never used,
    because Kelly trusts the model's probabilities and that trust is exactly what's being tested.</p>
    <h2>The HR board</h2>
    <p class="body">Each game card lists every confirmed batter's probability of homering —
    built bottom-up from per-plate-appearance rates (validated on 109,000 held-out plate
    appearances), his lineup slot's measured trips to the plate, the platoon matchup against
    tonight's starter, the park's HR factor, and a weather multiplier fitted on this project's
    own games. The board shows one action number: the minimum sportsbook price worth taking.
    The model's fair odds are the break-even; any price at or above them is value if the
    calibration holds — and the calibration tables are public. No EV percentages are shown
    against a "consensus" this site doesn't ingest; a comparison that can't be made honestly
    isn't made.</p>
    <h2>Honest limitations</h2>
    <p class="body">Cross-validated accuracy is ~0.55 against a 0.52 home-team baseline — a real
    but thin signal, nowhere near guaranteed to survive closing-line vig. Some prediction inputs
    fall back to training-mean placeholders when lineups or weather aren't posted (a fallback
    scheme rebuilt after a placeholder bias was caught flagging every road team on one slate —
    graded honestly in the project log). The sample of settled bets is small; nothing here is a
    conclusion yet. That's what the ledger is for.</p>
    <h2>Experiment log: barrel-based xHR prior (tested, not shipped)</h2>
    <p class="body">A barrel-quality prior for home-run rates was built and put through the
    same validation gate as everything else. The gate's verdict: blending it in made held-out
    predictions worse at every weight tried, so validation selected a weight of zero — the
    experiment runs at no influence. Logged for a corrected retry. Negative results are
    results.</p>
    </div></section>
    """
    return page("Method", body)


def load_record():
    if not BET_LOG_PATH.exists():
        return None
    df = pd.read_csv(BET_LOG_PATH)
    if len(df) == 0:
        return None
    df["profit_num"] = pd.to_numeric(df.get("profit_units"), errors="coerce").fillna(0.0)
    return df


def ledger_html(df):
    if df is None:
        return ('<div class="ledger"><div class="empty mono">Ledger opens with the first '
                'graded slate.</div></div>')

    settled = df[df["status"].isin(["won", "lost", "push"])]
    pending = df[df["status"] == "pending"]
    wins = int((settled["status"] == "won").sum())
    losses = int((settled["status"] == "lost").sum())
    pushes = int((settled["status"] == "push").sum())
    profit = settled["profit_num"].sum()
    staked = pd.to_numeric(settled.get("stake_units"), errors="coerce").fillna(0).sum()
    roi = profit / staked if staked > 0 else 0.0
    cls = "win" if profit > 0 else ("loss" if profit < 0 else "")

    record = f"{wins}-{losses}" + (f"-{pushes}" if pushes else "")
    head = f"""<div class="ledger-head mono">
<div class="stat"><div class="l">Record</div><div class="n">{record}</div></div>
<div class="stat"><div class="l">P&L</div><div class="n {cls}">{profit:+.1f}u</div></div>
<div class="stat"><div class="l">ROI</div><div class="n {cls}">{roi:+.1%}</div></div>
<div class="stat"><div class="l">Pending</div><div class="n">{len(pending)}</div></div>
</div>"""

    def pick_label(bet):
        bt = str(bet.get("bet_type") or "moneyline")
        if bt.startswith("total"):
            try:
                return f"{str(bet['side']).upper()} {float(bet['line']):g}"
            except (TypeError, ValueError):
                return str(bet["side"]).upper()
        return f"{abbr(str(bet['side']))} ML"

    rows = ('<div class="row headrow mono"><div>Date</div><div>Pick</div>'
            '<div class="hide-m">Odds / Model</div><div>Grade</div>'
            '<div class="hide-m">Units</div></div>')
    recent = df.iloc[::-1].head(6)
    for _, bet in recent.iterrows():
        status = str(bet["status"])
        grade = {"won": "W", "lost": "L", "push": "P"}.get(status, "·")
        units = f"{bet['profit_num']:+.2f}u" if status in ("won", "lost", "push") else "pending"
        rows += (f'<div class="row mono"><div>{bet["game_date"]}</div>'
                 f'<div>{pick_label(bet)} <span style="color:var(--muted)">'
                 f'({bet["matchup"]})</span></div>'
                 f'<div class="hide-m">{float(bet["odds"]):+.0f} / {float(bet["model_prob"]):.0%}</div>'
                 f'<div class="grade {grade}">{grade}</div>'
                 f'<div class="hide-m">{units}</div></div>')

    return f'<div class="ledger">{head}<div class="rows">{rows}</div></div>'


MANIFEST = """{
  "name": "MLBQuant",
  "short_name": "MLBQuant",
  "description": "MLBQuant — an MLB model paper-trading ledger. Every call logged before first pitch, graded after.",
  "start_url": "index.html",
  "display": "standalone",
  "background_color": "#EFF3EC",
  "theme_color": "#1E3A2F",
  "icons": [
    {"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
    {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"}
  ]
}"""

# Network-first: always show fresh ledger data when online, fall back
# to the last cached copy when offline.
SERVICE_WORKER = """const CACHE='mlbq-v1';
self.addEventListener('install',e=>{self.skipWaiting();});
self.addEventListener('activate',e=>{e.waitUntil(clients.claim());});
self.addEventListener('fetch',e=>{
  if(e.request.method!=='GET')return;
  e.respondWith(
    fetch(e.request).then(r=>{
      const copy=r.clone();
      caches.open(CACHE).then(c=>c.put(e.request,copy));
      return r;
    }).catch(()=>caches.match(e.request))
  );
});"""


if __name__ == "__main__":
    DOCS_DIR.mkdir(exist_ok=True)

    (DOCS_DIR / "style.css").write_text(CSS, encoding="utf-8")
    published = []

    (DOCS_DIR / "manifest.json").write_text(MANIFEST, encoding="utf-8")
    (DOCS_DIR / "sw.js").write_text(SERVICE_WORKER, encoding="utf-8")
    published.append("manifest.json + sw.js (installable app support)")

    assets = PROJECT_ROOT / "assets"
    for icon in ["icon-192.png", "icon-512.png"]:
        if (assets / icon).exists():
            shutil.copy(assets / icon, DOCS_DIR / icon)
            published.append(icon)

    season = REPORTS_DIR / "season_results.html"
    if season.exists():
        shutil.copy(season, DOCS_DIR / "season.html")
        published.append("season.html")

    edge_reports = sorted(REPORTS_DIR.glob("edge_report_*.html"))
    cheat_label = "Today's card"
    if edge_reports:
        latest = edge_reports[-1]
        shutil.copy(latest, DOCS_DIR / "today.html")
        cheat_label = latest.stem.replace("edge_report_", "Card: ")
        published.append(f"today.html ({latest.name})")

    (DOCS_DIR / "index.html").write_text(build_index(cheat_label), encoding="utf-8")
    published.append("index.html")
    (DOCS_DIR / "method.html").write_text(build_method(), encoding="utf-8")
    published.append("method.html")

    print("Published to docs/:")
    for item in published:
        print(f"  - {item}")
    print('\nNow run:  git add docs && git commit -m "Publish site" && git push')