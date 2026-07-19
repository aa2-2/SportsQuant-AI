"""
Publishes the project as a branded static website via GitHub Pages.

Generates docs/ :
  index.html   --- homepage: live record baked from bet_log.csv, recent
                 graded bets as ledger rows, the nine gates, links
  method.html  --- how the system works, honestly (pipeline, gates,
                 calibration, limitations)
  season.html  --- copy of the season-results dashboard
  today.html   --- copy of the newest daily cheat sheet
  style.css    --- shared stylesheet

Usage after any run you want reflected online:
    python src/publish_site.py
    git add docs && git commit -m "Publish latest reports" && git push

One-time GitHub setup: repo -> Settings -> Pages -> Deploy from a
branch -> main, /docs. Everything in docs/ becomes PUBLIC.
"""
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.config import DATA_DIR, PROJECT_ROOT
from src.bet_log import BET_LOG_PATH
from src.teams import abbr

REPORTS_DIR = DATA_DIR / "reports"
DOCS_DIR = PROJECT_ROOT / "docs"

CSS = """
:root{
  --paper:#EFF3EC;
  --ink:#1E3A2F;
  --text:#2B2B28;
  --rule:#C9D4C6;
  --win:#1E6B3C;
  --loss:#B3392E;
  --muted:#6E7A6E;
  --card:#F7FAF5;
  --primary:#2563EB;
  --primary-dark:#1D4ED8;
  --success:#10B981;
  --warning:#F59E0B;
  --danger:#EF4444;
}
*{box-sizing:border-box;margin:0}
body{
  background:var(--paper);
  color:var(--text);
  font-family:'Public Sans',system-ui,sans-serif;
  font-size:16px;
  line-height:1.6
}
.mono{font-family:'IBM Plex Mono',monospace;font-variant-numeric:tabular-nums}
a{color:var(--ink)}
.wrap{
  max-width:960px;
  margin:0 auto;
  padding:0 20px
}
header{border-bottom:2px solid var(--ink)}
.bar{
  display:flex;
  justify-content:space-between;
  align-items:center;
  padding:16px 0
}
.mark{
  font-family:'Barlow Condensed',sans-serif;
  font-weight:700;
  font-size:22px;
  letter-spacing:.06em;
  color:var(--ink);
  text-decoration:none
}
nav a{
  margin-left:22px;
  font-size:14px;
  text-decoration:none;
  color:var(--text)
}
nav a:hover{text-decoration:underline}
.hero{
  padding:56px 0 40px;
  background:
  repeating-linear-gradient(to bottom,transparent 0 27px,var(--rule) 27px 28px)
}
h1{
  font-family:'Barlow Condensed',sans-serif;
  font-weight:700;
  font-size:clamp(38px,6vw,58px);
  line-height:1.05;
  color:var(--ink);
  text-transform:uppercase;
  letter-spacing:.01em;
  max-width:640px
}
.sub{
  margin:14px 0 0;
  color:var(--muted);
  max-width:560px
}
.ledger{
  background:var(--card);
  border:2px solid var(--ink);
  margin:36px 0 0
}
.ledger-head{
  display:grid;
  grid-template-columns:repeat(4,1fr);
  border-bottom:2px solid var(--ink)
}
.stat{
  padding:16px 18px;
  border-right:1px solid var(--rule)
}
.stat:last-child{border-right:none}
.stat .l{
  font-size:11px;
  letter-spacing:.14em;
  text-transform:uppercase;
  color:var(--muted)
}
.stat .n{
  font-size:30px;
  font-weight:600
}
.n.win{color:var(--win)}
.n.loss{color:var(--loss)}
.rows{font-size:14px}
.row{
  display:grid;
  grid-template-columns:88px 1fr 130px 70px 90px;
  gap:10px;
  padding:9px 18px;
  border-top:1px solid var(--rule);
  align-items:baseline
}
.row.headrow{
  color:var(--muted);
  font-size:11px;
  letter-spacing:.12em;
  text-transform:uppercase;
  border-top:none
}
.grade{
  font-weight:600
}
.grade.W{color:var(--win)}
.grade.L{color:var(--loss)}
.grade.P{color:var(--muted)}
.empty{
  padding:22px 18px;
  color:var(--muted)
}
.actions{
  display:flex;
  gap:14px;
  margin:28px 0 0;
  flex-wrap:wrap
}
.btn{
  display:inline-block;
  border:2px solid var(--ink);
  padding:12px 22px;
  text-decoration:none;
  font-family:'Barlow Condensed',sans-serif;
  font-size:18px;
  letter-spacing:.05em;
  text-transform:uppercase;
  color:var(--ink);
  background:var(--card)
}
.btn.solid{
  background:var(--ink);
  color:var(--paper)
}
.btn:focus-visible{
  outline:3px solid var(--loss);
  outline-offset:2px
}
section{
  padding:48px 0;
  border-top:1px solid var(--rule)
}
h2{
  font-family:'Barlow Condensed',sans-serif;
  font-weight:600;
  font-size:28px;
  color:var(--ink);
  text-transform:uppercase;
  letter-spacing:.03em;
  margin-bottom:18px
}
.gates{
  list-style:none;
  counter-reset:g
}
.gates li{
  counter-increment:g;
  display:grid;
  grid-template-columns:52px 1fr;
  gap:14px;
  padding:12px 0;
  border-bottom:1px solid var(--rule)
}
.gates li::before{
  content:counter(g,decimal-leading-zero);
  font-family:'IBM Plex Mono',monospace;
  color:var(--loss);
  font-size:18px;
  padding-top:2px
}
.gates b{display:block;color:var(--ink)}
.gates span{color:var(--muted);font-size:14px}
.p.body{
  max-width:640px;
  margin-bottom:14px
}
footer{
  border-top:2px solid var(--ink);
  padding:26px 0;
  font-size:13px;
  color:var(--muted)
}
/* Game Cards for today.html */
.game-grid{
  display:grid;
  gap:1.5rem;
  margin:2rem 0
}
@media(min-width:640px){
  .game-grid{
    grid-template-columns:repeat(2,1fr)
  }
}
@media(min-width:1024px){
  .game-grid{
    grid-template-columns:repeat(3,1fr)
  }
}
.game-card{
  background:var(--card);
  border:1px solid var(--rule);
  border-radius:8px;
  overflow:hidden;
  display:flex;
  flex-direction:column;
  height:100%
}
.game-header{
  display:flex;
  justify-content:space-between;
  align-items:center;
  padding:1rem;
  background:var(--paper);
  border-bottom:1px solid var(--rule)
}
.teams{
  display:flex;
  align-items:center;
  gap:1rem
}
.team-logo{
  width:32px;
  height:32px;
  object-fit:contain
}
.team-info{
  display:flex;
  flex-direction:column
}
.team-name{
  font-weight:600;
  font-size:1.1rem
}
.pitcher{
  font-size:0.875rem;
  color:var(--muted)
}
.vs{
  font-weight:600;
  color:var(--ink);
  font-size:1.1rem
}
.game-body{
  padding:1rem;
  flex:1
}
.game-info{
  display:flex;
  justify-content:space-between;
  flex-wrap:wrap;
  gap:0.5rem;
  margin-bottom:1rem;
  font-size:0.875rem;
  color:var(--muted)
}
.game-info span{
  display:flex;
  align-items:center;
  gap:0.25rem
}
.bet-recommendation{
  margin-top:auto;
  padding:1rem;
  text-align:center;
  font-weight:600;
  font-size:1.125rem;
  border-top:1px solid var(--rule)
}
.bet-recommendation.win{
  background:#ECFDF5;
  color:var(--success)
}
.bet-recommendation.loss{
  background:#FEF2F2;
  color:var(--danger)
}
.bet-recommendation.push{
  background:#FFF7ED;
  color:var(--warning)
}
.confidence-badge{
  display:inline-block;
  padding:0.25rem 0.5rem;
  border-radius:0.25rem;
  font-size:0.75rem;
  font-weight:600;
  text-transform:uppercase
}
.confidence-high{
  background:#D1FAE5;
  color:var(--success)
}
.confidence-medium{
  background:#FEF3C7;
  color:var(--warning)
}
.confidence-low{
  background:#FEE2E2;
  color:var(--danger)
}
hr{
  border:0;
  border-top:1px solid var(--rule);
  margin:1.5rem 0
}
.section-title{
  display:flex;
  align-items:center;
  gap:0.5rem;
  margin-bottom:1.5rem
}
.section-title::before{
  content:"";
  display:inline-block;
  width:4px;
  height:24px;
  background:var(--primary);
  border-radius:2px
}
.featured-pick{
  background:var(--primary);
  color:var(--paper);
  padding:1.5rem;
  border-radius:8px;
  text-align:center;
  margin:2rem 0
}
.featured-pick h3{
  margin-top:0;
  font-size:1.25rem;
  opacity:0.9
}
.featured-pick p{
  font-size:2rem;
  font-weight:700;
  margin:0.5rem 0 0
}
/* Method page enhancements */
.method-diagram{
  background:var(--card);
  padding:1.5rem;
  border-radius:8px;
  border:1px solid var(--rule);
  margin:1.5rem 0
}
.method-step{
  display:flex;
  align-items:center;
  gap:1rem;
  padding:0.75rem 0;
  border-bottom:1px solid var(--rule)
}
.method-step:last-child{border-bottom:none}
.method-step-number{
  background:var(--primary);
  color:var(--paper);
  width:2rem;
  height:2rem;
  border-radius:50%;
  display:flex;
  align-items:center;
  justify-content:center;
  font-size:0.875rem;
  font-weight:600
}
.method-step-content{
  flex:1
}
.method-step-title{
  font-weight:600;
  margin-bottom:0.25rem
}
.method-step-description{
  font-size:0.875rem;
  color:var(--muted)
}
/* HR Board enhancements */
.hr-board{
  display:grid;
  gap:1rem
}
.hr-item{
  display:flex;
  align-items:center;
  gap:0.75rem;
  padding:0.75rem;
  background:var(--card);
  border:1px solid var(--rule);
  border-radius:6px
}
.hr-item img{
  width:24px;
  height:24px;
  border-radius:50%;
  object-fit:cover
}
.hr-details{
  flex:1
}
.hr-name{
  font-weight:600
}
.hr-team{
  font-size:0.875rem;
  color:var(--muted)
}
.hr-progress{
  height:6px;
  background:#E5E7EB;
  border-radius:3px;
  overflow:hidden;
  margin:0.5rem 0
}
.hr-progress-fill{
  height:100%;
  background:var(--primary);
  transition:width 0.3s ease
}
.hr-stats{
  display:flex;
  gap:1rem;
  font-size:0.875rem;
  color:var(--muted)
}
@media(max-width:640px){
  .ledger-head{
    grid-template-columns:repeat(2,1fr)
  }
  .stat:nth-child(2){
    border-right:none
  }
  .row{
    grid-template-columns:70px 1fr 60px;
    font-size:13px
  }
  .row .hide-m{
    display:none
  }
}
@media(prefers-reduced-motion:no-preference){
  .btn{
    transition:transform .12s ease
  }
  .btn:hover{
    transform:translateY(-2px)
  }
}
"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700'
         '&family=Public+Sans:wght@400;600&family=IBM+Plex+Mono:wght@400;600&display=swap" '
         'rel="stylesheet">')

GATES = [
    ("Minimum edge 3%", "Below that, model-vs-market disagreement is noise."),
    ("Expected value at the real price", "The edge must survive the vig --- profit is computed at the posted odds, not the fair line."),
    ("Probability band 30–70%", "The side doesn't need to be favored, but it must sit where the model's calibration is proven."),
    ("Both starting pitchers posted", "A flag built on placeholder pitching isn't the model's real opinion."),
    ("Odds between −250 and +250", "Beyond that, “edges” are usually stale lines or payout traps."),
    ("Edge sanity cap 15%", "Too good to be true means a data bug, not market-beating insight."),
    ("Game not started", "A bet logged after first pitch is hindsight, and hindsight poisons a track record."),
    ("Both lineups posted", "Without lineups, lineup-power and matchup features run on placeholder averages --- a flag built on defaults is not an opinion. Added after the July 17 incident this gate would have prevented."),
    ("Model must beat its baseline", "The totals model failed this check --- so the system refuses its bets, automatically."),
]

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

def build_index(cheat_label):
    df = load_record()
    updated = datetime.now().strftime("%B %d, %Y %H:%M")

    # Get today's featured pick for highlight
    featured_pick = None
    if df is not None and len(df) > 0:
        # Find today's pending bets with highest edge
        today = datetime.now().strftime("%Y-%m-%d")
        todays_bets = df[(df["game_date"] == today) & (df["status"] == "pending")]
        if len(todays_bets) > 0:
            # Calculate edge if not present
            if "edge" not in todays_bets.columns:
                todays_bets["edge"] = abs(todays_bets["model_prob"] - todays_bets["market_fair_prob"])
            featured_pick = todays_bets.loc[todays_bets["edge"].idxmax()]

    body = f"""
