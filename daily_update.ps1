# Daily update script for SportsQuant-AI
# This script automates the daily data collection and site publishing process

# Set working directory to the script's directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location -Path $scriptDir

Write-Host "Starting daily update process for SportsQuant-AI..." -ForegroundColor Green
Write-Host ""

try {
    # Update game data
    Write-Host "Step 1/6: Fetching game data..." -ForegroundColor Yellow
    python src/fetch_games.py
    Write-Host "Game data updated successfully." -ForegroundColor Green
    Write-Host ""

    # Update starting pitchers
    Write-Host "Step 2/6: Fetching starting pitchers..." -ForegroundColor Yellow
    python src/fetch_starting_pitchers.py
    Write-Host "Starting pitchers updated successfully." -ForegroundColor Green
    Write-Host ""

    # Update weather data
    Write-Host "Step 3/6: Fetching weather data..." -ForegroundColor Yellow
    python src/fetch_weather.py
    Write-Host "Weather data updated successfully." -ForegroundColor Green
    Write-Host ""

    # Calculate edges
    Write-Host "Step 4/6: Calculating betting edges..." -ForegroundColor Yellow
    python src/calculate_edge.py
    Write-Host "Betting edges calculated successfully." -ForegroundColor Green
    Write-Host ""

    # Publish site
    Write-Host "Step 5/6: Publishing updated website..." -ForegroundColor Yellow
    python src/publish_site.py
    Write-Host "Website published successfully." -ForegroundColor Green
    Write-Host ""

    # Git commit and push
    Write-Host "Step 6/6: Committing and pushing changes to git..." -ForegroundColor Yellow
    git add docs
    $commitDate = Get-Date -Format "yyyy-MM-dd"
    git commit -m "Daily update for $commitDate"
    git push
    Write-Host "Changes committed and pushed successfully." -ForegroundColor Green
    Write-Host ""

    Write-Host "Daily update process completed successfully!" -ForegroundColor Green
}
catch {
    Write-Host "Error occurred during daily update process:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Pause
}