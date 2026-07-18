"""
TRAIN/SERVE EQUALITY TESTS — the guard this week earned three times over.

Every bug that reached the site this week was the same species: the
live pipeline quietly disagreeing with the training pipeline
(placeholder bias, all-9-batters lineup power vs training's top-4,
patches referencing remembered rather than actual code). This file
makes that class of disagreement a test failure instead of a bad bet.

Run from the project root (pip install pytest first if needed):

    python -m pytest src/tests/test_train_serve_equality.py -v

Tier 1 always runs (synthetic data, answers known by construction).
Tier 2 runs when data/ exists: live-pipeline values vs the training
CSV's own stored rows on the final training date.
"""
import inspect
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import DATA_DIR, FEATURE_COLUMNS  # noqa: E402
import live_features as lf  # noqa: E402
from features import batter_power as bp  # noqa: E402


# ---------------- Tier 1: contracts ----------------

def test_feature_row_matches_training_columns_exactly():
    """Serve row must have training's columns, in training's order, no NaN."""
    stats = pd.DataFrame({
        "elo": [1520.0, 1480.0], "avg_exit_velo": [89.1, 88.4],
        "hr_rate": [0.034, 0.028], "k_rate": [0.22, 0.24],
        "bullpen_fatigue": [0.1, 0.3],
    }, index=["Boston Red Sox", "Tampa Bay Rays"])
    feats = pd.DataFrame({"home_team": ["Boston Red Sox"],
                          "date": ["2026-06-01"], "hr_park_factor": [1.08]})
    row = lf.build_feature_row("Boston Red Sox", "Tampa Bay Rays",
                               latest_stats=stats, starts=pd.DataFrame(),
                               features_df=feats)
    assert list(row.columns) == FEATURE_COLUMNS
    assert not row.isna().any().any(), "serve row contains NaN — model input corrupted"


def test_serve_lineup_power_uses_top4_of_last10():
    """
    THE definition that broke on 7/16: top 4 batters by 10-game mean
    exit velo, averaged. Nine batters at velocities 80..88 -> top-4
    mean 86.5. A result of 84.0 is the exact all-9 historical bug.
    """
    rows = []
    for j in range(9):  # 12 games each; only last 10 must count
        for g in range(12):
            rows.append({"batter": j, "avg_exit_velo": 70.0 if g < 2 else 80.0 + j,
                         "home_runs": 1 if (j >= 5 and g >= 2) else 0})
    batter_stats = pd.DataFrame(rows)
    velo, hr = lf.get_lineup_power([{"id": j} for j in range(9)], batter_stats)
    assert velo == pytest.approx(86.5), \
        f"lineup power wrong batter set (got {velo}; all-9 bug gives ~82)"
    assert hr == pytest.approx(1.0), "top-4 hr aggregation drifted"


def test_serve_lineup_power_default_matches_training_default():
    """Unknown batter must get training's neutral defaults (88.0 / 0.03)."""
    velo, hr = lf.get_lineup_power([{"id": 999}],
                                   pd.DataFrame({"batter": [], "avg_exit_velo": [],
                                                 "home_runs": []}))
    assert velo == pytest.approx(88.0) and hr == pytest.approx(0.03)


def test_shared_constants_have_not_drifted():
    """
    Training and serving must agree on window and top_n. Either side
    changing a default silently is exactly how the 7/16 bug was born.
    """
    train_sig = inspect.signature(bp.add_batter_power).parameters
    serve_sig = inspect.signature(lf.get_lineup_power).parameters
    assert train_sig["window"].default == serve_sig["last_n"].default == 10
    assert train_sig["top_n"].default == serve_sig["top_n"].default == 4
    train_src = inspect.getsource(bp.add_batter_power)
    assert "88.0" in train_src and "0.03" in train_src, \
        "training neutral defaults moved — update serve side and this test"


