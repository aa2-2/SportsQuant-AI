"""
Bet selection policy and stake sizing.

A value FLAG (model disagrees with the market) is not automatically a
BET. Every flag must pass all of these gates before it's logged as a
paper bet — each gate exists because of a specific, documented failure
mode, several found in this project's own evaluation work:

  1. MIN_EDGE       — below ~3%, model-vs-market gaps are noise.
  2. Probability band — this project's calibration analysis showed
                      the model is reliable in the ~30-70% range and
                      unreliable outside it (tiny samples, measured
                      overconfidence above 70%; below 30% is the mirror
                      image of the same region). The flagged side does
                      NOT need to be favored — it needs to sit where
                      the model's probabilities are demonstrated to
                      mean something.
  2b. MIN_EV        — a probability edge vs the vig-REMOVED fair line
                      is not profit; the bet pays at the ACTUAL price,
                      vig included. Expected value at the best posted
                      odds (p x payout - (1-p)) must clear a margin,
                      or the "edge" is an accounting illusion.
  3. Pitchers known — pitcher ERA is core model signal; a flag built
                      on league-average placeholder pitching is not
                      the model's real opinion of the game.
  4. Odds band      — beyond roughly -250/+250, "edges" are usually
                      stale lines or longshot payout traps, not
                      information the model actually has.
  5. MAX_EDGE       — an edge that looks too good to be true almost
                      always is: a name mismatch, postponed game, or
                      stale line — a data bug, not market-beating
                      insight. Suppressed, never bet.
  6. Not started    — a bet logged after first pitch is contaminated
                      by hindsight (live weather, early scoring, line
                      moves). The track record only means something if
                      every entry was decided BEFORE the game began.

STAKING: production stakes are FLAT 1 unit. Kelly sizing is computed
and RECORDED for every bet but not used, because Kelly takes the
model's probability as truth — miscalibration makes it overbet
exactly where the model is most wrong. Once the log has enough
settled bets, flat-vs-Kelly performance can be compared with
evidence instead of assumptions.
"""

MIN_EDGE = 0.03
MAX_EDGE = 0.15
MIN_MODEL_PROB = 0.30
MAX_MODEL_PROB = 0.70
MIN_EV = 0.02   # units of profit per unit staked, at the actual price
MIN_ODDS = -250   # heaviest favorite price we'll take
MAX_ODDS = 250    # longest underdog price we'll take

FLAT_STAKE = 1.0
KELLY_FRACTION = 0.25   # quarter-Kelly (recorded only, not staked)
KELLY_CAP = 2.0         # never record a suggested stake above 2 units


def expected_value(prob, american_odds):
    """
    Expected profit in units per 1 unit staked, at the ACTUAL price.
    EV = p * b - (1 - p), where b is profit per unit on a win.
    """
    odds = float(american_odds)
    b = odds / 100.0 if odds > 0 else 100.0 / abs(odds)
    p = float(prob)
    return p * b - (1.0 - p)


def evaluate_bet(edge, side_model_prob, side_odds,
                 home_pitcher_known, away_pitcher_known,
                 game_started=False, lineups_posted=False):
    """
    Applies every gate. Returns (approved, rejection_reasons).
    An empty reasons list means the bet is approved for logging.
    """
    reasons = []

    if edge < MIN_EDGE:
        reasons.append(f"edge {edge:+.1%} below minimum {MIN_EDGE:.0%}")
    if edge > MAX_EDGE:
        reasons.append(
            f"edge {edge:+.1%} exceeds {MAX_EDGE:.0%} sanity cap — "
            "too good to be true usually means a data problem, not value"
        )
    if side_model_prob > MAX_MODEL_PROB:
        reasons.append(
            f"model probability {side_model_prob:.1%} above {MAX_MODEL_PROB:.0%} — "
            "outside the model's demonstrated calibration range"
        )
    if side_model_prob < MIN_MODEL_PROB:
        reasons.append(
            f"model probability {side_model_prob:.1%} below {MIN_MODEL_PROB:.0%} — "
            "the side doesn't need to be favored, but it must sit in the "
            "range where the model's probabilities are validated"
        )
    ev = expected_value(side_model_prob, side_odds)
    if ev < MIN_EV:
        reasons.append(
            f"expected value {ev:+.3f}u per unit at the actual price ({side_odds:+.0f}) "
            f"is below the {MIN_EV:+.2f}u minimum — the edge doesn't survive the vig"
        )
    if not lineups_posted:
        reasons.append(
            "lineups not posted — lineup-dependent features are running on "
            "calibrated placeholders, so this is not the model's full opinion "
            "(the July 17 slate-wide fake-edge event was exactly this). "
            "Defaults to REJECT unless the caller proves lineups exist."
        )
    if not (home_pitcher_known and away_pitcher_known):
        reasons.append(
            "probable pitcher(s) not posted — flag is built on placeholder "
            "pitching, not the model's real read"
        )
    if side_odds < MIN_ODDS:
        reasons.append(f"odds {side_odds:+.0f} heavier than {MIN_ODDS} favorite limit")
    if side_odds > MAX_ODDS:
        reasons.append(f"odds {side_odds:+.0f} longer than +{MAX_ODDS} underdog limit")
    if game_started:
        reasons.append(
            "game already started — logging now would contaminate the "
            "track record with hindsight"
        )

    return len(reasons) == 0, reasons


def kelly_stake(prob, american_odds,
                fraction=KELLY_FRACTION, cap=KELLY_CAP):
    """
    Fractional Kelly stake in units for a given win probability and
    American odds. Recorded for analysis; NOT used as the real stake.

    Full Kelly: f* = (b*p - q) / b, where b is profit per unit staked.
    """
    odds = float(american_odds)
    b = odds / 100.0 if odds > 0 else 100.0 / abs(odds)
    p = float(prob)
    q = 1.0 - p

    full_kelly = (b * p - q) / b
    stake = max(0.0, full_kelly) * fraction
    return round(min(stake, cap), 3)
