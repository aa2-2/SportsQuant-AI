"""
Debug version of build_current_rates.py with progress prints
"""
import sys
from pathlib import Path

import joblib
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DATA_DIR  # noqa: E402
from sim.batter_rates import CATEGORIES, build_pa_table, log5, add_rolling_rates, log5_with_xhr, league_barrel_rate  # noqa: E402
from sim.game_hr import (  # noqa: E402
    add_batter_teams, add_lineup_slots, add_team_starters,
    slot_pa_distribution, starter_share,
)

SEASONS = [2024, 2025, 2026]
WINDOW = 500
SHRINK = 200
SPLIT_SHRINK = 120  # platoon prior: the batter's own overall rates


def _shrunk(grp, league, shrink):
    n = len(grp)
    return {c: float(((grp["outcome"] == c).sum() + shrink * league[c]) / (n + shrink))
            for c in CATEGORIES}


def current_rates(pa, entity_col, split_col=None):
    """
    Shrunk per-category rates over each entity's last WINDOW PAs.
    With split_col ("p_throws" for batters, "stand" for pitchers),
    also computes vs-R / vs-L splits — shrunk toward the entity's own
    OVERALL rate, so a thin platoon sample leans on the full body of
    work rather than the league.
    """
    league = {c: float((pa["outcome"] == c).mean()) for c in CATEGORIES}
    tail = pa.groupby(entity_col, sort=False).tail(WINDOW)
    out = {}
    for entity, grp in tail.groupby(entity_col, sort=False):
        overall = _shrunk(grp, league, SHRINK)
        entry = {"overall": overall}
        if split_col and split_col in grp.columns:
            for hand in ("R", "L"):
                sub = grp[grp[split_col] == hand]
                entry[f"vs_{hand}"] = _shrunk(sub, overall, SPLIT_SHRINK) if len(sub) else overall
        out[int(entity)] = entry
    return out, league


