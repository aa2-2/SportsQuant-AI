"""
Generates calibrated win-probability predictions for a date's MLB games.

Usage:
    python src/predict_upcoming.py                # today's games
    python src/predict_upcoming.py --date 2026-07-18
"""
import argparse
from datetime import date

import pandas as pd

from config import DATA_DIR
from explain import explain_prediction, format_reasons, load_raw_model
from live_features import (
    build_game_feature_row,
    load_prediction_context,
    get_pitcher_era,
    get_pitcher_era_vs_opponent,
    get_upcoming_schedule,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate MLB game win-probability predictions for a given date."
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Target date in YYYY-MM-DD format. Defaults to today.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    target_date = args.date if args.date else date.today().isoformat()

    schedule = get_upcoming_schedule(target_date)

    ctx = load_prediction_context(DATA_DIR)
    starts = ctx["starts"]  # used below for the per-starter ERA display
    model, scaler = ctx["model"], ctx["scaler"]
    raw_model = load_raw_model()  # for the "why" breakdown

    print(f"\nPredictions for {target_date}\n" + "=" * 50)

    if len(schedule) == 0:
        print("No games scheduled on this date.")

    for _, game in schedule.iterrows():
        home, away = game["home_team"], game["away_team"]

        try:
            row, live_weather = build_game_feature_row(game, ctx)
        except KeyError:
            print(f"\n{away} @ {home}")
            print("  Skipped: team not found in historical data (name mismatch?)")
            continue

        home_win_prob = model.predict_proba(scaler.transform(row))[0][1]

        home_era = get_pitcher_era(starts, game["home_pitcher_name"])
        away_era = get_pitcher_era(starts, game["away_pitcher_name"])
        home_era_vs_opp = get_pitcher_era_vs_opponent(starts, game["home_pitcher_name"], away)
        away_era_vs_opp = get_pitcher_era_vs_opponent(starts, game["away_pitcher_name"], home)

        # Honest data-quality report: which inputs are real vs invented
        # neutral values, so a precise-looking % can't hide thin inputs.
        missing_inputs = []
        if not (game["home_lineup"] and game["away_lineup"]):
            missing_inputs.append("confirmed lineups (batter power + matchup features on neutral defaults)")
        if live_weather is None:
            missing_inputs.append("real weather (using 78F / calm)")
        if game["home_pitcher_name"] is None or game["away_pitcher_name"] is None:
            missing_inputs.append("probable pitcher(s) (ERA features on league average)")
        missing_inputs.append("current pitcher whiff rates (always placeholder for upcoming games)")

        quality = "HIGH" if len(missing_inputs) == 1 else ("MEDIUM" if len(missing_inputs) == 2 else "LOW")

        toward_home, toward_away = explain_prediction(raw_model, scaler, row)

        print(f"\n{away} @ {home}")
        print(f"  Home starter: {game['home_pitcher_name'] or 'TBD'} "
              f"(ERA {home_era:.2f}, vs {away}: {home_era_vs_opp:.2f})")
        print(f"  Away starter: {game['away_pitcher_name'] or 'TBD'} "
              f"(ERA {away_era:.2f}, vs {home}: {away_era_vs_opp:.2f})")
        print(f"  Model (calibrated): {home} win probability = {home_win_prob:.1%}")
        print(f"  Pushing toward {home}: {format_reasons(toward_home)}")
        print(f"  Pushing toward {away}: {format_reasons(toward_away)}")
        print(f"  Data quality: {quality}")
        for item in missing_inputs:
            print(f"    - missing: {item}")
