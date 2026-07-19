# SportsQuant-AI Daily Automation

This repository contains automation scripts to streamline the daily data collection and site publishing process for the SportsQuant-AI MLB prediction model.

## Available Automation Scripts

### 1. Windows Batch File (`daily_update.bat`)
Double-click to run or execute from Command Prompt:
```
daily_update.bat
```

### 2. PowerShell Script (`daily_update.ps1`)
Right-click and "Run with PowerShell" or execute from PowerShell:
```
.\daily_update.ps1
```

## What the Automation Does

The automation script performs the following steps in sequence:

1. **Fetch game data** (`src/fetch_games.py`) - Updates the MLB games schedule with weather information
2. **Fetch starting pitchers** (`src/fetch_starting_pitchers.py`) - Updates today's starting pitcher data
3. **Fetch weather data** (`src/fetch_weather.py`) - Updates game-time weather forecasts
4. **Calculate betting edges** (`src/calculate_edge.py`) - Runs the model to identify betting opportunities
5. **Publish website** (`src/publish_site.py`) - Regenerates the static website with latest data
6. **Git commit and push** - Commits the updated docs/ folder and pushes to remote repository

## Prerequisites

- Python 3.x installed and in PATH
- Git installed and configured
- Required Python packages installed (see requirements.txt if available)
- Repository cloned or downloaded to local machine

## Scheduling Automation (Windows Task Scheduler)

To run this automatically each day:

1. Open Task Scheduler
2. Create Basic Task
3. Set trigger to Daily at your preferred time
4. Set action to "Start a program"
5. Program/script: `powershell.exe`
6. Add arguments: `-ExecutionPolicy Bypass -File "C:\path\to\SportsQuant-AI\daily_update.ps1"`
7. Set start in (optional): `C:\path\to\SportsQuant-AI`

## Manual Execution

If you prefer to run the steps manually, execute these commands in sequence:

```bash
python src/fetch_games.py
python src/fetch_starting_pitchers.py
python src/fetch_weather.py
python src/calculate_edge.py
python src/publish_site.py
git add docs
git commit -m "Daily update for YYYY-MM-DD"
git push
```