<div class="hero"><div class="wrap">
<h1>Every call logged before first&nbsp;pitch. Graded&nbsp;after.</h1>
<p class="sub">A student-built MLB model that compares its win probabilities against the
betting market, bets on paper under a nine-gate policy, and publishes the graded ledger —
wins, losses, and everything it refused to bet. Daily cards now carry a per-batter HR board:
calibrated home-run probabilities (platoon, park, and weather adjusted) with the minimum
odds worth taking.</p>
{ledger_html(df)}
"""

    if featured_pick is not None:
        # Format the bet display properly
        if featured_pick["bet_type"].startswith("total"):
            bet_display = f"{featured_pick['side'].upper()} {featured_pick['line']}"
        else:
            bet_display = f"{abbr(featured_pick['side']).upper()} ML"
        body += f"""
<div class="featured-pick">
<h3>Today's Featured Pick</h3>
<p>{bet_display} ({featured_pick['matchup']})</p>
<p>Model: {featured_pick['model_prob']:.0%} • Market: {featured_pick['market_fair_prob']:.0%} • Edge: {featured_pick['edge']:.1%}</p>
</div>
"""

    body += f"""
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
    return page("Live ledger", body) .replace("Updated —", f"Updated {updated}")
def build_method():
    body = """
<div class="hero"><div class="wrap"><h1>How the system works</h1>
<p class="sub">And, just as deliberately, what it refuses to do.</p></div></div>
<section><div class="wrap">
<h2>The pipeline</h2>
<p class="body">Six seasons of MLB results, starting pitchers, Statcast batted-ball data, and
game-time weather feed 25 leakage-safe features --- every rolling statistic uses only
information available <em>before</em> the game it describes. A calibrated logistic regression
produces win probabilities; those are compared against vig-removed consensus odds from nine
sportsbooks; disagreements above threshold become flags; flags that clear all nine gates
become simulated 1-unit paper bets, logged with their odds, probability, expected value,
and the model's top reasons. Final scores grade every bet automatically.</p>
<h2>Why the probabilities can be trusted (and where they can't)</h2>
<p class="body">Calibration analysis on held-out 2026 games shows predicted probabilities in
the 30–70% band track observed win rates. Outside that band the samples are thin and the
model measurably overconfident --- so the policy simply refuses to bet there. The betting gates
are derived from the project's own validation findings, not borrowed thresholds.</p>
<h2>What it refuses to do</h2>
<p class="body">A second model that predicts run totals failed to beat the naive
always-predict-the-average baseline in cross-validation. The system reads that verdict from
the model's own saved report card and disables O/U betting automatically --- the model exists,
and is not allowed to act, until it earns it. There is also no real-money automation anywhere:
the ledger's job is to establish, in public, whether the edges are real. Sizing stays at a
flat 1 unit; quarter-Kelly stakes are recorded in parallel for comparison but never used,
because Kelly trusts the model's probabilities and that trust is exactly what's being tested.</p>
<h2>The HR board</h2>
<p class="body">Each game card lists every confirmed batter's probability of homering ---
built bottom-up from per-plate-appearance rates (validated on 109,000 held-out plate
appearances), his lineup slot's measured trips to the plate, the platoon matchup against
tonight's starter, the park's HR factor, and a weather multiplier fitted on this project's
own games. The board shows one action number: the minimum sportsbook price worth taking.
The model's fair odds are the break-even; any price at or above them is value if the
calibration holds --- and the calibration tables are public. No EV percentages are shown
against a "consensus" this site doesn't ingest; a comparison that can't be made honestly
isn't made.</p>
<h2>Honest limitations</h2>
<p class="body">Cross-validated accuracy is ~0.55 against a 0.52 home-team baseline --- a real
but thin signal, nowhere near guaranteed to survive closing-line vig. Some prediction inputs
fall back to training-mean placeholders when lineups or weather aren't posted (a fallback
scheme rebuilt after a placeholder bias was caught flagging every road team on one slate ---
graded honestly in the project log). The sample of settled bets is small; nothing here is a
conclusion yet. That's what the ledger is for.</p>
<h2>Recent Model Improvement: Phase 5.2 Barrel-based xHR Prior</p>
<div class="method-diagram">
<p><strong>Enhanced home run prediction using Statcast barrel data:</strong></p>
<div class="method-step">
<div class="method-step-number">1</div>
<div class="method-step-content">
<div class="method-step-title">Barrel Rate Calculation</div>
<div class="method-step-description">For each batter, calculate rolling barrel rate (barrels/batted ball events) using Statcast's barrel definition (launch_speed_angle == 6) with leakage protection via shift(1) windows.</div>
</div>
</div>
<div class="method-step">
<div class="method-step-number">2</div>
<div class="method-step-content">
<div class="method-step-title">Expected HR Rate (xHR)</div>
<div class="method-step-description">Convert barrel rate to expected home run rate using league-wide HR per barrel ratio, then apply Bayesian shrinkage to stabilize small sample estimates.</div>
</div>
</div>
<div class="method-step">
<div class="method-step-number">3</div>
<div class="method-step-content">
<div class="method-step-title">Blending with Observed HR</div>
<div class="method-step-description">Mix barrel-based xHR rate with observed HR rate using optimized weight (xhr_weight) determined by validation set performance to prevent overfitting.</div>
</div>
</div>
<div class="method-step">
<div class="method-step-number">4</div>
<div class="method-step-content">
<div class="method-step-title">Log5 Integration</div>
<div class="method-step-description">Blend the prior with observed rates using the log5 framework: combined_hr = (xhr_weight * xHR_rate) + ((1 - xhr_weight) * observed_hr_rate), then apply log5 with pitcher and league averages.</div>
</div>
</div>
</div>
<p class="body">This enhancement improves home run prediction accuracy by incorporating batted ball quality metrics while maintaining all existing model validation gates.</p>
</div></section>
"""
    return page("Method", body)