def compute_xhr_prior(pa, batter_rates, pitcher_rates, league, validation_start_date="2025-07-01"):
    """
    Compute barrel-based xHR prior and optimize blending weight.

    Returns:
    - batter_rates_updated: batter rates with blended HR rates
    - optimal_weight: the weight that minimizes validation log-loss
    """
    print("Starting compute_xhr_prior...")

    # Calculate league barrel rate for reference
    lg_barrel_rate = league_barrel_rate(pa)
    print(f"League barrel rate: {lg_barrel_rate}")

    # Calculate barrel rates for each batter using rolling window approach (leakage-safe)
    barrel_rates = {}

    print("Calculating barrel rates for batters...")
    batter_count = pa["batter"].nunique()
    processed = 0

    for batter_id, batter_pa in pa.groupby("batter"):
        processed += 1
        if processed % 50 == 0:
            print(f"  Processed {processed}/{batter_count} batters")

        # Sort by date to ensure proper temporal ordering
        sort_cols = ["game_date"]
        if "at_bat_number" in batter_pa.columns:
            sort_cols.append("at_bat_number")
        batter_pa_sorted = batter_pa.sort_values(sort_cols)

        # Calculate rolling sums, shifted by 1 to prevent leakage
        is_barrel = (batter_pa_sorted["launch_speed_angle"] == 6).astype(float)
        # Ball in play: not a walk, strikeout, or hit by pitch
        is_bip = (~batter_pa_sorted["outcome"].isin(["walk", "strikeout", "hit_by_pitch", "intentional_walk"])).astype(float)
        barrels_rolling = is_barrel.rolling(window=WINDOW, min_periods=1).sum().shift(1)
        bip_rolling = is_bip.rolling(window=WINDOW, min_periods=1).sum().shift(1)

        # Calculate barrel rate (handle division by zero)
        barrel_rate = np.where(bip_rolling > 0, barrels_rolling / bip_rolling, 0.0)

        # Apply shrinkage toward league barrel rate
        barrel_rate_shrunk = (barrels_rolling + SHRINK * lg_barrel_rate) / (bip_rolling + SHRINK)
        barrel_rate_shrunk = np.where(bip_rolling + SHRINK > 0, barrel_rate_shrunk, lg_barrel_rate)

        # Fill NaN values (first PA) with league average
        barrel_rate_shrunk = np.where(np.isnan(barrel_rate_shrunk), lg_barrel_rate, barrel_rate_shrunk)

        barrel_rates[batter_id] = barrel_rate_shrunk

    print(f"Finished calculating barrel rates for {len(barrel_rates)} batters")

    # Calculate optimal blending weight using validation period
    cutoff = "2026-03-25"
    val_mask = (pa["game_date"] >= validation_start_date) & (pd.to_datetime(pa["game_date"]) < pd.Timestamp(cutoff))
    print(f"Validation mask sum: {val_mask.sum()}")

    if val_mask.sum() == 0:
        # Fallback if no validation data
        optimal_weight = 0.0
        optimal_damp = 0.9  # From our validation
        print("No validation data found, using defaults")
    else:
        # Get validation data
        val_pa = pa[val_mask].copy()
        y_val = (val_pa["outcome"] == "home_run").astype(float).values
        print(f"Validation set size: {len(y_val)}")

        # Get batter and pitcher IDs for validation set
        batters_val = val_pa["batter"].values
        pitchers_val = val_pa["pitcher"].values

        # Calculate barrel rate for validation set (leakage-safe) - using same approach as above
        print("Calculating validation barrel rates...")
        is_barrel_val = (val_pa["launch_speed_angle"] == 6).astype(float)
        # Ball in play: not a walk, strikeout, or hit by pitch
        is_bip_val = (~val_pa["outcome"].isin(["walk", "strikeout", "hit_by_pitch", "intentional_walk"])).astype(float)
        barrels_rolling_val = is_barrel_val.rolling(window=WINDOW, min_periods=1).sum().shift(1)
        bip_rolling_val = is_bip_val.rolling(window=WINDOW, min_periods=1).sum().shift(1)
        barrel_rate_val = (barrels_rolling_val / bip_rolling_val).fillna(lg_barrel_rate)  # league average

        # Get league HR rate for validation set (expanding + shifted)
        is_hr = (pa["outcome"] == "home_run").astype(float)
        league_hr = is_hr.expanding().mean().shift(1).fillna(is_hr.mean())
        league_hr_vals = league_hr.values[val_mask]
        print(f"League HR values shape: {league_hr_vals.shape}")

        # Get batter HR rates for validation set
        print("Getting batter HR rates for validation set...")
        bat_hr_rates = np.array([batter_rates.get(b, {}).get("overall", {}).get("home_run", league_hr_vals[i])
                                for i, b in enumerate(batters_val)])

        # Get pitcher allowed HR rates for validation set
        print("Getting pitcher HR rates for validation set...")
        pit_hr_rates = np.array([pitcher_rates.get(p, {}).get("overall", {}).get("home_run", league_hr_vals[i])
                                for i, p in enumerate(pitchers_val)])

        # Optimize damp and xhr_weight on validation set
        best_damp, best_xhr_weight = 0.9, 0.0  # Defaults from our test
        best_ll = float('inf')

        print("Starting grid search for optimal parameters...")
        # Grid search for damp
        damp_values = [1.0, 0.9, 0.8, 0.7, 0.6]
        xhr_weight_values = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

        total_combinations = len(damp_values) * len(xhr_weight_values)
        current = 0

        for damp in damp_values:
            # Grid search for xhr_weight
            for w in xhr_weight_values:
                current += 1
                if current % 10 == 0:
                    print(f"  Progress: {current}/{total_combinations} combinations tested")

                # Calculate xhr rate for validation set: using league HR rate as proxy for league_hr_per_barrel
                xhr_rate = league_hr_vals * barrel_rate_val.values

                # Blended hr rate
                blended_hr = w * xhr_rate + (1 - w) * bat_hr_rates

                ll = 0.0
                eps = 1e-9
                for i in range(len(y_val)):
                    p_pred = log5_with_xhr(
                        blended_hr[i],
                        pit_hr_rates[i],
                        league_hr_vals[i],
                        barrel_rate_val.values[i],
                        league_hr_vals[i],  # Using league_hr as proxy for league_hr_per_barrel
                        damp=damp,
                        xhr_weight=w)
                    p_pred = max(eps, min(1.0 - eps, p_pred))
                    ll += -(y_val[i] * np.log(p_pred) + (1 - y_val[i]) * np.log(1.0 - p_pred))
                ll /= len(y_val)

                if ll < best_ll:
                    best_ll, best_damp, best_xhr_weight = ll, damp, w
                    print(f"    New best: damp={damp}, xhr_weight={w}, ll={ll:.5f}")

        optimal_weight = best_xhr_weight
        optimal_damp = best_damp
        print(f"Grid search complete. Best: damp={optimal_damp}, xhr_weight={optimal_weight}")

    print(f"Optimal XHR weight: {optimal_weight:.3f}, Optimal damp: {optimal_damp:.1f}")

    # Apply the optimal weight to create blended HR rates for all batters
    print("Applying optimal weight to create blended HR rates...")
    updated_batter_rates = {}
    processed = 0
    total_batters = len(batter_rates)

    for batter_id, rates in batter_rates.items():
        processed += 1
        if processed % 50 == 0:
            print(f"  Processed {processed}/{total_batters} batters for blending")

        if "overall" not in rates:
            updated_batter_rates[batter_id] = rates
            continue

        # Get original HR rate
        original_hr_rate = rates["overall"].get("home_run", league["home_run"])

        # Get barrel rate for this batter (use most recent value, default to league average)
        barrel_rate = lg_barrel_rate  # Default
        if batter_id in barrel_rates and len(barrel_rates[batter_id]) > 0:
            # Get the most recent barrel rate (last element)
            barrel_rate = barrel_rates[batter_id][-1]

        # Calculate xHR rate: league HR rate * barrel rate
        xhr_rate = league["home_run"] * barrel_rate

        # Blend: weight * xHR + (1-weight) * observed
        blended_hr_rate = optimal_weight * xhr_rate + (1 - optimal_weight) * original_hr_rate

        # Update the rates dictionary
        updated_rates = rates.copy()
        if "overall" not in updated_rates:
            updated_rates["overall"] = {}
        updated_rates["overall"]["home_run"] = blended_hr_rate

        # Also update platoon splits if they exist
        for hand in ["R", "L"]:
            key = f"vs_{hand}"
            if key in rates:
                if key not in updated_rates:
                    updated_rates[key] = {}
                original_hr_rate_split = rates[key].get("home_run", league["home_run"])
                blended_hr_rate_split = optimal_weight * xhr_rate + (1 - optimal_weight) * original_hr_rate_split
                updated_rates[key]["home_run"] = blended_hr_rate_split

        updated_batter_rates[batter_id] = updated_rates

    print(f"Finished processing {len(updated_batter_rates)} batters")
    return updated_batter_rates, optimal_weight


