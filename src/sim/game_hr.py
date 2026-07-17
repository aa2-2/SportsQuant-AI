"""
Phase B: from per-PA rates to per-GAME batter HR distributions.

A batter's game is: some number of plate appearances (driven by his
lineup slot — leadoff hits more often than ninth), each PA carrying a
log5-adjusted HR probability (vs the opposing starter for the starter's
share of PAs, vs a league-average arm for the bullpen share). His HR
count is then Binomial across those PAs — which is where P(0), P(1),
and P(2+) all come from with no extra model.

Everything empirical here (slot PA distributions, starter share) is
measured from this project's own data, on the training era only.
"""
import numpy as np
import pandas as pd


def add_batter_teams(pa):
    """Batter's team abbreviation: Bot of inning -> home team."""
    pa = pa.copy()
    pa["bat_team"] = np.where(pa["inning_topbot"] == "Bot",
                              pa["home_team"], pa["away_team"])
    return pa


def add_lineup_slots(pa):
    """
    Lineup slot 1-9 per (game, team) by order of first plate
    appearance. Pinch hitters / substitutes appearing 10th or later
    are capped at slot 9 (they inherit bottom-of-order PA counts).
    """
    pa = pa.sort_values(["game_pk", "at_bat_number"], kind="mergesort").copy()
    first_seen = (pa.groupby(["game_pk", "bat_team", "batter"], sort=False)
                    ["at_bat_number"].transform("min"))
    pa["_first_ab"] = first_seen
    order = (pa[["game_pk", "bat_team", "batter", "_first_ab"]]
             .drop_duplicates(["game_pk", "bat_team", "batter"])
             .sort_values(["game_pk", "bat_team", "_first_ab"]))
    order["slot"] = order.groupby(["game_pk", "bat_team"]).cumcount() + 1
    order["slot"] = order["slot"].clip(upper=9)
    pa = pa.merge(order[["game_pk", "bat_team", "batter", "slot"]],
                  on=["game_pk", "bat_team", "batter"], how="left")
    return pa.drop(columns=["_first_ab"])


def slot_pa_distribution(pa_train):
    """
    {slot: {n_pas: probability}} measured from the training era.
    PA counts clipped to 1..6.
    """
    counts = (pa_train.groupby(["game_pk", "bat_team", "batter", "slot"])
              .size().rename("n").reset_index())
    counts["n"] = counts["n"].clip(1, 6)
    dist = {}
    for slot, grp in counts.groupby("slot"):
        vc = grp["n"].value_counts(normalize=True).sort_index()
        dist[int(slot)] = {int(n): float(p) for n, p in vc.items()}
    return dist


def add_team_starters(pa):
    """
    The opposing starter for each PA's batting team: the pitcher who
    threw that team's FIRST plate appearance of the game.
    """
    pa = pa.sort_values(["game_pk", "at_bat_number"], kind="mergesort").copy()
    starters = (pa.groupby(["game_pk", "bat_team"], sort=False)
                  .agg(starter=("pitcher", "first")).reset_index())
    return pa.merge(starters, on=["game_pk", "bat_team"], how="left")


def starter_share(pa_train):
    """Fraction of a team's PAs faced against the opposing starter."""
    return float((pa_train["pitcher"] == pa_train["starter"]).mean())


def batter_game_hr_distribution(p_vs_starter, p_vs_bullpen, slot, slot_dist, share):
    """
    (expected_hrs, p_at_least_1, p_at_least_2) for one batter-game.
    Per-PA probability blends starter and bullpen matchups by the
    measured starter share; HR count is Binomial over the slot's
    empirical PA-count distribution.
    """
    p = share * p_vs_starter + (1.0 - share) * p_vs_bullpen
    dist = slot_dist.get(int(slot), slot_dist.get(9))
    e_hrs, p0, p1 = 0.0, 0.0, 0.0
    for n, w in dist.items():
        e_hrs += w * n * p
        p0 += w * (1 - p) ** n
        p1 += w * n * p * (1 - p) ** (n - 1)
    return e_hrs, 1.0 - p0, max(0.0, 1.0 - p0 - p1)