def build_today(cheat_label):
    """Build today's game cards with enhanced information."""
    df = load_record()

    # Load additional data for today's games
    pitchers_data, weather_data = load_todays_data()

    # Get today's date string
    today_str = datetime.now().strftime("%Y-%m-%d")

    # If we have bets for today, use them; otherwise show a message
    todays_bets = None
    if df is not None and len(df) > 0:
        todays_bets = df[(df["game_date"] == today_str) & (df["status"] == "pending")]

    # If no bets for today, we might want to show upcoming games without bets
    # For now, we'll show the bets we have or a message

    game_cards = ""
    if todays_bets is not None and len(todays_bets) > 0:
        for _, bet in todays_bets.iterrows():
            # Get teams
            away_team = bet.get("away_team", bet.get("side") if bet.get("side") != bet.get("home_team", "") else "TBD")
            home_team = bet.get("home_team", bet.get("side") if bet.get("side") != bet.get("away_team", "") else "TBD")

            # If we don't have explicit away/home, infer from matchup
            if "away_team" not in bet or "home_team" not in bet:
                matchup = bet.get("matchup", "")
                if " @ " in matchup:
                    away_team, home_team = matchup.split(" @ ", 1)
                else:
                    away_team, home_team = "TBD", "TBD"

            # Get pitcher data
            pitcher_info = pitchers_data.get((away_team, home_team), {})
            away_pitcher = pitcher_info.get("away_pitcher", "TBD")
            home_pitcher = pitcher_info.get("home_pitcher", "TBD")
            away_era = pitcher_info.get("away_pitcher_era", 0.0)
            home_era = pitcher_info.get("home_pitcher_era", 0.0)

            # Get weather data
            weather_info = weather_data.get((away_team, home_team), {})
            temp = weather_info.get("temp", 0.0)
            wind = weather_info.get("wind", 0.0)
            condition = weather_info.get("condition", "Clear")

            # Get team logos
            away_logo = get_team_logo_path(away_team)
            home_logo = get_team_logo_path(home_team)

            # Determine bet type and confidence
            bet_type = bet.get("bet_type", "moneyline")
            if bet_type.startswith("total"):
                side = bet.get("side", "over").upper()
                line = bet.get("line", 0.0)
                display_bet = f"{side} {line}"
            else:
                side = bet.get("side", "").upper()
                display_bet = f"{abbr(side)} ML" if side else "ML"

            model_prob = float(bet.get("model_prob", 0.0))
            # Determine confidence badge class
            if model_prob >= 0.6:
                confidence_class = "confidence-high"
                confidence_text = "High"
            elif model_prob >= 0.5:
                confidence_class = "confidence-medium"
                confidence_text = "Medium"
            else:
                confidence_class = "confidence-low"
                confidence_text = "Low"

            # Determine bet outcome class for styling
            outcome_class = ""
            if bet.get("status") == "won":
                outcome_class = "win"
            elif bet.get("status") == "lost":
                outcome_class = "loss"
            elif bet.get("status") == "push":
                outcome_class = "push"

            # Format game time (assuming we have it or use placeholder)
            game_time = "TBD"  # Would need to extract from scheduled data

            game_cards += f'''
<div class="game-card {outcome_class}">
<header class="game-header">
<div class="teams">
<img src="{away_logo if away_logo else '#'}" alt="{away_team}" class="team-logo">
<div class="team-info">
<div class="team-name">{away_team}</div>
<div class="pitcher">{away_pitcher} ({away_era:.2f} ERA)</div>
</div>
</div>
<div class="vs">vs</div>
<div class="teams">
<img src="{home_logo if home_logo else '#'}" alt="{home_team}" class="team-logo">
<div class="team-info">
<div class="team-name">{home_team}</div>
<div class="pitcher">{home_pitcher} ({home_era:.2f} ERA)</div>
</div>
</div>
</header>
<div class="game-body">
<div class="game-info">
<span>🕒 {game_time}</span>
<span>📺 TBD</span>
<span>🌡️ {temp:.0f}°F 💨 {wind:.0f}mph {condition}</span>
</div>
<div class="bet-recommendation">
<span>{display_bet}</span>
<span class="confidence-badge {confidence_class}">{confidence_text} Confidence ({model_prob:.0%})</span>
</div>
</div>
</div>
'''
    else:
        game_cards = '''
<div class="game-card">
<header class="game-header">
<div class="teams">
<div class="team-info">
<div class="team-name">No games scheduled for today</div>
</div>
</div>
</div>
<div class="game-body">
<p class="text-center py-4">Check back later for today's matchups and predictions.</p>
</div>
</div>
'''

    body = f'''
<section><div class="wrap">
<h1>{cheat_label}</h1>
<p class="sub">Today's MLB matchups with model probabilities and betting recommendations.</p>
<div class="game-grid">
{game_cards}
</div>
</div></section>
'''
    return page("Today's Games", body)

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

