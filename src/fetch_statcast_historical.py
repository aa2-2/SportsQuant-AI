import pybaseball
import pandas as pd
import time

def fetch_statcast_year(year):
    """
    Pulls a full season of Statcast data, one month at a time.
    """
    if year == 2026:
        # Partial season - only through what's actually been played
        month_ranges = [
            (f"{year}-03-01", f"{year}-03-31"),
            (f"{year}-04-01", f"{year}-04-30"),
            (f"{year}-05-01", f"{year}-05-31"),
            (f"{year}-06-01", f"{year}-06-30"),
            (f"{year}-07-01", f"{year}-07-31"),
        ]
    else:
        month_ranges = [
            (f"{year}-03-01", f"{year}-03-31"),
            (f"{year}-04-01", f"{year}-04-30"),
            (f"{year}-05-01", f"{year}-05-31"),
            (f"{year}-06-01", f"{year}-06-30"),
            (f"{year}-07-01", f"{year}-07-31"),
            (f"{year}-08-01", f"{year}-08-31"),
            (f"{year}-09-01", f"{year}-09-30"),
            (f"{year}-10-01", f"{year}-10-31"),
        ]

    all_months = []
    for start, end in month_ranges:
        print(f"Fetching Statcast {start} to {end}...")
        month_df = pybaseball.statcast(start_dt=start, end_dt=end)
        all_months.append(month_df)
        time.sleep(1)

    return pd.concat(all_months, ignore_index=True)


if __name__ == "__main__":
    for year in [2024, 2025]:
        print(f"\n=== Fetching {year} ===")
        df = fetch_statcast_year(year)
        df.to_csv(f"data/statcast_{year}.csv", index=False)
        print(f"{year}: {len(df)} pitches saved to data/statcast_{year}.csv")

    print("\nNote: statcast_2026.csv already exists from earlier today - not re-pulled.")