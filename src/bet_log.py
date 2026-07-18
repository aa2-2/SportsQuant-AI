"""
Paper-trading bet log.

Every value flag gets recorded here as a SIMULATED 1-unit flat-stake
bet — no real money, ever. The point is to build an honest, automated
track record: the model picks the side and stake, this module logs it,
and settle_bets.py grades it against the real result. Whether the
model's edges are real is decided by this file, not by anyone's
optimism.

Flat 1-unit staking is deliberate (rather than Kelly sizing): Kelly
assumes the model's probabilities are trustworthy, which is exactly
the thing the log exists to test. Sizing up on an unproven model just
amplifies noise.
"""
import pandas as pd

from datetime import datetime, timezone

from config import DATA_DIR

BET_LOG_PATH = DATA_DIR / "bet_log.csv"

LOG_COLUMNS = [
    "logged_at",       # when the flag was recorded
    "game_date",       # date the game is played
    "game_pk",
    "matchup",         # "Away @ Home"
    "bet_type",        # moneyline / total_over / total_under
    "line",            # total points line (blank for moneyline)
    "side",            # team (moneyline) or "Over"/"Under" (totals)
    "side_is_home",
    "model_prob",      # model's win probability for that side
    "market_fair_prob",# vig-removed market probability for that side
    "edge",
    "ev_units",        # expected profit per unit at the actual logged price
    "odds",            # best American odds available for that side
    "bookmaker",
    "stake_units",     # always 1.0 (flat staking — the production stake)
    "kelly_stake_units",  # quarter-Kelly suggestion, recorded for comparison only
    "weather_real",    # was live weather available at log time
    "confidence",      # HIGH / MEDIUM (edge tier at log time)
    "reasons",         # top model drivers, "a | b | c"
    "status",          # pending / won / lost / push / void
    "profit_units",    # flat-stake P&L; blank while pending
    "kelly_profit_units",  # what quarter-Kelly staking would have made/lost
]


def load_bet_log():
    if BET_LOG_PATH.exists():
        return pd.read_csv(BET_LOG_PATH)
    return pd.DataFrame(columns=LOG_COLUMNS)


def save_bet_log(log_df):
    try:
        log_df.to_csv(BET_LOG_PATH, index=False)
    except PermissionError:
        raise SystemExit(
            f"\nCannot write {BET_LOG_PATH} — the file is locked, almost "
            "certainly because it's open in Excel. Close it there and re-run. "
            "(Nothing was lost; pending bets stay pending until a save succeeds.)"
        )


def log_flag(entry):
    """
    Appends one flagged game as a pending paper bet. Returns True if
    logged, False if this (game, side) was already logged — reruns of
    calculate_edge on the same day must not double-log.
    """
    log_df = load_bet_log()

    entry.setdefault("bet_type", "moneyline")
    entry.setdefault("logged_at",
                     datetime.now(timezone.utc).isoformat(timespec="seconds"))
    entry.setdefault("line", "")

    if len(log_df) > 0:
        existing_types = log_df.get("bet_type")
        if existing_types is None:
            existing_types = pd.Series(["moneyline"] * len(log_df))
        existing_types = existing_types.fillna("moneyline")
        duplicate = (
            (log_df["game_pk"] == entry["game_pk"])
            & (existing_types == entry["bet_type"])
        ).any()
    else:
        duplicate = False

    if duplicate:
        return False

    entry = {**entry, "status": "pending", "profit_units": ""}
    log_df = pd.concat([log_df, pd.DataFrame([entry])], ignore_index=True)
    save_bet_log(log_df[LOG_COLUMNS])
    return True


def profit_for_win(american_odds, stake=1.0):
    """Profit (excluding returned stake) on a winning American-odds bet."""
    odds = float(american_odds)
    if odds > 0:
        return stake * odds / 100.0
    return stake * 100.0 / abs(odds)


def summarize(log_df):
    """Prints the running paper-trading record and ROI."""
    settled = log_df[log_df["status"].isin(["won", "lost", "push"])]
    pending = log_df[log_df["status"] == "pending"]

    print("\nPAPER-TRADING RECORD (simulated 1-unit flat stakes, no real money)")
    print("=" * 60)
    if len(settled) == 0:
        print(f"No settled bets yet ({len(pending)} pending).")
        return

    wins = (settled["status"] == "won").sum()
    losses = (settled["status"] == "lost").sum()
    pushes = (settled["status"] == "push").sum()
    profit = pd.to_numeric(settled["profit_units"], errors="coerce").fillna(0).sum()
    staked = pd.to_numeric(settled["stake_units"], errors="coerce").fillna(0).sum()

    print(f"Record: {wins}-{losses}" + (f"-{pushes}" if pushes else ""))
    print(f"Flat 1u staking:  staked {staked:.1f}u, net {profit:+.2f}u"
          + (f", ROI {profit / staked:+.1%}" if staked > 0 else ""))

    kelly_staked = pd.to_numeric(settled.get("kelly_stake_units"), errors="coerce").fillna(0).sum()
    kelly_profit = pd.to_numeric(settled.get("kelly_profit_units"), errors="coerce").fillna(0).sum()
    if kelly_staked > 0:
        print(f"1/4-Kelly (paper): staked {kelly_staked:.1f}u, net {kelly_profit:+.2f}u, "
              f"ROI {kelly_profit / kelly_staked:+.1%}  <- recorded for comparison, not the production stake")

    print(f"Pending: {len(pending)}")

    if "confidence" in settled.columns and settled["confidence"].notna().any():
        for tier in ["HIGH", "MEDIUM"]:
            tier_bets = settled[settled["confidence"] == tier]
            if len(tier_bets) > 0:
                t_profit = pd.to_numeric(tier_bets["profit_units"], errors="coerce").fillna(0).sum()
                t_wins = (tier_bets["status"] == "won").sum()
                print(f"  {tier}: {t_wins}-{len(tier_bets) - t_wins}, net {t_profit:+.2f}u")

    bet_types = settled.get("bet_type")
    if bet_types is not None:
        bet_types = bet_types.fillna("moneyline")
        for market, label in [("moneyline", "Moneyline"), ("total", "Totals (O/U)")]:
            m_bets = settled[bet_types.str.startswith(market)]
            if len(m_bets) > 0:
                m_profit = pd.to_numeric(m_bets["profit_units"], errors="coerce").fillna(0).sum()
                m_wins = (m_bets["status"] == "won").sum()
                m_losses = (m_bets["status"] == "lost").sum()
                print(f"  {label}: {m_wins}-{m_losses}, net {m_profit:+.2f}u")
    if len(settled) < 30:
        print(f"(Only {len(settled)} settled bets — far too few to conclude anything yet.)")