def test_placeholders_are_neutral_after_calibration():
    """Placeholder-bias bug (7/15): defaults must sit at training means."""
    rng = np.random.default_rng(0)
    feats = pd.DataFrame({
        "home_team_top_power_exit_velo": rng.normal(86.5, 1.0, 400),
        "away_team_top_power_exit_velo": rng.normal(86.5, 1.0, 400),
        "home_team_top_power_hr_rate": rng.normal(0.04, 0.01, 400),
        "away_team_top_power_hr_rate": rng.normal(0.04, 0.01, 400),
        "home_team_vs_away_pitcher_avg": rng.normal(0.25, 0.03, 400),
        "away_team_vs_home_pitcher_avg": rng.normal(0.25, 0.03, 400),
        "home_pitcher_whiff_rate": rng.normal(0.11, 0.02, 400),
        "away_pitcher_whiff_rate": rng.normal(0.11, 0.02, 400),
        "temp": rng.normal(74, 8, 400),
        "signed_wind": rng.normal(0.5, 4, 400),
    })
    lf.calibrate_placeholders(feats)
    assert abs(lf.PLACEHOLDER_TOP_POWER_EXIT_VELO - 86.5) < 0.3
    assert abs(lf.PLACEHOLDER_MATCHUP_AVG - 0.25) < 0.02
    assert abs(lf.PLACEHOLDER_TEMP - 74) < 2.0


def test_calibration_is_wired_into_live_context():
    """
    July 17's bug: calibrate_placeholders existed, passed its test, and
    was CALLED BY NOTHING — so production ran on hardcoded 91.0-style
    defaults (3.5 sigma off the real mean) whenever data was missing.
    A fix without a call site is not a fix. This pins the wiring.
    """
    source = inspect.getsource(lf.load_prediction_context)
    assert "calibrate_placeholders(" in source, \
        "load_prediction_context no longer calibrates placeholders — rewire it"


def test_bet_policy_rejects_without_lineups_and_fails_closed():
    """
    July 17: eleven bets logged from a lineups-absent afternoon run —
    placeholder-driven edges cleared every gate because no gate asked
    about lineups. Now one does, and OMITTING the argument = rejection.
    """
    from bet_policy import evaluate_bet
    perfect = dict(edge=0.05, side_model_prob=0.55, side_odds=120,
                   home_pitcher_known=True, away_pitcher_known=True,
                   game_started=False)
    ok, reasons = evaluate_bet(**perfect, lineups_posted=True)
    assert ok and not reasons
    ok, reasons = evaluate_bet(**perfect, lineups_posted=False)
    assert not ok and any("lineups not posted" in r for r in reasons)
    ok, reasons = evaluate_bet(**perfect)  # fail-closed: forgetting = no bet
    assert not ok


# ---------------- Tier 2: real-data equality ----------------

FEATURES_CSV = DATA_DIR / "games_with_features_all_seasons.csv"


@pytest.mark.skipif(not FEATURES_CSV.exists(), reason="training data not present")
def test_live_values_match_training_rows_on_final_date():
    """
    For games on the LAST training date, the live context's team stats
    and park factor must equal what training stored — same data, same
    date, so any gap is train/serve skew by definition.
    """
    feats = pd.read_csv(FEATURES_CSV, parse_dates=["date"])
    last_day = feats[feats["date"] == feats["date"].max()]
    latest = lf.get_latest_team_stats(feats)
    checked = 0
    for _, g in last_day.head(5).iterrows():
        if g["home_team"] not in latest.index:
            continue
        assert lf.get_hr_park_factor(feats, g["home_team"]) == pytest.approx(
            g["hr_park_factor"], rel=1e-6), f"park factor skew: {g['home_team']}"
        for col, stat in [("home_team_elo", "elo"),
                          ("home_team_hr_rate", "hr_rate"),
                          ("home_team_k_rate", "k_rate")]:
            if col in g.index and pd.notna(g[col]) and stat in latest.columns:
                assert latest.loc[g["home_team"], stat] == pytest.approx(
                    g[col], rel=0.02), f"{col} skew for {g['home_team']}"
        checked += 1
    assert checked > 0, "no comparable games found on final training date"
