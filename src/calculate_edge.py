"""
Compares the model's win probabilities against sportsbook moneyline
odds, flags games where they meaningfully disagree, and explains WHY
the model leans the way it does.

Usage:
    python src/calculate_edge.py                  # today's games
    python src/calculate_edge.py --date 2026-07-18

Requires data/mlb_odds.csv (run src/fetch_odds.py first).

NOTE: a "VALUE FLAG" means the model and the market disagree — it is a
scorecard for the model, not wagering advice. Whether these flags mean
anything is exactly what the prediction log is accumulating evidence on.
"""
import argparse
from datetime import date

import joblib
import pandas as pd

from config import DATA_DIR
from datetime import datetime

from bet_log import log_flag
from bet_policy import FLAT_STAKE, evaluate_bet, expected_value, kelly_stake
from explain import full_breakdown, load_raw_model, strength_label
from report import build_report
from mlb_api import get_json
from teams import format_game_time
from hr_model import hr_model_trusted, load_hr_model, predict_game_hrs
from sim.live_board import board_total_hrs, hr_board_for_lineup, load_sim_rates
from totals import load_totals_model, predict_total, prob_over, totals_model_trusted
from live_features import (
    build_game_feature_row,
    get_pitcher_id_by_name,
    build_totals_row,
    weather_runs_effect,
    get_upcoming_schedule,
    load_prediction_context,
)

# Minimum model-vs-market gap before a game gets flagged. Below this,
# the disagreement is within noise and not worth calling out.
EDGE_THRESHOLD = 0.03   # MEDIUM flag (must match bet_policy.MIN_EDGE)
HIGH_THRESHOLD = 0.06   # HIGH flag


def american_odds_to_implied_prob(odds):
    if odds < 0:
        return abs(odds) / (abs(odds) + 100)
    return 100 / (odds + 100)


def remove_vig(home_implied, away_implied):
    total = home_implied + away_implied
    return home_implied / total, away_implied / total


def get_best_odds_per_game(odds_df):
    """
    Best available price per GAME. Grouping must include commence_time:
    the odds feed contains today's AND tomorrow's games, and a series
    (or doubleheader) repeats the same matchup — grouping by team names
    alone collapses distinct games into one row with a mixed timestamp,
    which then (correctly) fails the nearest-time match and reports
    "no odds posted" for games whose odds exist.
    """
    keys = ["home_team", "away_team", "commence_time"]

    best_home_odds = odds_df.loc[odds_df.groupby(keys)["home_odds"].idxmax()]
    best_home_odds = best_home_odds[
        keys + ["bookmaker", "home_odds"]
    ].rename(columns={"bookmaker": "best_home_bookmaker"})

    best_away_odds = odds_df.loc[odds_df.groupby(keys)["away_odds"].idxmax()]
    best_away_odds = best_away_odds[keys + ["bookmaker", "away_odds"]].rename(
        columns={"bookmaker": "best_away_bookmaker", "away_odds": "best_away_odds"}
    )
    return best_home_odds.merge(best_away_odds, on=keys)


def get_display_lines(odds_df, home, away):
    """
    Consensus run line and total for the card display: the most common
    line across books, with the best price available at that line.
    Display only — the model covers moneyline; no run-line or totals
    model exists (yet), so no recommendation is attached to these.
    """
    rows = odds_df[(odds_df["home_team"] == home) & (odds_df["away_team"] == away)]
    lines = {"home_spread": None, "home_spread_odds": None,
             "away_spread": None, "away_spread_odds": None,
             "total_points": None, "over_odds": None, "under_odds": None}
    if len(rows) == 0:
        return lines

    spreads = rows.dropna(subset=["home_spread"])
    if len(spreads) > 0:
        line = spreads["home_spread"].mode().iloc[0]
        at_line = spreads[spreads["home_spread"] == line]
        lines["home_spread"] = line
        lines["home_spread_odds"] = at_line["home_spread_odds"].max()
        lines["away_spread"] = -line
        lines["away_spread_odds"] = at_line["away_spread_odds"].max()

    totals = rows.dropna(subset=["total_points"])
    if len(totals) > 0:
        points = totals["total_points"].mode().iloc[0]
        at_points = totals[totals["total_points"] == points]
        lines["total_points"] = points
        lines["over_odds"] = at_points["over_odds"].max()
        lines["under_odds"] = at_points["under_odds"].max()
    return lines


def game_has_started(iso_utc):
    """True if the scheduled first pitch is in the past."""
    if not iso_utc:
        return False
    try:
        from datetime import datetime, timezone
        start = datetime.fromisoformat(str(iso_utc).replace("Z", "+00:00"))
        return datetime.now(timezone.utc) >= start
    except Exception:
        return False


