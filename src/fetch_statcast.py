import pybaseball
import pandas as pd
import time

def fetch_statcast_season(year):
    """
    Pulls full-season Statcast pitch-by-pitch data, one month at a time
    (matches the same chunking approach used for fetch_games.py, since
    pulling a whole season in one call is slow and riskier to retry).
    """
    month_ranges = [
        (f"{year}-03-01", f"{year}-03-31"),
        (f"{year}-04-01", f"{year}-04-30"),
        (f"{year}-05-01", f"{year}-05-31"),
        (f"{year}-06-01", f"{year}-06-30"),
        (f"{year}-07-01", f"{year}-07-31"),
    ]

    all_months = []
    for start, end in month_ranges:
        print(f"Fetching Statcast {start} to {end}...")
        month_df = pybaseball.statcast(start_dt=start, end_dt=end)
        all_months.append(month_df)
        time.sleep(1)

    full_season = pd.concat(all_months, ignore_index=True)
    return full_season


if __name__ == "__main__":
    df = fetch_statcast_season(2026)
    print(f"\nTotal pitches collected: {len(df)}")
    df.to_csv("data/statcast_2026.csv", index=False)
    print("Saved to data/statcast_2026.csv")