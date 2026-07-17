"""
THE PHASE B GATE: do per-batter GAME home-run probabilities calibrate?

For every held-out 2026 batter-game, predicts P(at least 1 HR) from
pregame information only — the batter's rolling rate as of his first
PA, the opposing starter's allowed rate, lineup slot PA distribution,
and the measured starter share — then compares log-loss against the
baseline "every batter-game gets the league average P(HR)".

Also validates the multi-HR claim directly: the sum of predicted
P(2+ HR) across all holdout batter-games vs how many 2+ HR games
actually happened.

    python src/sim/check_game_hr.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DATA_DIR  # noqa: E402
from sim.batter_rates import add_rolling_rates, build_pa_table, log5  # noqa: E402
from sim.game_hr import (  # noqa: E402
    add_batter_teams, add_lineup_slots, add_team_starters,
    batter_game_hr_distribution, slot_pa_distribution, starter_share,
)

CUTOFF = "2026-03-25"
SEASONS = [2024, 2025, 2026]
DAMP = 0.8  # re-tune via check_pa_model.py if its validation picks differently


def log_loss(y, p, eps=1e-9):
    p = np.clip(p, eps, 1 - eps)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


if __name__ == "__main__":
    frames = []
    cols = ["game_pk", "game_date", "batter", "pitcher", "events",
            "inning_topbot", "home_team", "away_team", "at_bat_number"]
    for year in SEASONS:
        print(f"Loading statcast_{year}.csv...")
        frames.append(pd.read_csv(DATA_DIR / f"statcast_{year}.csv", usecols=cols))
    pa = build_pa_table(pd.concat(frames, ignore_index=True),
                        keep_cols=("inning_topbot", "home_team", "away_team", "at_bat_number"))
    print(f"Plate appearances: {len(pa):,}")

    print("Rolling batter rates...")
    pa = add_rolling_rates(pa, "batter", prefix="bat")
    print("Rolling pitcher-allowed rates...")
    pa = add_rolling_rates(pa, "pitcher", prefix="pit")
    is_hr = (pa["outcome"] == "home_run").astype(float)
    pa["league_hr"] = is_hr.expanding().mean().shift(1).fillna(is_hr.mean())

    pa = add_batter_teams(pa)
    pa = add_lineup_slots(pa)
    pa = add_team_starters(pa)

    train = pa[pa["game_date"] < CUTOFF]
    slot_dist = slot_pa_distribution(train)
    share = starter_share(train)
    print(f"\nMeasured from training era: starter faces {share:.1%} of PAs")
    print("Slot -> expected PAs: " + ", ".join(
        f"{s}:{sum(n * w for n, w in d.items()):.2f}" for s, d in sorted(slot_dist.items())))

    # One row per holdout batter-game, using PREGAME rates (first PA of the game)
    holdout = pa[pa["game_date"] >= CUTOFF]
    first_pa = holdout.groupby(["game_pk", "batter"], sort=False).first().reset_index()
    game_hrs = (holdout.assign(hr=(holdout["outcome"] == "home_run").astype(int))
                .groupby(["game_pk", "batter"], sort=False)["hr"].sum().reset_index())
    bg = first_pa.merge(game_hrs, on=["game_pk", "batter"])

    # Starter's PREGAME allowed rate: his rate at his own first PA of that game
    starter_first = (pa.groupby(["game_pk", "pitcher"], sort=False)
                     ["pit_home_run_rate"].first().reset_index()
                     .rename(columns={"pitcher": "starter",
                                      "pit_home_run_rate": "starter_hr_rate"}))
    bg = bg.merge(starter_first, on=["game_pk", "starter"], how="left")
    bg["starter_hr_rate"] = bg["starter_hr_rate"].fillna(bg["league_hr"])

    print(f"Holdout batter-games: {len(bg):,}")

    p_star = log5(bg["bat_home_run_rate"].values, bg["starter_hr_rate"].values,
                  bg["league_hr"].values, damp=DAMP)
    p_pen = log5(bg["bat_home_run_rate"].values, bg["league_hr"].values,
                 bg["league_hr"].values, damp=DAMP)

    preds = np.array([
        batter_game_hr_distribution(ps, pp, s, slot_dist, share)
        for ps, pp, s in zip(p_star, p_pen, bg["slot"].values)
    ])
    e_hrs, p_ge1, p_ge2 = preds[:, 0], preds[:, 1], preds[:, 2]
    y1 = (bg["hr"] >= 1).astype(float).values
    y2 = (bg["hr"] >= 2).astype(float).values

    base_rate = float((train.assign(hr=(train["outcome"] == "home_run").astype(int))
                       .groupby(["game_pk", "batter"])["hr"].sum() >= 1).mean())
    model_ll = log_loss(y1, p_ge1)
    base_ll = log_loss(y1, np.full_like(y1, base_rate))
    print(f"\nP(>=1 HR) log-loss — model: {model_ll:.5f}   baseline (league {base_rate:.3f}): {base_ll:.5f}")
    if model_ll < base_ll:
        print(f"MODEL BEATS BASELINE by {base_ll - model_ll:.5f} — Phase B gate PASSED.")
    else:
        print("WARNING: does not beat baseline — Phase B gate FAILED; fix before Phase C.")

    print("\nCalibration: predicted P(>=1 HR) bin -> observed rate")
    bins = pd.cut(p_ge1, [0, .05, .08, .11, .14, .18, .25, 1.0])
    table = pd.DataFrame({"bin": bins, "pred": p_ge1, "actual": y1}).groupby(
        "bin", observed=True).agg(games=("actual", "size"),
                                  predicted=("pred", "mean"),
                                  observed=("actual", "mean"))
    print(table.to_string(float_format=lambda v: f"{v:.4f}"))

    print(f"\nMulti-HR check: predicted 2+ HR games {p_ge2.sum():.1f} "
          f"vs actual {int(y2.sum())} (of {len(bg):,} batter-games)")
    print(f"Expected total HRs {e_hrs.sum():.0f} vs actual {int(bg['hr'].sum())}")
