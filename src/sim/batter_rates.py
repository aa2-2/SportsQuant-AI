"""
Phase A of the bottom-up game simulation: per-plate-appearance event
probabilities for every batter and pitcher.

Design principles (same as the rest of MLBQuant):
  - LEAKAGE-SAFE: every rate is computed from strictly earlier plate
    appearances (shift(1) before the rolling window).
  - SHRUNK: small samples get pulled toward the league rate
    (rate = (successes + k * league) / (n + k)), so a 10-PA hot streak
    can't masquerade as true talent. k is the number of league-average
    PAs the prior is worth.
  - COMBINED honestly: batter rate x pitcher-allowed rate via the
    odds-ratio (log5) method against the league rate.

Phase A must pass its gate (sim/check_pa_model.py) before anything is
built on top of it.
"""
import numpy as np
import pandas as pd

# Every PA resolves to exactly one of these
CATEGORIES = ["home_run", "single", "double", "triple", "walk", "strikeout", "out"]

EVENT_MAP = {
    "home_run": "home_run",
    "single": "single",
    "double": "double",
    "triple": "triple",
    "walk": "walk",
    "hit_by_pitch": "walk",          # reaches base without contact: pooled
    "intent_walk": "walk",
    "strikeout": "strikeout",
    "strikeout_double_play": "strikeout",
}


def build_pa_table(statcast_df, keep_cols=()):
    """
    One row per plate appearance: date, batter, pitcher, outcome (plus
    any `keep_cols` present, e.g. teams / at_bat_number for Phase B).
    Anything not in EVENT_MAP (field outs, errors, DPs, sacrifices...)
    is an 'out' for modeling purposes.
    """
    pa = statcast_df[statcast_df["events"].notna()].copy()
    pa["outcome"] = pa["events"].map(EVENT_MAP).fillna("out")
    pa["game_date"] = pd.to_datetime(pa["game_date"])
    sort_keys = ["game_date", "game_pk"]
    if "at_bat_number" in pa.columns:
        sort_keys.append("at_bat_number")
    pa = pa.sort_values(sort_keys, kind="mergesort").reset_index(drop=True)
    cols = ["game_pk", "game_date", "batter", "pitcher", "outcome"]
    cols += [c for c in keep_cols if c in pa.columns and c not in cols]
    return pa[cols]


def add_rolling_rates(pa_df, entity_col, window=500, shrink_pa=200, prefix=None):
    """
    For each entity (batter or pitcher), adds shrunk rolling per-PA
    rates for every category, computed over that entity's previous
    `window` plate appearances (shift(1) — the current PA never sees
    itself). League rates use the expanding league average, also
    shifted.
    """
    prefix = prefix or entity_col
    df = pa_df.copy()

    for cat in CATEGORIES:
        df[f"_is_{cat}"] = (df["outcome"] == cat).astype(float)

    for cat in CATEGORIES:
        league = df[f"_is_{cat}"].expanding().mean().shift(1).fillna(
            df[f"_is_{cat}"].mean())
        grouped = df.groupby(entity_col)[f"_is_{cat}"]
        successes = grouped.transform(
            lambda s: s.shift(1).rolling(window, min_periods=1).sum())
        counts = grouped.transform(
            lambda s: s.shift(1).rolling(window, min_periods=1).count())
        successes = successes.fillna(0.0)
        counts = counts.fillna(0.0)
        df[f"{prefix}_{cat}_rate"] = (
            (successes + shrink_pa * league) / (counts + shrink_pa)
        )

    return df.drop(columns=[f"_is_{cat}" for cat in CATEGORIES])


def league_rates(pa_df):
    """Overall league per-PA rate for each category."""
    return {cat: float((pa_df["outcome"] == cat).mean()) for cat in CATEGORIES}


def log5(p_batter, p_pitcher, p_league, floor=1e-5, ceiling=0.6, damp=1.0):
    """
    Odds-ratio combination of a batter's rate and a pitcher's allowed
    rate relative to league: combined_odds = (b_odds * p_odds) / l_odds.

    `damp` (0..1) blends the result back toward league: 1.0 = raw log5.
    Phase A's holdout calibration showed the top tail was too
    aggressive (predicted 4.4% where 3.7% happened), the classic sign
    of under-shrunk extremes. The damp value is selected on a
    PRE-holdout validation window — never on the holdout itself.
    """
    b = np.clip(p_batter, floor, ceiling)
    p = np.clip(p_pitcher, floor, ceiling)
    l = np.clip(p_league, floor, ceiling)
    odds = (b / (1 - b)) * (p / (1 - p)) / (l / (1 - l))
    raw = odds / (1 + odds)
    return np.clip(damp * raw + (1.0 - damp) * l, floor, ceiling)
