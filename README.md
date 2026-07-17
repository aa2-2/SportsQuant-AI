# SportsQuant-AI

An MLB game-prediction and analytics pipeline built from scratch, combining live sports data APIs, Statcast pitch-level data, leakage-safe feature engineering, and machine learning — built as a portfolio project to demonstrate quantitative thinking, data engineering, and responsible use of AI for a finance/data-focused internship search.

Created by Alex Anastos

---

## What this project actually does

Given an MLB schedule date, this pipeline predicts each game's home-team win probability using a model trained on real historical performance — not just team records, but starting pitcher quality, ballpark and weather effects, team batting strength, and historical batter-vs-pitcher and pitcher-vs-team matchup data.

This is a prediction model, not yet a full betting tool — it estimates win probability but does not currently compare against sportsbook odds. See [Known Limitations](#known-limitations--next-steps) below for an honest account of what's still missing.

---

## Project goals

- Collect real MLB data through public APIs (MLB Stats API, Baseball Savant/Statcast)
- Engineer prediction features the right way: leakage-safe, verified against real outcomes at every step
- Train and honestly evaluate multiple models (logistic regression, Random Forest) using proper time-based cross-validation, not just a single train/test split
- Generate live predictions for upcoming, real-world games
- Do all of the above transparently enough to explain every decision in an interview

---

## Current results

The model is trained on 6,293 games (2024–2026 seasons) using 23 leakage-safe features. Performance is evaluated using 5-fold time-series cross-validation (not a single lucky split):

| Model | Cross-validated accuracy | Baseline (always pick home team) |
|---|---|---|
| Logistic Regression | **0.559** (± 0.016) | 0.522 |
| Random Forest | 0.550 (± 0.022) | 0.522 |

Logistic Regression is the current production model. For context: even professional sportsbook models are typically only slightly better than a coin flip on individual MLB games, so this result — a real, validated edge over the home-field baseline — is a meaningful, honestly-earned outcome rather than a headline number.

---

## Features used

All features are calculated using only information available **strictly before** the game being predicted (no data leakage) — verified individually during development, not just assumed.

| Feature | What it measures |
|---|---|
| Team run differential | Season-to-date scoring margin, home & away |
| Starting pitcher ERA | Rolling ERA over last 5 starts |
| Starting pitcher whiff rate | Swing-and-miss rate, from real Statcast pitch data |
| HR-specific park factor | How much a park inflates/suppresses home runs specifically, calculated from real 2024–2026 home run data (not general run scoring) |
| Temperature / wind speed | Real recorded game-day weather (MLB Stats API) |
| Team batting strength | Rolling average exit velocity, HR rate, strikeout rate |
| Top-power-hitters strength | Same, but isolated to a team's top 4 power hitters by recent form (verified as a genuinely distinct signal from team averages, not redundant) |
| Pitcher-vs-opponent ERA | A starter's historical ERA specifically against today's opponent (2021–2026 history) |
| Team-vs-pitcher batting average | Confirmed lineup's historical batting average against today's specific starter (2024–2026 Statcast matchup history) |

**Data sources:** MLB Stats API (schedule, boxscores, weather, probable pitchers/lineups) and Baseball Savant/Statcast via `pybaseball` (pitch-level data: exit velocity, launch angle, pitch outcomes).

---

## Project structure

```
SportsQuant-AI/
├── data/                       # generated data (gitignored — see Rebuilding the Data)
├── src/
│   ├── config.py                       # shared FEATURE_COLUMNS / TARGET_COLUMN
│   ├── fetch_games.py                  # pulls game results from MLB Stats API
│   ├── fetch_historical_seasons.py     # pulls multiple seasons of games
│   ├── fetch_starting_pitchers.py      # pulls starting pitcher boxscore stats
│   ├── fetch_historical_pitchers.py    # same, across all seasons
│   ├── fetch_statcast.py               # pulls current-season Statcast data
│   ├── fetch_statcast_historical.py    # pulls prior-season Statcast data
│   ├── fetch_weather.py / fetch_weather_historical.py
│   ├── features/
│   │   ├── win_pct.py                  # rolling pregame win percentage
│   │   ├── recent_form.py              # last-10-games win percentage
│   │   ├── run_differential.py         # rolling run differential
│   │   ├── rest_days.py                # days since last game
│   │   ├── pitcher_era.py              # rolling starting-pitcher ERA
│   │   ├── pitcher_quality.py          # Statcast-based pitcher contact quality
│   │   ├── pitcher_vs_team.py          # pitcher ERA vs. specific opponent
│   │   ├── ballpark.py                 # general & HR-specific park factor
│   │   ├── weather.py                  # temperature / wind parsing
│   │   ├── batting_strength.py         # team-level rolling batting stats
│   │   ├── batter_power.py             # top-power-hitter tracking
│   │   └── batter_vs_pitcher.py        # batter-vs-pitcher matchup history
│   ├── build_features.py               # single-season feature pipeline
│   ├── build_features_all_seasons.py   # multi-season feature pipeline
│   ├── train_model.py                  # trains & cross-validates both models
│   └── predict_upcoming.py             # generates live predictions for a given date
├── requirements.txt
└── README.md
```

---

## Setup

```bash
pip install -r requirements.txt
```

---

## Rebuilding the Data

Large data files (multi-season game data, Statcast pitch-level data, trained models) are excluded from this repository via `.gitignore` — they're regenerable and too large for GitHub's file size limits. To rebuild everything from scratch, run these in order:

**1. Pull historical game data (2021–2026)**
```bash
python src/fetch_historical_seasons.py
```
Creates `data/games_all_seasons.csv`

**2. Pull starting pitcher data for all seasons**
```bash
python src/fetch_historical_pitchers.py
```
Creates `data/starting_pitchers_all_seasons.csv`. Takes 30–60+ minutes — this pulls one boxscore per game across ~13,500 games.

**3. Pull Statcast pitch-level data (2024–2026)**
```bash
python src/fetch_statcast_historical.py
python src/fetch_statcast.py
```
Creates `data/statcast_2024.csv`, `data/statcast_2025.csv`, `data/statcast_2026.csv`. These are large (~450–475MB each) and can each take 15–30+ minutes to pull.

**4. Pull weather data**
```bash
python src/fetch_weather_historical.py
python src/fetch_weather.py
python src/combine.weather.py
```
Creates `data/weather_all_seasons.csv`

**5. Build the full feature set**
```bash
python src/build_features_all_seasons.py
```
Creates `data/games_with_features_all_seasons.csv` — the final training dataset (~6,293 games with all 23 features).

**6. Train the model**
```bash
python src/train_model.py
```
Creates `data/trained_model.joblib`, `data/feature_scaler.joblib`, `data/random_forest_model.joblib`, and prints full accuracy/cross-validation results.

**7. Generate predictions for upcoming games**
```bash
python src/predict_upcoming.py
```
Prints win probabilities for each scheduled game on the target date (currently hardcoded inside the script — see Known Limitations).

---

## Design principles followed throughout

- **No data leakage.** Every rolling/historical feature uses `shift(1)` before any average or sum, so a game's own outcome can never influence its own pregame features. Verified individually for every feature during development (e.g., confirming season-opening games show neutral defaults, not real data that hasn't happened yet).
- **Honest evaluation over impressive numbers.** Every model result is checked with 5-fold time-series cross-validation, not just a single train/test split — a single lucky split produced a flashier number early on that didn't hold up under proper testing, and the more conservative, cross-validated number is what's reported here.
- **Neutral fallbacks, not guesses.** Every feature has an explicit, documented neutral default for cases with insufficient history (e.g., a team's first game of the season, or a pitcher facing a new opponent) — never a silent guess.
- **Empirical testing over intuition.** Every new feature was tested for actual impact on cross-validated accuracy before being kept. Notably, adding more Statcast pitcher-quality features did *not* improve accuracy on a smaller dataset — a legitimate negative result that directly motivated pulling more historical data instead, which did.

---

## Known Limitations & Next Steps

This project is under active development. Current known gaps, in rough priority order:

1. **Not yet a true betting tool.** The model outputs a win probability but does not compare against real sportsbook odds, so it cannot yet identify betting "value" or edge.
2. **Accuracy alone isn't sufficient for betting use.** Calibration (does a game graded "60%" actually win ~60% of the time?) has not yet been formally measured via log loss, Brier score, or a probability-calibration table.
3. **Some prediction inputs use neutral placeholders** when live data isn't available yet at prediction time (e.g., pitcher whiff rate, weather for future games) — the script does not yet report per-prediction data-quality/confidence.
4. **`TARGET_DATE` is hardcoded** in `predict_upcoming.py` rather than accepted as a command-line argument.
5. **No automated tests yet** for the leakage-sensitive feature functions (e.g., verifying doubleheader ordering, innings-pitched conversion, or missing-data fallbacks stay correct as the code evolves).
6. **Opponent-specific pitcher ERA and batter-vs-pitcher averages can be based on small samples** and would benefit from shrinkage toward each pitcher's/batter's overall rate as sample size increases.

Longer-term, larger ideas intentionally deferred: full 9-player lineup-level batter tracking beyond the current top-power-hitter proxy, batter-vs-specific-pitch-type matchups (would require deeper Statcast pitch-type analysis), a live dashboard, and an AI-generated natural-language explanation layer for individual predictions.