if __name__ == "__main__":
    print("Starting build_current_rates_debug.py...")
    frames = []
    cols = ["game_pk", "game_date", "batter", "pitcher", "events",
            "inning_topbot", "home_team", "away_team", "at_bat_number",
            "stand", "p_throws", "launch_speed", "launch_speed_angle"]
    for year in SEASONS:
        print(f"Loading statcast_{year}.csv...")
        frames.append(pd.read_csv(DATA_DIR / f"statcast_{year}.csv", usecols=cols))
    pa = build_pa_table(pd.concat(frames, ignore_index=True),
                        keep_cols=("inning_topbot", "home_team", "away_team",
                                   "at_bat_number", "stand", "p_throws",
                                   "launch_speed", "launch_speed_angle"))
    print(f"Plate appearances: {len(pa):,}")

    print("Computing current batter rates (with platoon splits)...")
    batter_rates, league = current_rates(pa, "batter", split_col="p_throws")
    print("Computing current pitcher-allowed rates (with platoon splits)...")
    pitcher_rates, _ = current_rates(pa, "pitcher", split_col="stand")

    # Apply XHR prior optimization
    print("Applying barrel-based xHR prior optimization...")
    batter_rates, xhr_weight = compute_xhr_prior(pa, batter_rates, pitcher_rates, league)

    hands = {}
    if "p_throws" in pa.columns:
        hands["pitcher"] = pa.groupby("pitcher")["p_throws"].agg(
            lambda s: s.mode().iloc[0]).to_dict()
    if "stand" in pa.columns:
        hands["batter"] = pa.groupby("batter")["stand"].agg(
            lambda s: s.mode().iloc[0]).to_dict()

    # Weather -> HR multiplier, fitted on OUR games (features CSV has
    # historical temp / signed wind + we can count HRs per game)
    print("Fitting weather HR multiplier from own games...")
    feats = pd.read_csv(DATA_DIR / "games_with_features_all_seasons.csv",
                        usecols=["game_pk", "date", "temp", "wind_speed", "signed_wind"])
    game_hrs = (pa.assign(hr=(pa["outcome"] == "home_run").astype(int))
                .groupby("game_pk")["hr"].sum().rename("hrs").reset_index())
    wx = feats.merge(game_hrs, on="game_pk", how="inner").dropna()
    X = np.column_stack([np.ones(len(wx)), wx["temp"], wx["signed_wind"]])
    coefs, *_ = np.linalg.lstsq(X, wx["hrs"].values.astype(float), rcond=None)
    weather_hr = {"temp_coef": float(coefs[1]), "wind_coef": float(coefs[2]),
                  "mean_hrs": float(wx["hrs"].mean()),
                  "mean_temp": float(wx["temp"].mean())}
    print(f"  {weather_hr['temp_coef']:+.4f} HRs/degF, {weather_hr['wind_coef']:+.4f} HRs/mph "
          f"(mean {weather_hr['mean_hrs']:.2f} HRs/game)")

    pa = add_team_starters(add_lineup_slots(add_batter_teams(pa)))
    bundle = {
        "batter_rates": batter_rates,
        "pitcher_rates": pitcher_rates,
        "hands": hands,
        "league": league,
        "slot_dist": slot_pa_distribution(pa),
        "starter_share": starter_share(pa),
        "damp": 0.9,  # Use the damp value from our validation
        "asof": str(pa["date"].max().date()),
        "xhr_weight": xhr_weight,  # Store the optimal weight for transparency
    }
    joblib.dump(bundle, DATA_DIR / "sim_rates.joblib")
    print(f"\n{len(batter_rates):,} batters, {len(pitcher_rates):,} pitchers, "
          f"data through {bundle['asof']}")
    print(f"Saved to {DATA_DIR / 'sim_rates.joblib'}")