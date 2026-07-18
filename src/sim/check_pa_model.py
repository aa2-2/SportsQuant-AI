"""
THE PHASE A GATE: does the per-PA model actually know more than the
league average?

On held-out 2026 plate appearances, compares log-loss of the model's
HR-per-PA probability (rolling batter rate x pitcher-allowed rate via
log5) against the baseline "assign every PA the league HR rate."
Also prints a calibration table — predicted probability bins vs the
HR rate that actually happened in each bin.

If the model doesn't beat the baseline, nothing gets built on top of
it. Same rule as every model in this project.

    python src/sim/check_pa_model.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DATA_DIR  # noqa: E402
from sim.batter_rates import (  # noqa: E402
    add_rolling_rates, build_pa_table, log5, log5_with_xhr
)

CUTOFF = "2026-03-25"
SEASONS = [2024, 2025, 2026]


def log_loss(y, p, eps=1e-9):
    p = np.clip(p, eps, 1 - eps)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


if __name__ == "__main__":
    frames = []
    for year in SEASONS:
        print(f"Loading statcast_{year}.csv (PA columns only)...")
        frames.append(pd.read_csv(
            DATA_DIR / f"statcast_{year}.csv",
            usecols=["game_pk", "game_date", "batter", "pitcher", "events",
                     "launch_speed", "launch_speed_angle"],
        ))
    pa = build_pa_table(pd.concat(frames, ignore_index=True),
                        keep_cols=["launch_speed", "launch_speed_angle"])
    print(f"Plate appearances: {len(pa):,}")

    print("Computing rolling batter rates (this takes a minute)...")
    pa = add_rolling_rates(pa, "batter", prefix="bat")
    print("Computing rolling pitcher-allowed rates...")
    pa = add_rolling_rates(pa, "pitcher", prefix="pit")

    # League HR rate, expanding + shifted (no PA sees itself)
    is_hr = (pa["outcome"] == "home_run").astype(float)
    pa["league_hr"] = is_hr.expanding().mean().shift(1).fillna(is_hr.mean())

    holdout = pa[pa["game_date"] >= CUTOFF].copy()
    print(f"\nHoldout 2026 PAs: {len(holdout):,}")

    # Damping and xhr_weight selected on a validation window strictly BEFORE the
    # holdout — tuning on the holdout would be lying with extra steps.
    val = pa[(pa["game_date"] >= "2025-07-01") & (pa["game_date"] < CUTOFF)]
    y_val = (val["outcome"] == "home_run").astype(float).values
    best_damp, best_ll = 1.0, float("inf")
    for damp in [1.0, 0.9, 0.8, 0.7, 0.6]:
        ll = log_loss(y_val, log5(val["bat_home_run_rate"].values,
                                  val["pit_home_run_rate"].values,
                                  val["league_hr"].values, damp=damp))
        marker = ""
        if ll < best_ll:
            best_damp, best_ll, marker = damp, ll, "  <- best"
        print(f"  damp {damp:.1f}: validation log-loss {ll:.5f}{marker}")
    print(f"Selected damp = {best_damp} (validation only)")

    # Now find optimal xhr_weight using the same validation set
    # Calculate barrel rate for validation set (leakage-safe)
    is_barrel_val = (val["launch_speed_angle"] == 6).astype(float)
    # Ball in play: not a walk, strikeout, or hit by pitch
    is_bip_val = (~val["outcome"].isin(["walk", "strikeout", "hit_by_pitch", "intentional_walk"])).astype(float)
    barrel_sum_val = is_barrel_val.rolling(window=500, min_periods=1).sum().shift(1)
    bip_sum_val = is_bip_val.rolling(window=500, min_periods=1).sum().shift(1)
    barrel_rate_val = (barrel_sum_val / bip_sum_val).fillna(0.08)  # league average

    best_xhr_weight, best_xhr_ll = 0.5, float("inf")
    for w in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
        # Calculate xhr rate for validation set: using league HR rate as proxy
        xhr_rate = val["league_hr"].values * barrel_rate_val.values

        # Blended hr rate
        blended_hr = w * xhr_rate + (1 - w) * val["bat_home_run_rate"].values

        ll = log_loss(y_val, log5_with_xhr(
            blended_hr,
            val["pit_home_run_rate"].values,
            val["league_hr"].values,
            barrel_rate_val.values,
            val["league_hr"].values,  # Using league_hr as proxy for league_hr_per_barrel
            damp=best_damp,
            xhr_weight=w))
        marker = ""
        if ll < best_xhr_ll:
            best_xhr_weight, best_xhr_ll, marker = w, ll, "  <- best"
        print(f"  xhr_weight {w:.1f}: validation log-loss {ll:.5f}{marker}")
    print(f"Selected xhr_weight = {best_xhr_weight} (validation only)")

    # Prepare holdout data
    y = (holdout["outcome"] == "home_run").astype(float).values

    # Calculate barrel rate for holdout set (leakage-safe)
    is_barrel_holdout = (holdout["launch_speed_angle"] == 6).astype(float)
    # Ball in play: not a walk, strikeout, or hit by pitch
    is_bip_holdout = (~holdout["outcome"].isin(["walk", "strikeout", "hit_by_pitch", "intentional_walk"])).astype(float)
    barrel_sum_holdout = is_barrel_holdout.rolling(window=500, min_periods=1).sum().shift(1)
    bip_sum_holdout = is_bip_holdout.rolling(window=500, min_periods=1).sum().shift(1)
    barrel_rate_holdout = (barrel_sum_holdout / bip_sum_holdout).fillna(0.08)  # league average

    p_model = log5_with_xhr(
        holdout["bat_home_run_rate"].values,
        holdout["pit_home_run_rate"].values,
        holdout["league_hr"].values,
        barrel_rate_holdout.values,
        holdout["league_hr"].values,  # Using league_hr as proxy for league_hr_per_barrel
        damp=best_damp,
        xhr_weight=best_xhr_weight)
    p_baseline = holdout["league_hr"].values

    model_ll = log_loss(y, p_model)
    base_ll = log_loss(y, p_baseline)

    print(f"\nHR-per-PA log-loss — model: {model_ll:.5f}   baseline (league rate): {base_ll:.5f}")
    if model_ll < base_ll:
        print(f"MODEL BEATS BASELINE by {base_ll - model_ll:.5f} — Phase A gate PASSED.")
    else:
        print("WARNING: model does not beat the league-rate baseline — "
              "Phase A gate FAILED; do not build the simulation on this.")

    print("\nCalibration (holdout): predicted HR prob bin -> observed HR rate")
    bins = pd.cut(p_model, [0, .01, .02, .03, .04, .05, .07, .10, 1.0])
    table = pd.DataFrame({"bin": bins, "pred": p_model, "actual": y}).groupby(
        "bin", observed=True).agg(PAs=("actual", "size"),
                                  predicted=("pred", "mean"),
                                  observed=("actual", "mean"))
    print(table.to_string(float_format=lambda v: f"{v:.4f}"))

    print("\n(Repeat for hits: any-hit probability model vs baseline)")
    hit_cats = ["home_run", "single", "double", "triple"]
    y_hit = holdout["outcome"].isin(hit_cats).astype(float).values
    bat_hit = sum(holdout[f"bat_{c}_rate"].values for c in hit_cats)
    pit_hit = sum(holdout[f"pit_{c}_rate"].values for c in hit_cats)
    is_hit_all = pa["outcome"].isin(hit_cats).astype(float)
    league_hit = is_hit_all.expanding().mean().shift(1).fillna(is_hit_all.mean())
    p_hit = log5(bat_hit, pit_hit, league_hit[holdout.index].values)
    print(f"Hit-per-PA log-loss — model: {log_loss(y_hit, p_hit):.5f}   "
          f"baseline: {log_loss(y_hit, league_hit[holdout.index].values):.5f}")