def parse_args():
    parser = argparse.ArgumentParser(
        description="Compare model win probabilities against sportsbook odds."
    )
    parser.add_argument("--date", type=str, default=None,
                        help="Target date in YYYY-MM-DD format. Defaults to today.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    target_date = args.date if args.date else date.today().isoformat()

    scheduled = get_upcoming_schedule(target_date)

    odds_path = DATA_DIR / "mlb_odds.csv"
    odds_age_h = (datetime.now().timestamp() - odds_path.stat().st_mtime) / 3600
    if odds_age_h > 3:
        print(f"WARNING: odds file is {odds_age_h:.1f} hours old — fetch_odds.py "
              "likely failed (check your ODDS_API_KEY). Prices below are STALE; "
              "do not publish flags from this run.")
    odds_df = pd.read_csv(odds_path)
    odds_games = get_best_odds_per_game(odds_df)

    print(f"Scheduled games on {target_date}: {len(scheduled)}")
    print(f"Games with odds available right now: {len(odds_games)}\n")

    # Full context: lineups, matchup history, live weather — the SAME
    # inputs predict_upcoming.py uses, so there is exactly one model
    # probability per game across the whole project.
    ctx = load_prediction_context(DATA_DIR)
    model, scaler = ctx["model"], ctx["scaler"]
    raw_model = load_raw_model()  # for the "why" breakdown
    totals_bundle = load_totals_model()
    totals_trusted = totals_bundle is not None and totals_model_trusted(totals_bundle)
    if totals_bundle is None:
        print("(No totals model found — run train_totals_model.py to enable O/U recommendations.)")
    elif not totals_trusted:
        print("(Totals model FAILED its baseline check at training time "
              f"[CV MAE {totals_bundle['cv_mae']:.3f} vs baseline {totals_bundle['baseline_mae']:.3f}] "
              "— O/U recommendations disabled until a model beats the baseline.)")

    def resolve_player_names(schedule):
        """One batched MLB Stats API lookup for every lineup ID today."""
        rows = (g for _, g in schedule.iterrows()) if hasattr(schedule, "iterrows") else schedule
        ids = sorted({p.get("id") for g in rows
                      for p in (g.get("home_lineup") or []) + (g.get("away_lineup") or [])
                      if p.get("id")})
        names = {}
        for i in range(0, len(ids), 100):
            chunk = ids[i:i + 100]
            try:
                data = get_json("https://statsapi.mlb.com/api/v1/people",
                                params={"personIds": ",".join(map(str, chunk))})
                for person in data.get("people", []):
                    names[person["id"]] = person.get("fullName")
            except Exception as exc:
                print(f"  (name lookup failed for {len(chunk)} ids: {exc})")
        return names

    player_names = resolve_player_names(scheduled)
    if player_names:
        print(f"Resolved {len(player_names)} lineup player names")

    sim_rates = load_sim_rates()
    if sim_rates is None:
        print("(No sim rates found — run sim/build_current_rates.py to enable the per-batter HR board.)")
    else:
        print(f"(Per-batter HR board active — rates through {sim_rates.get('asof', '?')}, "
              "platoon/park/weather adjusted.)")

    hr_bundle = load_hr_model()
    hr_trusted = hr_bundle is not None and hr_model_trusted(hr_bundle)
    if hr_bundle is None:
        print("(No HR model found — run train_hr_model.py to enable HR projections.)")
    elif not hr_trusted:
        print("(HR model FAILED its baseline check "
              f"[CV MAE {hr_bundle['cv_mae']:.4f} vs baseline {hr_bundle['baseline_mae']:.4f}] "
              "— projections disabled until a model beats the baseline.)")

    flagged = []
    cards = []
    no_odds_games = []

    print("MODEL vs MARKET\n" + "=" * 60)

    for _, sched_game in scheduled.iterrows():
        home, away = sched_game["home_team"], sched_game["away_team"]

        odds_match = odds_games[
            (odds_games["home_team"] == home) & (odds_games["away_team"] == away)
        ]

        # Doubleheaders: two scheduled games share team names but the
        # books may have posted odds for only one. Match by closest
        # start time (within 3 hours) so game 2 can't silently borrow
        # game 1's odds.
        if len(odds_match) > 0 and sched_game.get("game_time_utc"):
            sched_time = pd.to_datetime(sched_game["game_time_utc"], utc=True)
            odds_times = pd.to_datetime(odds_match["commence_time"], utc=True)
            gaps = (odds_times - sched_time).abs()
            if gaps.min() <= pd.Timedelta(hours=3):
                odds_match = odds_match.loc[[gaps.idxmin()]]
            else:
                odds_match = odds_match.iloc[0:0]

        print(f"\n{away} @ {home}")

        if len(odds_match) == 0:
            print("  Odds status: NOT YET POSTED by any tracked sportsbook - rerun closer to game time")
            no_odds_games.append({"away_team": away, "home_team": home,
                                  "game_time_utc": sched_game.get("game_time_utc")})
            continue

        game = odds_match.iloc[0]

        try:
            row, weather_source = build_game_feature_row(sched_game, ctx)
        except KeyError:
            print("  Skipped: team not found in historical data (name mismatch?)")
            continue

        model_home_prob = model.predict_proba(scaler.transform(row))[0][1]

        # Weather framed as run environment, not winner: its measured
        # effect on total run scoring (fit on our own historical games),
        # as runs and as a % of the average total.
        w_runs, w_pct, w_label = None, None, None
        if weather_source:
            w_runs, w_pct = weather_runs_effect(
                float(row["temp"].iloc[0]), float(row["signed_wind"].iloc[0]),
                ctx["weather_model"],
            )
            w_label = ("favors hitters" if w_pct > 0.02
                       else "favors pitchers" if w_pct < -0.02 else "neutral")

        home_implied = american_odds_to_implied_prob(game["home_odds"])
        away_implied = american_odds_to_implied_prob(game["best_away_odds"])
        home_fair, away_fair = remove_vig(home_implied, away_implied)

        home_edge = model_home_prob - home_fair
        away_edge = (1 - model_home_prob) - away_fair

        if weather_source and w_pct is not None:
            weather_status = (f"{weather_source} — {w_pct:+.1%} run scoring "
                              f"({w_runs:+.2f} runs, {w_label})")
        else:
            weather_status = "unavailable — neutral"

        print(f"  Best odds: {game['best_home_bookmaker']} {game['home_odds']:+.0f} (home) "
              f"/ {game['best_away_odds']:+.0f} (away)")
        print(f"  Market fair probability: {home} {home_fair:.1%} / {away} {away_fair:.1%}")
        print(f"  Model probability:       {home} {model_home_prob:.1%} / {away} {1 - model_home_prob:.1%}")
        print(f"  Weather input: {weather_status}")

        # Which side does the model like more than the market, and why?
        side, edge = (home, home_edge) if home_edge >= away_edge else (away, away_edge)
        side_is_home = side == home

        breakdown = full_breakdown(raw_model, scaler, row)
        tier = "HIGH" if edge >= HIGH_THRESHOLD else ("MEDIUM" if edge >= EDGE_THRESHOLD else "NONE")

        cards.append({
            "home": home, "away": away,
            "lines": get_display_lines(odds_df, home, away),
            "time_str": format_game_time(sched_game.get("game_time_utc")),
            "venue": sched_game.get("venue", ""),
            "home_odds": game["home_odds"], "away_odds": game["best_away_odds"],
            "home_fair": home_fair, "model_home_prob": model_home_prob,
            "side": side, "side_is_home": side_is_home,
            "side_odds": game["home_odds"] if side_is_home else game["best_away_odds"],
            "side_book": game["best_home_bookmaker"] if side_is_home else game["best_away_bookmaker"],
            "side_model_prob": model_home_prob if side_is_home else 1 - model_home_prob,
            "side_fair_prob": home_fair if side_is_home else away_fair,
            "edge": edge, "tier": tier, "breakdown": breakdown,
            "started": game_has_started(sched_game.get("game_time_utc")),
            "weather_real": weather_source is not None,
            "weather_source": weather_source,
            "weather_runs": w_runs,
            "weather_pct": w_pct,
            "weather_label": w_label,
            "lineups": bool(sched_game["home_lineup"] and sched_game["away_lineup"]),
        })

        card = cards[-1]

        # ---------- TOTALS (O/U) evaluation ----------
        lines_info = card["lines"]
        if totals_bundle is not None and not totals_trusted:
            card["totals_untrusted"] = True
        if totals_trusted and lines_info.get("total_points") is not None \
                and lines_info.get("over_odds") is not None and lines_info.get("under_odds") is not None:
            line = float(lines_info["total_points"])
            t_row = build_totals_row(row, home, away, ctx["latest_stats"], ctx["features_df"])
            model_total = predict_total(totals_bundle, t_row)
            p_over = prob_over(model_total, line, totals_bundle["sigma"])

            over_implied = american_odds_to_implied_prob(lines_info["over_odds"])
            under_implied = american_odds_to_implied_prob(lines_info["under_odds"])
            over_fair, under_fair = remove_vig(over_implied, under_implied)

            over_edge = p_over - over_fair
            under_edge = (1 - p_over) - under_fair
            t_side, t_edge = ("Over", over_edge) if over_edge >= under_edge else ("Under", under_edge)
            t_prob = p_over if t_side == "Over" else 1 - p_over
            t_odds = lines_info["over_odds"] if t_side == "Over" else lines_info["under_odds"]
            t_tier = "HIGH" if t_edge >= HIGH_THRESHOLD else ("MEDIUM" if t_edge >= EDGE_THRESHOLD else "NONE")

            card["totals"] = {
                "model_total": model_total, "line": line, "p_over": p_over,
                "side": t_side, "edge": t_edge, "tier": t_tier,
                "odds": t_odds, "prob": t_prob,
                "fair": over_fair if t_side == "Over" else under_fair,
            }
            print(f"  Totals: model {model_total:.1f} vs line {line:g} "
                  f"(P(over) {p_over:.1%} vs market {over_fair:.1%})")

            if t_tier != "NONE":
                t_ok, t_rejections = evaluate_bet(
                    edge=t_edge, side_model_prob=t_prob, side_odds=t_odds,
                    home_pitcher_known=sched_game["home_pitcher_name"] is not None,
                    away_pitcher_known=sched_game["away_pitcher_name"] is not None,
                    game_started=game_has_started(sched_game.get("game_time_utc")),
                )
                card["totals"]["approved"] = t_ok
                card["totals"]["rejections"] = t_rejections
                print(f"  >>> {t_tier} TOTALS FLAG: {t_side} {line:g} — model {t_edge:+.1%} vs market "
                      f"({t_odds:+.0f})")
                if not t_ok:
                    print("      FLAG SUPPRESSED — not bet:")
                    for reason in t_rejections:
                        print(f"        - {reason}")
                else:
                    t_logged = log_flag({
                        "logged_at": datetime.now().isoformat(timespec="seconds"),
                        "game_date": target_date,
                        "game_pk": sched_game["game_pk"],
                        "matchup": f"{away} @ {home}",
                        "bet_type": "total_over" if t_side == "Over" else "total_under",
                        "line": line,
                        "side": t_side,
                        "side_is_home": False,
                        "model_prob": round(t_prob, 4),
                        "market_fair_prob": round(card["totals"]["fair"], 4),
                        "edge": round(t_edge, 4),
                        "ev_units": round(expected_value(t_prob, t_odds), 4),
                        "odds": t_odds,
                        "bookmaker": "consensus best",
                        "weather_real": weather_source is not None,
                        "confidence": t_tier,
                        "reasons": f"model total {model_total:.1f} vs line {line:g}",
                        "stake_units": FLAT_STAKE,
                        "kelly_stake_units": kelly_stake(t_prob, t_odds),
                    })
                    print("      Logged as 1.0u flat PAPER bet" if t_logged
                          else "      Already in the paper-bet log (not re-logged)")
                    flagged.append((f"{away} @ {home}", f"{t_side} {line:g}", t_edge))

        if tier == "NONE":
            print(f"  Verdict: no value flag (largest gap {edge:+.1%}, threshold {EDGE_THRESHOLD:.0%})")
            continue

        approved, rejections = evaluate_bet(
            edge=edge,
            side_model_prob=card["side_model_prob"],
            side_odds=card["side_odds"],
            home_pitcher_known=sched_game["home_pitcher_name"] is not None,
            away_pitcher_known=sched_game["away_pitcher_name"] is not None,
            game_started=game_has_started(sched_game.get("game_time_utc")),
            lineups_posted=bool(sched_game["home_lineup"]) and bool(sched_game["away_lineup"]),
        )
        if odds_age_h > 3 and approved:
            approved = False
            rejections.append(
                f"odds file {odds_age_h:.1f}h old - a bet at a price that may "
                "no longer exist is not a bet; run fetch_odds.py and re-run"
            )
        card["approved"] = approved
        card["rejections"] = rejections

        if sim_rates is not None:
            park = float(row["hr_park_factor"].iloc[0])
            wx = ((float(row["temp"].iloc[0]), float(row["signed_wind"].iloc[0]))
                  if weather_source else None)
            home_sp_id = get_pitcher_id_by_name(ctx["starts"], sched_game["home_pitcher_name"])
            away_sp_id = get_pitcher_id_by_name(ctx["starts"], sched_game["away_pitcher_name"])
            card["hr_board_home"] = hr_board_for_lineup(
                sched_game["home_lineup"], away_sp_id, sim_rates, park_hr=park, weather=wx)
            card["hr_board_away"] = hr_board_for_lineup(
                sched_game["away_lineup"], home_sp_id, sim_rates, park_hr=park, weather=wx)
            for board in (card["hr_board_home"], card["hr_board_away"]):
                for r in board:
                    r["name"] = player_names.get(r.get("pid"), r["name"])
            board_all = card["hr_board_home"] + card["hr_board_away"]
            if board_all:
                card["proj_hrs"] = board_total_hrs(card["hr_board_home"], card["hr_board_away"])
                top = sorted(board_all, key=lambda r: -r["p_hr"])[:3]
                print(f"  Projected HRs (board sum): {card['proj_hrs']:.1f}")
                print("  HR board (top 3): " + "; ".join(
                    f"{r['name']} {r['p_hr']:.0%} — take {r['take_odds']:+d} or better"
                    for r in top))

        if hr_trusted and "proj_hrs" not in card:
            card["proj_hrs"] = predict_game_hrs(hr_bundle, row)
            print(f"  Projected HRs (game total): {card['proj_hrs']:.1f}")
        elif hr_bundle is not None:
            card["hr_untrusted"] = True

        side_ev = expected_value(card["side_model_prob"], card["side_odds"])
        print(f"  >>> {tier} VALUE FLAG: {side} — model {edge:+.1%} vs market "
              f"({card['side_book']} {card['side_odds']:+.0f})")
        print(f"      Expected value at that price: {side_ev:+.3f}u per 1u staked")
        print(f"      Why the model leans toward {side}:")
        print(f"        - model {card['side_model_prob']:.1%} vs market fair {card['side_fair_prob']:.1%}")
        top_for = [r for r in breakdown if (r["contribution"] > 0) == side_is_home][:4]
        top_against = [r for r in breakdown if (r["contribution"] > 0) != side_is_home][:2]
        for r in top_for:
            print(f"        - {r['readable']}: {r['value']:g} "
                  f"({strength_label(r['contribution'])}, {r['contribution']:+.2f})")
        if top_against:
            print(f"      Working against the flag:")
            for r in top_against:
                print(f"        - {r['readable']}: {r['value']:g} "
                      f"({strength_label(r['contribution'])}, {r['contribution']:+.2f})")

        if not approved:
            print("      FLAG SUPPRESSED — not bet:")
            for reason in rejections:
                print(f"        - {reason}")
            continue

        reasons_text = " | ".join(r["readable"] for r in top_for)
        newly_logged = log_flag({
            "logged_at": datetime.now().isoformat(timespec="seconds"),
            "game_date": target_date,
            "game_pk": sched_game["game_pk"],
            "matchup": f"{away} @ {home}",
            "side": side,
            "side_is_home": side_is_home,
            "model_prob": round(card["side_model_prob"], 4),
            "market_fair_prob": round(card["side_fair_prob"], 4),
            "edge": round(edge, 4),
            "ev_units": round(side_ev, 4),
            "odds": card["side_odds"],
            "bookmaker": card["side_book"],
            "weather_real": weather_source is not None,
            "confidence": tier,
            "reasons": reasons_text,
            "stake_units": FLAT_STAKE,
            "kelly_stake_units": kelly_stake(card["side_model_prob"], card["side_odds"]),
        })
        k_stake = kelly_stake(card["side_model_prob"], card["side_odds"])
        print(f"      Logged as PAPER bet: 1.0u flat (1/4-Kelly would stake {k_stake}u — recorded, not used)"
              if newly_logged else "      Already in the paper-bet log (not re-logged)")
        flagged.append((f"{away} @ {home}", side, edge))

    print("\n" + "=" * 60)
    if flagged:
        print(f"SUMMARY — {len(flagged)} flagged game(s), largest gap first:")
        for matchup, side, edge in sorted(flagged, key=lambda f: -f[2]):
            print(f"  {matchup}: {side} ({edge:+.1%})")
    else:
        print("SUMMARY — no games cleared the value threshold today.")
    if cards or no_odds_games:
        report_path = build_report(target_date, cards, no_odds_games)
        print(f"\nHTML cheat sheet: {report_path}")

    print(f"Flags are auto-logged as simulated 1-unit paper bets in {DATA_DIR / 'bet_log.csv'}.")
    print("Run settle_bets.py after games finish to grade them and see the running record.")
    