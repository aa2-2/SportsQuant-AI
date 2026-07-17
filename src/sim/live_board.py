"""
The per-batter HR board for the daily cards — Phase A+B math applied
to today's confirmed lineups, upgraded with the ingredients that
matter: platoon splits (batter vs tonight's starter's hand, starter
vs each batter's hand), the park HR factor, and a weather multiplier
fitted on this project's own games.

Display-only. The underlying layers passed their holdout gates
(check_pa_model.py, check_game_hr.py); the platoon and weather
adjustments use the same shrunk-rates machinery those gates validated.
Fair odds are the American odds implied by the calibrated P(>=1 HR) —
the number to compare against a sportsbook prop the day a props feed
exists. No book comparison is shown until then, because inventing one
would be decoration.
"""
import joblib
import numpy as np

from config import DATA_DIR
from sim.batter_rates import log5
from sim.game_hr import batter_game_hr_distribution

SIM_RATES_PATH = DATA_DIR / "sim_rates.joblib"


def load_sim_rates():
    if not SIM_RATES_PATH.exists():
        return None
    return joblib.load(SIM_RATES_PATH)


def prob_to_american(p):
    """Fair American odds implied by a probability."""
    p = min(max(float(p), 1e-4), 0.9999)
    if p >= 0.5:
        return -round(100 * p / (1 - p))
    return round(100 * (1 - p) / p)


def take_threshold(fair_odds):
    """
    The recommendation rule (owner's spec): a book price is worth
    taking only if it's AT LEAST the model's fair odds — fair +243
    means take +250 and better, never +230. Rounded UP to the next 10
    so the threshold is always at-or-better than fair, never worse.
    If calibration holds (the gates say it does), any price clearing
    this line is positive expected value by construction.
    """
    import math
    fair = int(fair_odds)
    if fair >= 100:
        return int(math.ceil(fair / 10.0) * 10)
    return fair


def board_total_hrs(*boards):
    """Sum of expected HRs across boards -> the game's Proj HRs."""
    return float(sum(r["e_hrs"] for board in boards for r in (board or [])))


def weather_hr_multiplier(temp, signed_wind, weather_hr):
    """
    Multiplier on HR probability from conditions, from the own-data
    fit (game HRs ~ temp + signed wind), clipped to a sane band —
    our data does not support +24% style boosts, so we can't show them.
    """
    if temp is None or weather_hr is None:
        return 1.0
    delta = (weather_hr["temp_coef"] * (float(temp) - weather_hr["mean_temp"])
             + weather_hr["wind_coef"] * float(signed_wind or 0.0))
    return float(np.clip(1.0 + delta / weather_hr["mean_hrs"], 0.75, 1.30))


def _rates_for(entity_entry, vs_hand, league):
    if not entity_entry:
        return {}
    if vs_hand and f"vs_{vs_hand}" in entity_entry:
        return entity_entry[f"vs_{vs_hand}"]
    return entity_entry.get("overall", entity_entry if isinstance(entity_entry, dict) else {})


def hr_board_for_lineup(lineup_players, opposing_starter_id, rates,
                        park_hr=1.0, weather=None):
    """
    One row per lineup batter: expected HRs, P(>=1), P(>=2), fair odds.
    weather = (temp, signed_wind) or None.
    """
    if not lineup_players:
        return []
    league = rates["league"]
    hands = rates.get("hands", {})
    starter_hand = hands.get("pitcher", {}).get(opposing_starter_id)
    starter_entry = rates["pitcher_rates"].get(opposing_starter_id, {})
    damp, share = rates["damp"], rates["starter_share"]
    wx_mult = weather_hr_multiplier(weather[0] if weather else None,
                                    weather[1] if weather else None,
                                    rates.get("weather_hr"))
    adj = park_hr * wx_mult

    rows = []
    for slot, player in enumerate(lineup_players[:9], start=1):
        pid = player.get("id")
        bat_hand = hands.get("batter", {}).get(pid)
        bat = _rates_for(rates["batter_rates"].get(pid, {}), starter_hand, league)
        pit = _rates_for(starter_entry, bat_hand, league)
        b_hr = bat.get("home_run", league["home_run"])
        s_hr = pit.get("home_run", league["home_run"])
        p_star = float(log5(b_hr, s_hr, league["home_run"], damp=damp)) * adj
        p_pen = float(log5(b_hr, league["home_run"], league["home_run"], damp=damp)) * adj
        e_hrs, p1, p2 = batter_game_hr_distribution(
            min(p_star, 0.5), min(p_pen, 0.5), slot, rates["slot_dist"], share)
        rows.append({
            "name": player.get("name") or f"#{pid}",
            "slot": slot,
            "e_hrs": e_hrs,
            "p_hr": p1,
            "p_2hr": p2,
            "fair_odds": prob_to_american(p1),
            "take_odds": take_threshold(prob_to_american(p1)),
        })
    return rows
