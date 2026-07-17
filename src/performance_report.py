"""
Season Results report — the performance side of the paper-trading
system. Generates a self-contained HTML dashboard from bet_log.csv:

  - headline stats: record, P&L, ROI, win rate, pending count
  - cumulative P&L chart (TOTAL plus HIGH / MEDIUM tier lines, and a
    dashed quarter-Kelly reference line)
  - the full bet log as a table, newest first, with running P&L

settle_bets.py regenerates it automatically after every settlement;
it can also be run standalone:

    python src/performance_report.py

Output: data/reports/season_results.html
"""
import pandas as pd

from config import DATA_DIR
from bet_log import load_bet_log
from teams import abbr

OUTPUT_PATH = DATA_DIR / "reports" / "season_results.html"

CSS = """
* { box-sizing:border-box; margin:0; }
body { background:#f4f1ea; color:#1a1a1a; font-family:'Segoe UI',system-ui,sans-serif; padding:32px 16px; }
.wrap { max-width:900px; margin:0 auto; }
.tophead { display:flex; justify-content:space-between; align-items:center; margin-bottom:28px; }
h1 { font-size:30px; font-weight:800; }
.pill { background:#d9ead9; color:#1a7a3a; font-size:12px; font-weight:700; padding:4px 14px; border-radius:999px; letter-spacing:.05em; }
.stats { display:grid; grid-template-columns:repeat(2,1fr); gap:26px 40px; text-align:center; margin-bottom:30px; }
.stat .l { font-size:12px; color:#8a8578; text-transform:uppercase; letter-spacing:.12em; margin-bottom:6px; }
.stat .n { font-size:34px; font-weight:800; font-variant-numeric:tabular-nums; }
.pos { color:#1a9a4a; } .neg { color:#c23b3b; }
.meta { text-align:center; color:#8a8578; font-size:13px; margin-bottom:26px; }
h2 { font-size:16px; font-weight:700; margin:26px 0 10px; }
.chartbox { background:#faf8f3; border:1px solid #e2ddd0; border-radius:12px; padding:16px; }
.legend { display:flex; gap:18px; justify-content:center; font-size:12px; color:#555; margin-top:8px; }
.legend span::before { content:''; display:inline-block; width:18px; height:3px; margin-right:6px; vertical-align:middle; border-radius:2px; }
.leg-total::before { background:#1a1a1a; } .leg-ml::before { background:#2f6fd6; }
.leg-ou::before { background:#d99a22; } .leg-kelly::before { background:#7a5fd0; }
table { width:100%; border-collapse:collapse; font-size:12.5px; background:#faf8f3; border:1px solid #e2ddd0; border-radius:12px; overflow:hidden; }
th { text-align:left; padding:9px 10px; color:#8a8578; font-size:10.5px; text-transform:uppercase; letter-spacing:.08em; border-bottom:1px solid #e2ddd0; }
td { padding:8px 10px; border-bottom:1px solid #eee8db; font-variant-numeric:tabular-nums; }
tr:last-child td { border-bottom:none; }
.tier { font-size:10px; font-weight:800; padding:2px 8px; border-radius:999px; }
.tier.HIGH { background:#d9ead9; color:#1a7a3a; } .tier.MEDIUM { background:#f4e6c4; color:#9a6d10; }
.won { color:#1a9a4a; font-weight:700; } .lost { color:#c23b3b; font-weight:700; } .pendingtxt { color:#8a8578; }
.footer { color:#8a8578; font-size:12px; margin-top:24px; line-height:1.6; }
.empty { text-align:center; color:#8a8578; padding:40px 0; }
"""


def _cumulative_series(df, profit_col="profit_units"):
    """Cumulative P&L over settled bets in chronological order."""
    settled = df[df["status"].isin(["won", "lost", "push"])].copy()
    settled["p"] = pd.to_numeric(settled[profit_col], errors="coerce").fillna(0.0)
    return settled["p"].cumsum().tolist()


