"""
Settles pending paper bets against real game results.

Run any time (e.g. each morning): it finds every pending entry in
data/bet_log.csv, fetches the real final score from the MLB Stats API,
grades the bet, records the simulated profit/loss, and prints the
running record and ROI.

    python src/settle_bets.py
"""
import pandas as pd

from bet_log import load_bet_log, profit_for_win, save_bet_log, summarize
from mlb_api import fetch_schedule


def fetch_final_result(game_pk, game_date):
    """
    Returns (home_score, away_score, was_final) for a game, or
    (None, None, False) if it isn't final yet / was postponed.
    """
    data = fetch_schedule(date=str(game_date))
    for day in data.get("dates", []):
        for game in day["games"]:
            if game["gamePk"] != game_pk:
                continue
            if game["status"]["detailedState"] != "Final":
                return None, None, False
            home = game["teams"]["home"]
            away = game["teams"]["away"]
            return home["score"], away["score"], True
    return None, None, False


if __name__ == "__main__":
    log_df = load_bet_log()

    if len(log_df) == 0:
        print("Bet log is empty — run calculate_edge.py first to log some flags.")
        raise SystemExit

    pending = log_df[log_df["status"] == "pending"]
    print(f"Pending paper bets to check: {len(pending)}")

    settled_now = 0
    for idx, bet in pending.iterrows():
        home_score, away_score, was_final = fetch_final_result(bet["game_pk"], bet["game_date"])

        if not was_final:
            print(f"  {bet['matchup']} ({bet['game_date']}): not final yet")
            continue

        bet_type = str(bet.get("bet_type") or "moneyline")

        if bet_type.startswith("total"):
            total = home_score + away_score
            line = float(bet["line"])
            if total == line:
                log_df.loc[idx, "status"] = "push"
                log_df.loc[idx, "profit_units"] = 0.0
                log_df.loc[idx, "kelly_profit_units"] = 0.0
                print(f"  {bet['matchup']}: {bet['side']} {line:g} -> PUSH (landed exactly {total})")
                settled_now += 1
                continue
            bet_won = total > line if bet_type == "total_over" else total < line
            detail = f"{bet['side']} {line:g} (final total {total})"
        else:
            home_won = home_score > away_score
            bet_won = home_won if bet["side_is_home"] else not home_won
            detail = f"{bet['side']} at {bet['odds']:+.0f}"

        kelly_stake = float(bet.get("kelly_stake_units", 0) or 0)
        if bet_won:
            log_df.loc[idx, "status"] = "won"
            log_df.loc[idx, "profit_units"] = round(profit_for_win(bet["odds"], bet["stake_units"]), 3)
            log_df.loc[idx, "kelly_profit_units"] = round(profit_for_win(bet["odds"], kelly_stake), 3)
        else:
            log_df.loc[idx, "status"] = "lost"
            log_df.loc[idx, "profit_units"] = -float(bet["stake_units"])
            log_df.loc[idx, "kelly_profit_units"] = -kelly_stake

        result = "WON" if bet_won else "lost"
        print(f"  {bet['matchup']}: {detail} -> {result} "
              f"({log_df.loc[idx, 'profit_units']:+.2f} units)")
        settled_now += 1

    if settled_now:
        save_bet_log(log_df)
        print(f"\nSettled {settled_now} bet(s).")

    summarize(load_bet_log())

    from performance_report import build_performance_report
    report_path = build_performance_report()
    print(f"\nSeason results report updated: {report_path}")
