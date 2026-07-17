"""
Phase C: the Monte Carlo game engine.

Simulates a game plate-appearance by plate-appearance: each batter's
PA samples one of seven outcomes from his log5-adjusted probabilities,
runners advance by explicit base-running rules, three outs retire the
side, nine innings (plus extras on ties) make a game. Repeat a few
thousand times and the run DISTRIBUTION falls out — mean totals,
P(over any line), win probability, HR distributions, all from one
engine.

Base-advancement rules (deliberately simple, documented, and judged
by the Phase C gate rather than by opinion):
  single: batter->1B; runners on 2B and 3B score; runner on 1B -> 2B
  double: batter->2B; runners on 2B/3B score; runner on 1B -> 3B
  triple: batter->3B; all runners score
  home run: everyone scores
  walk:   forced runners advance one base
  strikeout / out: no advancement, one out
No steals, errors, or double plays — omissions that roughly offset,
and the gate's calibration verdict is what decides if "roughly" is
good enough.
"""
import numpy as np

from sim.batter_rates import CATEGORIES

IDX = {cat: i for i, cat in enumerate(CATEGORIES)}
MAX_RUNS_PER_HALF = 20  # safety valve for degenerate probability sets


def simulate_half_inning(probs, batter_idx, rng, aggr=0.0, _cum=None):
    """
    One half inning. `probs` is (9, 7): per-lineup-slot category
    probabilities. Returns (runs, next_batter_idx).

    `aggr` is base-running aggressiveness: the probability that the
    runner on 1B takes the extra base (1B->3B on a single, 1B scores
    on a double). Fitted by the gate on the TRAINING era so the sim's
    league-average scoring matches reality — never fitted on holdout.
    """
    outs, runs = 0, 0
    first = second = third = False
    cum = _cum if _cum is not None else np.cumsum(probs, axis=1)

    while outs < 3 and runs < MAX_RUNS_PER_HALF:
        u = rng.random()
        outcome = CATEGORIES[int(np.searchsorted(cum[batter_idx % 9], u))]
        batter_idx += 1

        if outcome in ("strikeout", "out"):
            outs += 1
        elif outcome == "walk":
            if first and second and third:
                runs += 1
            elif first and second:
                third = True
            elif first:
                second = True
            first = True
        elif outcome == "single":
            runs += int(second) + int(third)
            second, third = False, False
            if first:
                if rng.random() < aggr:
                    third = True
                else:
                    second = True
            first = True
        elif outcome == "double":
            runs += int(second) + int(third)
            if first and rng.random() < aggr:
                runs += 1
                third = False
            else:
                third = first
            first, second = False, True
        elif outcome == "triple":
            runs += int(first) + int(second) + int(third)
            first, second, third = False, False, True
        elif outcome == "home_run":
            runs += 1 + int(first) + int(second) + int(third)
            first = second = third = False

    return runs, batter_idx


def simulate_game(away_probs, home_probs, rng, max_innings=12, aggr=0.0,
                  _away_cum=None, _home_cum=None):
    """
    One full game. Returns (away_runs, home_runs). Home team skips the
    bottom of the 9th when already ahead; ties play extras (capped, a
    coin flip breaks a still-tied cap — rare and noted).
    """
    away_runs = home_runs = 0
    away_idx = home_idx = 0

    away_cum = _away_cum if _away_cum is not None else np.cumsum(away_probs, axis=1)
    home_cum = _home_cum if _home_cum is not None else np.cumsum(home_probs, axis=1)
    for inning in range(1, max_innings + 1):
        r, away_idx = simulate_half_inning(away_probs, away_idx, rng, aggr, away_cum)
        away_runs += r
        if inning == 9 and home_runs > away_runs:
            break
        r, home_idx = simulate_half_inning(home_probs, home_idx, rng, aggr, home_cum)
        home_runs += r
        if inning >= 9 and home_runs != away_runs:
            break

    if home_runs == away_runs:  # cap reached: coin flip, keeps totals honest
        if rng.random() < 0.52:
            home_runs += 1
        else:
            away_runs += 1
    return away_runs, home_runs


def simulate_matchup(away_probs, home_probs, n_sims=2000, seed=0, aggr=0.0):
    """
    Full distribution for one matchup. Returns dict with mean total,
    win prob, and the raw totals array for any P(over line) query.
    """
    rng = np.random.default_rng(seed)
    away_cum = np.cumsum(away_probs, axis=1)
    home_cum = np.cumsum(home_probs, axis=1)
    totals = np.empty(n_sims)
    home_wins = 0
    for i in range(n_sims):
        a, h = simulate_game(away_probs, home_probs, rng, aggr=aggr,
                             _away_cum=away_cum, _home_cum=home_cum)
        totals[i] = a + h
        home_wins += h > a
    return {
        "mean_total": float(totals.mean()),
        "home_win_prob": home_wins / n_sims,
        "totals": totals,
    }


def build_lineup_probs(per_pa_probs):
    """
    (9, 7) probability matrix from a list of 9 dicts
    {category: prob}; each row renormalized to sum to 1.
    """
    mat = np.zeros((9, 7))
    for i, probs in enumerate(per_pa_probs):
        for cat, p in probs.items():
            mat[i, IDX[cat]] = p
        mat[i] /= mat[i].sum()
    return mat