def _svg_chart(df, width=820, height=300):
    """Cumulative P&L line chart as inline SVG. No JS, no libraries."""
    settled = df[df["status"].isin(["won", "lost", "push"])].copy()
    if len(settled) == 0:
        return "<div class='empty'>No settled bets yet — the chart appears after the first settlement.</div>"

    settled = settled.reset_index(drop=True)
    n = len(settled)

    series = {"TOTAL": _cumulative_series(settled)}
    bet_types = settled.get("bet_type")
    bet_types = bet_types.fillna("moneyline") if bet_types is not None else pd.Series(["moneyline"] * len(settled))
    p_all = pd.to_numeric(settled["profit_units"], errors="coerce").fillna(0.0)
    series["ML"] = p_all.where(bet_types == "moneyline", 0.0).cumsum().tolist()
    series["OU"] = p_all.where(bet_types.str.startswith("total"), 0.0).cumsum().tolist()
    if "kelly_profit_units" in settled.columns:
        k = pd.to_numeric(settled["kelly_profit_units"], errors="coerce").fillna(0.0)
        series["KELLY"] = k.cumsum().tolist()

    all_vals = [v for vals in series.values() for v in vals] + [0.0]
    lo, hi = min(all_vals), max(all_vals)
    span = (hi - lo) or 1.0
    lo -= span * 0.1
    hi += span * 0.1

    pad_l, pad_r, pad_t, pad_b = 46, 12, 10, 26
    plot_w, plot_h = width - pad_l - pad_r, height - pad_t - pad_b

    def x(i):
        return pad_l + (plot_w * (i / max(n - 1, 1)))

    def y(v):
        return pad_t + plot_h * (1 - (v - lo) / (hi - lo))

    def polyline(vals, color, dash=""):
        pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(vals))
        d = f" stroke-dasharray='5,4'" if dash else ""
        return f"<polyline points='{pts}' fill='none' stroke='{color}' stroke-width='2.4'{d}/>"

    # horizontal gridlines at nice unit steps
    grid = ""
    step = max(round(span / 4) or 1, 1)
    tick = (int(lo // step)) * step
    while tick <= hi:
        gy = y(tick)
        grid += (f"<line x1='{pad_l}' y1='{gy:.1f}' x2='{width - pad_r}' y2='{gy:.1f}' "
                 f"stroke='#e2ddd0' stroke-dasharray='3,4'/>"
                 f"<text x='{pad_l - 8}' y='{gy + 4:.1f}' font-size='11' fill='#8a8578' "
                 f"text-anchor='end'>{tick:g}u</text>")
        tick += step

    # x labels: first, middle, last game date
    labels = ""
    dates = settled["game_date"].astype(str).tolist()
    for i in sorted({0, n // 2, n - 1}):
        labels += (f"<text x='{x(i):.1f}' y='{height - 8}' font-size='11' fill='#8a8578' "
                   f"text-anchor='middle'>{dates[i]}</text>")

    lines = ""
    if "KELLY" in series:
        lines += polyline(series["KELLY"], "#7a5fd0", dash="1")
    lines += polyline(series["OU"], "#d99a22")
    lines += polyline(series["ML"], "#2f6fd6")
    lines += polyline(series["TOTAL"], "#1a1a1a")

    legend = ("<div class='legend'><span class='leg-total'>TOTAL (flat 1u)</span>"
              "<span class='leg-ml'>ML</span><span class='leg-ou'>O/U</span>"
              + ("<span class='leg-kelly'>1/4-Kelly (reference)</span>" if "KELLY" in series else "")
              + "</div>")

    return (f"<svg viewBox='0 0 {width} {height}' width='100%' "
            f"xmlns='http://www.w3.org/2000/svg'>{grid}{lines}</svg>{legend}")


def _pick_label(bet):
    bet_type = str(bet.get("bet_type") or "moneyline")
    if bet_type.startswith("total"):
        line = bet.get("line")
        try:
            return f"{str(bet['side']).upper()} {float(line):g}"
        except (TypeError, ValueError):
            return str(bet["side"]).upper()
    return f"{abbr(str(bet['side']))} ML"


def _log_table(df):
    if len(df) == 0:
        return "<div class='empty'>No bets logged yet.</div>"

    df = df.copy()
    df["p_num"] = pd.to_numeric(df["profit_units"], errors="coerce").fillna(0.0)
    settled_mask = df["status"].isin(["won", "lost", "push"])
    df["running"] = df["p_num"].where(settled_mask, 0.0).cumsum()

    rows = ""
    for _, b in df.iloc[::-1].iterrows():  # newest first
        if b["status"] == "won":
            result = f"<span class='won'>WON {b['p_num']:+.2f}u</span>"
        elif b["status"] == "lost":
            result = f"<span class='lost'>LOST {b['p_num']:+.2f}u</span>"
        elif b["status"] == "push":
            result = "PUSH"
        else:
            result = "<span class='pendingtxt'>pending</span>"

        tier = b.get("confidence") or ""
        tier_html = f"<span class='tier {tier}'>{tier}</span>" if tier in ("HIGH", "MEDIUM") else ""
        running = f"{b['running']:+.2f}u" if b["status"] in ("won", "lost", "push") else "—"

        rows += (f"<tr><td>{b['game_date']}</td>"
                 f"<td>{b['matchup']}</td>"
                 f"<td><b>{_pick_label(b)}</b></td>"
                 f"<td>{tier_html}</td>"
                 f"<td>{float(b['odds']):+.0f}</td>"
                 f"<td>{float(b['model_prob']):.1%}</td>"
                 f"<td>{float(b['market_fair_prob']):.1%}</td>"
                 f"<td>{float(b['edge']):+.1%}</td>"
                 f"<td>{result}</td>"
                 f"<td>{running}</td></tr>")

    return ("<table><tr><th>Date</th><th>Matchup</th><th>Pick</th><th>Tier</th><th>Odds</th>"
            "<th>Model</th><th>Market</th><th>Edge</th><th>Result</th><th>Running</th></tr>"
            + rows + "</table>")


def build_performance_report():
    df = load_bet_log()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    settled = df[df["status"].isin(["won", "lost", "push"])]
    pending = df[df["status"] == "pending"]
    wins = int((settled["status"] == "won").sum())
    losses = int((settled["status"] == "lost").sum())
    pushes = int((settled["status"] == "push").sum())

    profit = pd.to_numeric(settled["profit_units"], errors="coerce").fillna(0).sum()
    staked = pd.to_numeric(settled["stake_units"], errors="coerce").fillna(0).sum()
    roi = profit / staked if staked > 0 else 0.0
    win_rate = wins / max(wins + losses, 1)

    record = f"{wins}-{losses}" + (f"-{pushes}" if pushes else "")
    sign = "pos" if profit >= 0 else "neg"
    small_note = ("" if len(settled) >= 30 else
                  f" · only {len(settled)} settled — far too few to conclude anything yet")

    kelly_line = ""
    if "kelly_profit_units" in df.columns:
        k_profit = pd.to_numeric(settled.get("kelly_profit_units"), errors="coerce").fillna(0).sum()
        k_staked = pd.to_numeric(settled.get("kelly_stake_units"), errors="coerce").fillna(0).sum()
        if k_staked > 0:
            kelly_line = (f" · 1/4-Kelly reference: {k_profit:+.2f}u on {k_staked:.2f}u staked "
                          f"({k_profit / k_staked:+.1%} ROI)")

    from datetime import datetime
    html = f"""<!DOCTYPE html>
<html><head><meta charset='utf-8'><title>SportsQuant-AI — Season Results</title>
<style>{CSS}</style></head><body><div class='wrap'>
<div class='tophead'><h1>Season Results</h1><span class='pill'>PAPER · 2026</span></div>
<div class='stats'>
  <div class='stat'><div class='l'>Record</div><div class='n'>{record}</div></div>
  <div class='stat'><div class='l'>P&amp;L</div><div class='n {sign}'>{profit:+.1f}u</div></div>
  <div class='stat'><div class='l'>ROI</div><div class='n {sign}'>{roi:+.1%}</div></div>
  <div class='stat'><div class='l'>Win Rate</div><div class='n'>{win_rate:.1%}</div></div>
</div>
<div class='meta'>{len(df)} bets logged · {len(pending)} pending{small_note}{kelly_line}
· generated {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
<h2>Cumulative P&amp;L</h2>
<div class='chartbox'>{_svg_chart(df)}</div>
<h2>Bet Log</h2>
{_log_table(df)}
<div class='footer'>All stakes are simulated 1-unit flat paper bets — no real money. The quarter-Kelly
line is recorded for sizing comparison only. Every entry was approved by the six-gate policy in
bet_policy.py before logging; games already started are never logged.</div>
</div></body></html>"""

    OUTPUT_PATH.write_text(html, encoding="utf-8")
    return OUTPUT_PATH


if __name__ == "__main__":
    path = build_performance_report()
    print(f"Season results report: {path}")
