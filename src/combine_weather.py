"""
Combines the historical and current-season weather pulls into one file.
(Renamed from combine.weather.py — the extra dot made the module
un-importable and easy to mistake for a data file.)
"""
import pandas as pd

from config import DATA_DIR

if __name__ == "__main__":
    w1 = pd.read_csv(DATA_DIR / "weather_2024_2025.csv")
    w2 = pd.read_csv(DATA_DIR / "weather.csv")
    combined = pd.concat([w1, w2], ignore_index=True)
    combined.to_csv(DATA_DIR / "weather_all_seasons.csv", index=False)
    print(f"Combined weather: {len(combined)} games")
