"""
Precomputes CURRENT per-PA rates for every batter and pitcher — the
live counterpart of Phase A. Run daily (fast) before calculate_edge:

    python src/sim/build_current_rates.py

Saves data/sim_rates.joblib: shrunk per-category rates as of right
now, league rates, slot PA distributions, and starter share — enough
for the daily cards to show the per-batter HR board (Phase A+B math,
both gate-PASSED on 2026 holdout: PA log-loss beat baseline, game
P(>=1 HR) calibrated, total HRs within 1%).
"""
import sys
from pathlib import Path

import joblib
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DATA_DIR  # noqa: E402
from sim.batter_rates import CATEGORIES, build_pa_table  # noqa: E402
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


if __name__ == "__main__":
    frames = []
    cols = ["game_pk", "game_date", "batter", "pitcher", "events",
            "inning_topbot", "home_team", "away_team", "at_bat_number",
            "stand", "p_throws"]
    for year in SEASONS:
        print(f"Loading statcast_{year}.csv...")
        frames.append(pd.read_csv(DATA_DIR / f"statcast_{year}.csv", usecols=cols))
    pa = build_pa_table(pd.concat(frames, ignore_index=True),
                        keep_cols=("inning_topbot", "home_team", "away_team",
                                   "at_bat_number", "stand", "p_throws"))
    print(f"Plate appearances: {len(pa):,}")

    print("Computing current batter rates (with platoon splits)...")
    batter_rates, league = current_rates(pa, "batter", split_col="p_throws")
    print("Computing current pitcher-allowed rates (with platoon splits)...")
    pitcher_rates, _ = current_rates(pa, "pitcher", split_col="stand")

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
    import numpy as np
    feats = pd.read_csv(DATA_DIR / "games_with_features_all_seasons.csv",
                        usecols=["game_pk", "temp", "signed_wind"])
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
        "weather_hr": weather_hr,
        "league": league,
        "slot_dist": slot_pa_distribution(pa),
        "starter_share": starter_share(pa),
        "damp": 0.8,
        "asof": str(pa["game_date"].max().date()),
    }
    joblib.dump(bundle, DATA_DIR / "sim_rates.joblib")
    print(f"\n{len(batter_rates):,} batters, {len(pitcher_rates):,} pitchers, "
          f"data through {bundle['asof']}")
    print(f"Saved to {DATA_DIR / 'sim_rates.joblib'}")