def page(title, body, active=""):
    def navlink(href, label):
        return f'<a href="{href}">{label}</a>'
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#1E3A2F">
<link rel="manifest" href="manifest.json">
<link rel="apple-touch-icon" href="icon-192.png">
<title>{title} --- MLBQuant</title>{FONTS}
<link rel="stylesheet" href="style.css">
<script>if('serviceWorker' in navigator){{navigator.serviceWorker.register('sw.js');}}</script>
</head><body>
<header><div class="wrap bar">
<a class="mark" href="index.html">MLBQUANT</a>
<nav>{navlink("season.html", "Results")}{navlink("today.html", "Today")}{navlink("method.html", "Method")}</nav>
</div></header>
{body}
<footer><div class="wrap">All stakes are simulated 1-unit paper bets --- a public, timestamped
model track record, not wagering advice. Built by a student; every pick is logged before
first pitch and graded after. <a href="https://github.com/aa2-2/SportsQuant-AI">Source on GitHub</a>.
</div></footer></body></html>"""

if __name__ == "__main__":
    DOCS_DIR.mkdir(exist_ok=True)
    published = []

    (DOCS_DIR / "style.css").write_text(CSS, encoding="utf-8")
    published.append("style.css")

    (DOCS_DIR / "manifest.json").write_text('''{
  "name": "MLBQuant",
  "short_name": "MLBQuant",
  "description": "MLBQuant --- an MLB model paper-trading ledger. Every call logged before first pitch, graded after.",
  "start_url": "index.html",
  "display": "standalone",
  "background_color": "#EFF3EC",
  "theme_color": "#1E3A2F",
  "icons": [
    {"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
    {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"}
  ]
}''', encoding="utf-8")
    (DOCS_DIR / "sw.js").write_text('''const CACHE='mlbq-v1';
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
});''', encoding="utf-8")

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
    (DOCS_DIR / "today.html").write_text(build_today(cheat_label), encoding="utf-8")
    published.append(f"today.html ({cheat_label})")

    print("Published to docs/:")
    for item in published:
        print(f"  - {item}")
    print('\nNow run:  git add docs && git commit -m "Publish site" && git push')