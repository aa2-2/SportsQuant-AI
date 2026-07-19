@echo off
cd /d %~dp0
echo Starting daily update process for SportsQuant-AI...
echo.

REM Update game data
echo Step 1/6: Fetching game data...
python src/fetch_games.py
if errorlevel 1 (
    echo Error: fetch_games.py failed
    pause
    exit /b 1
)
echo Game data updated successfully.
echo.

REM Update starting pitchers
echo Step 2/6: Fetching starting pitchers...
python src/fetch_starting_pitchers.py
if errorlevel 1 (
    echo Error: fetch_starting_pitchers.py failed
    pause
    exit /b 1
)
echo Starting pitchers updated successfully.
echo.

REM Update weather data
echo Step 3/6: Fetching weather data...
python src/fetch_weather.py
if errorlevel 1 (
    echo Error: fetch_weather.py failed
    pause
    exit /b 1
)
echo Weather data updated successfully.
echo.

REM Calculate edges
echo Step 4/6: Calculating betting edges...
python src/calculate_edge.py
if errorlevel 1 (
    echo Error: calculate_edge.py failed
    pause
    exit /b 1
)
echo Betting edges calculated successfully.
echo.

REM Publish site
echo Step 5/6: Publishing updated website...
python src/publish_site.py
if errorlevel 1 (
    echo Error: publish_site.py failed
    pause
    exit /b 1
)
echo Website published successfully.
echo.

REM Git commit and push
echo Step 6/6: Committing and pushing changes to git...
git add docs
if errorlevel 1 (
    echo Error: git add failed
    pause
    exit /b 1
)

REM Get current date for commit message
for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime ^| find "."') do set dt=%%a
set commit_date=%dt:~0,4%-%dt:~4,2%-%dt:~6,2%
git commit -m "Daily update for %commit_date%"
if errorlevel 1 (
    echo Error: git commit failed
    pause
    exit /b 1
)

git push
if errorlevel 1 (
    echo Error: git push failed
    pause
    exit /b 1
)
echo Changes committed and pushed successfully.
echo.

echo.
echo Daily update process completed successfully!
echo.
pause