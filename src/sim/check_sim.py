"""
THE PHASE C GATE: does the bottom-up simulation predict game totals
better than "always guess the league average"?

The regression approach failed this baseline twice (MAE 3.542, 3.555
vs 3.537). This is the simulation's turn — plus the thing no
regression could offer: a full distribution, so P(over 8.5) gets a
calibration table of its own.

Base-running aggressiveness is fitted on the TRAINING era (matching
simulated league scoring to actual training-era scoring), then the
holdout is touched exactly once.

    python src/sim/check_sim.py            (300 sims/game, ~5-10 min)
    python src/sim/check_sim.py --sims 800 (tighter, slower)
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DATA_DIR  # noqa: E402
from sim.batter_rates import CATEGORIES, add_rolling_rates, build_pa_table, log5  # noqa: E402
from sim.engine import build_lineup_probs, simulate_matchup  # noqa: E402
from sim.game_hr import add_batter_teams, add_lineup_slots, add_team_starters, starter_share  # noqa: E402

CUTOFF = "2026-03-25"
SEASONS = [2024, 2025, 2026]
DAMP = 0.8


def lineup_probs_for(bg_rows, starter_rates, league, share, park_hr=1.0):
    """
    Per-slot PA outcome dicts for one team-game -> (9,7) matrix.
    park_hr multiplies each batter's HR probability (the park factor
    is precomputed leakage-safe in the features CSV); the adjustment
    is absorbed by the 'out' bucket, then rows renormalize.
    """
    per_slot = {}
    for _, r in bg_rows.iterrows():
        probs = {}
        for cat in CATEGORIES:
            b = r[f"bat_{cat}_rate"]
            s = starter_rates.get(cat, league[cat])
            p_star = float(log5(b, s, league[cat], damp=DAMP))
            p_pen = float(log5(b, league[cat], league[cat], damp=DAMP))
            probs[cat] = share * p_star + (1 - share) * p_pen
        hr_adj = probs["home_run"] * (park_hr - 1.0)
        probs["home_run"] += hr_adj
        probs["out"] = max(probs["out"] - hr_adj, 0.01)
        per_slot[int(r["slot"])] = probs
    league_row = {c: league[c] for c in CATEGORIES}
    return build_lineup_probs([per_slot.get(s, league_row) for s in range(1, 10)])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sims", type=int, default=500)
    ap.add_argument("--limit", type=int, default=0, help="cap holdout games (0=all)")
    args = ap.parse_args()

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
    print("Rolling pitcher rates...")
    pa = add_rolling_rates(pa, "pitcher", prefix="pit")

    pa = add_batter_teams(pa)
    pa = add_lineup_slots(pa)
    pa = add_team_starters(pa)

    train = pa[pa["game_date"] < CUTOFF]
    share = starter_share(train)
    league = {c: float((train["outcome"] == c).mean()) for c in CATEGORIES}
    print(f"Starter share {share:.1%}; league HR/PA {league['home_run']:.4f}")

    # Actual totals per game (runs scored = from events is unknowable here;
    # use the features CSV, which has final scores)
    games = pd.read_csv(DATA_DIR / "games_with_features_all_seasons.csv",
                        usecols=["game_pk", "date", "home_score", "away_score", "hr_park_factor"])
    games["total"] = games["home_score"] + games["away_score"]
    games["date"] = pd.to_datetime(games["date"])

    train_totals = games[games["date"] < CUTOFF]["total"]
    train_mean = float(train_totals.mean())

    # Fit base-running aggressiveness on TRAIN: match league-average sim to train mean
    league_mat = build_lineup_probs([league] * 9)
    print(f"\nFitting base-running aggressiveness on training era (actual mean {train_mean:.2f}):")
    results = {}
    for aggr in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
        m = simulate_matchup(league_mat, league_mat, n_sims=3000, seed=42, aggr=aggr)["mean_total"]
        results[aggr] = m
        print(f"  aggr {aggr:.2f}: simulated mean {m:.2f}")
    best_aggr = min(results, key=lambda a: abs(results[a] - train_mean))
    print(f"Selected aggr = {best_aggr} (closest to {train_mean:.2f}; training era only)")

    # Holdout: build lineups from pregame rates, simulate, score
    holdout_games = games[games["date"] >= CUTOFF]
    if args.limit:
        holdout_games = holdout_games.head(args.limit)
    ho_pa = pa[pa["game_date"] >= CUTOFF]
    first_pa = ho_pa.groupby(["game_pk", "batter"], sort=False).first().reset_index()
    starter_first = (pa.groupby(["game_pk", "pitcher"], sort=False).first()
                     .reset_index()[["game_pk", "pitcher"] + [f"pit_{c}_rate" for c in CATEGORIES]])

    print(f"\nSimulating {len(holdout_games)} holdout games x {args.sims} sims "
          f"(progress every 200)...")
    rows = []
    for i, (_, g) in enumerate(holdout_games.iterrows()):
        gp = g["game_pk"]
        g_pa = first_pa[first_pa["game_pk"] == gp]
        if len(g_pa) < 14:
            continue
        teams = g_pa["bat_team"].unique()
        if len(teams) != 2:
            continue
        # home team abbr = the team batting in Bot innings
        home_abbr = g_pa[g_pa["inning_topbot"] == "Bot"]["bat_team"].iloc[0] \
            if (g_pa["inning_topbot"] == "Bot").any() else teams[0]
        mats = {}
        for team in teams:
            rows_t = g_pa[g_pa["bat_team"] == team].sort_values("slot").drop_duplicates("slot")
            starter_id = rows_t["starter"].iloc[0]
            sr = starter_first[(starter_first["game_pk"] == gp) &
                               (starter_first["pitcher"] == starter_id)]
            starter_rates = ({c: float(sr[f"pit_{c}_rate"].iloc[0]) for c in CATEGORIES}
                             if len(sr) else dict(league))
            mats[team] = lineup_probs_for(rows_t, starter_rates, league, share,
                                          park_hr=float(g.get("hr_park_factor", 1.0) or 1.0))
        away_abbr = [t for t in teams if t != home_abbr][0]
        res = simulate_matchup(mats[away_abbr], mats[home_abbr],
                               n_sims=args.sims, seed=int(gp) % 100000, aggr=best_aggr)
        rows.append({"game_pk": gp, "pred_total": res["mean_total"],
                     "p_over_85": float((res["totals"] > 8.5).mean()),
                     "home_win_prob": res["home_win_prob"],
                     "actual": g["total"], "home_won": g["home_score"] > g["away_score"]})
        if (i + 1) % 200 == 0:
            print(f"  {i + 1} games simulated")

    out = pd.DataFrame(rows)
    print(f"\nScored {len(out)} games")
    sim_mae = float((out["pred_total"] - out["actual"]).abs().mean())
    base_mae = float((out["actual"] - train_mean).abs().mean())
    print(f"\nTOTALS — simulation MAE: {sim_mae:.3f}   baseline (always {train_mean:.2f}): {base_mae:.3f}")
    if sim_mae < base_mae:
        print(f"SIMULATION BEATS BASELINE by {base_mae - sim_mae:.3f} — Phase C gate PASSED.")
    else:
        print("WARNING: simulation does not beat the baseline — Phase C gate FAILED.")

    print("\nP(over 8.5) calibration: predicted bin -> observed over rate")
    bins = pd.cut(out["p_over_85"], [0, .35, .45, .55, .65, 1.0])
    tbl = out.assign(bin=bins, over=(out["actual"] > 8.5).astype(float)).groupby(
        "bin", observed=True).agg(games=("over", "size"),
                                  predicted=("p_over_85", "mean"),
                                  observed=("over", "mean"))
    print(tbl.to_string(float_format=lambda v: f"{v:.3f}"))

    win_brier = float(((out["home_win_prob"] - out["home_won"].astype(float)) ** 2).mean())
    base_brier = float(((out["home_won"].astype(float) - out["home_won"].mean()) ** 2).mean())
    print(f"\nBonus — home win prob Brier: sim {win_brier:.4f} vs constant-rate {base_brier:.4f}")
    out.to_csv(DATA_DIR / "sim_holdout_results.csv", index=False)
    print(f"Per-game results saved to {DATA_DIR / 'sim_holdout_results.csv'}")
