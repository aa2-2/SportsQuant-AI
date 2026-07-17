"""
Generates a self-contained HTML "cheat sheet" report from a day's
edge run — one card per game, styled like commercial betting-analytics
dashboards: odds up front, a recommendation with a confidence tier,
the edge, and bullet reasons backed by the model's actual numbers.

calculate_edge.py calls build_report() automatically; the file lands
in data/reports/edge_report_<date>.html — double-click to open.
"""
from datetime import datetime

from config import DATA_DIR
from teams import abbr

REPORTS_DIR = DATA_DIR / "reports"

CSS = """
:root { color-scheme: dark; }
* { box-sizing: border-box; margin: 0; }
body { background:#0d1117; color:#e6edf3; font-family:'Segoe UI',system-ui,sans-serif; padding:32px 16px; }
.wrap { max-width: 860px; margin: 0 auto; }
h1 { font-size: 22px; margin-bottom: 4px; }
.sub { color:#8b949e; font-size: 13px; margin-bottom: 20px; }
.totals { display:flex; gap:12px; margin-bottom:24px; flex-wrap:wrap; }
.stat { background:#161b22; border:1px solid #30363d; border-radius:10px; padding:12px 18px; }
.stat .n { font-size:20px; font-weight:700; }
.stat .l { font-size:11px; color:#8b949e; text-transform:uppercase; letter-spacing:.05em; }
.card { background:#161b22; border:1px solid #30363d; border-radius:12px; padding:20px; margin-bottom:18px; }
.head { display:flex; justify-content:space-between; align-items:baseline; flex-wrap:wrap; gap:8px; }
.matchup { font-size:18px; font-weight:700; }
.meta { color:#8b949e; font-size:12px; }
.odds { display:flex; gap:10px; margin:14px 0; flex-wrap:wrap; }
.oddbox { background:#0d1117; border:1px solid #30363d; border-radius:8px; padding:8px 14px; font-size:13px; }
.oddbox b { font-size:15px; }
.probbar { height:10px; border-radius:5px; background:#1f6feb33; overflow:hidden; margin:8px 0 4px; }
.probbar div { height:100%; background:#1f6feb; }
.problabel { display:flex; justify-content:space-between; font-size:12px; color:#8b949e; margin-bottom:12px; }
.rec { border-radius:10px; padding:14px 16px; margin-top:6px; }
.rec.high { background:#0f2e1c; border:1px solid #2ea043; }
.rec.medium { background:#2d2308; border:1px solid #d29922; }
.rec.none { background:#21262d; border:1px solid #30363d; color:#8b949e; }
.tier { display:inline-block; font-size:11px; font-weight:700; letter-spacing:.08em; padding:2px 10px; border-radius:999px; margin-right:8px; }
.tier.high { background:#2ea043; color:#04120a; }
.tier.medium { background:#d29922; color:#1c1503; }
.pick { font-size:16px; font-weight:700; }
.edge { float:right; font-weight:700; }
ul.reasons { margin:10px 0 0 0; padding-left:18px; font-size:13px; line-height:1.7; }
.abbrs { font-size:20px; font-weight:800; letter-spacing:.02em; }
.fullnames { color:#8b949e; font-size:12px; margin-top:2px; }
.markets { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin:14px 0; }
.mkt { background:#0d1117; border:1px solid #30363d; border-radius:8px; padding:10px 12px; }
.mkt .t { font-size:10px; color:#8b949e; text-transform:uppercase; letter-spacing:.08em; margin-bottom:6px; }
.mkt .r { display:flex; justify-content:space-between; font-size:13px; padding:1px 0; }
.mkt .r b { font-variant-numeric:tabular-nums; }
.rechead { font-size:11px; color:#8b949e; text-transform:uppercase; letter-spacing:.08em; margin:12px 0 6px; }
.norec { color:#8b949e; font-size:13px; padding:8px 0 0; }
@media (max-width:640px){ .markets { grid-template-columns:1fr; } }
ul.reasons .against { color:#8b949e; }
.dq { margin-top:10px; font-size:12px; color:#8b949e; }
.footer { color:#8b949e; font-size:12px; margin-top:28px; line-height:1.6; }
"""


def _reason_bullet(item, home_team, away_team):
    toward = home_team if item["contribution"] > 0 else away_team
    return (
        f"<li>{item['readable']}: {item['value']:g} — "
        f"{strengthen(item)} push toward {toward}</li>"
    )


def strengthen(item):
    from explain import strength_label
    return strength_label(item["contribution"])


def _fmt_odds(value):
    return f"{value:+.0f}" if value is not None and value == value else "—"


def _fmt_line(value):
    return f"{value:+g}" if value is not None and value == value else "—"


def render_markets(card):
    home_a, away_a = abbr(card["home"]), abbr(card["away"])
    lines = card.get("lines") or {}
    total = lines.get("total_points")
    total_str = f"{total:g}" if total is not None and total == total else "—"
    return f"""
      <div class='markets'>
        <div class='mkt'><div class='t'>Moneyline</div>
          <div class='r'><span>{away_a}</span><b>{_fmt_odds(card['away_odds'])}</b></div>
          <div class='r'><span>{home_a}</span><b>{_fmt_odds(card['home_odds'])}</b></div>
        </div>
        <div class='mkt'><div class='t'>Run Line</div>
          <div class='r'><span>{away_a} {_fmt_line(lines.get('away_spread'))}</span><b>{_fmt_odds(lines.get('away_spread_odds'))}</b></div>
          <div class='r'><span>{home_a} {_fmt_line(lines.get('home_spread'))}</span><b>{_fmt_odds(lines.get('home_spread_odds'))}</b></div>
        </div>
        <div class='mkt'><div class='t'>Total: {total_str}</div>
          <div class='r'><span>Over</span><b>{_fmt_odds(lines.get('over_odds'))}</b></div>
          <div class='r'><span>Under</span><b>{_fmt_odds(lines.get('under_odds'))}</b></div>
        </div>
      </div>"""


def render_totals_rec(card):
    t = card.get("totals")
    if not t:
        if card.get("totals_untrusted"):
            return ("<div class='norec'>— disabled: totals model failed its baseline "
                    "validation (can't out-predict the league-average total), so its "
                    "edges would be noise</div>")
        return "<div class='norec'>— (no totals model trained, or no total posted)</div>"

    bullets = (f"<ul class='reasons'>"
               f"<li>Model {t['model_total']:.1f} vs Market {t['line']:g} "
               f"({t['model_total'] - t['line']:+.1f})</li>"
               f"<li>P({t['side'].lower()}) {t['prob']:.1%} vs market {t['fair']:.1%}</li></ul>")

    if t["tier"] in ("HIGH", "MEDIUM") and not t.get("approved", True):
        items = "".join(f"<li>{r}</li>" for r in t.get("rejections", []))
        return (f"<div class='rec none'><b>Flag suppressed — not bet.</b>"
                f"<ul class='reasons'>{items}</ul></div>")
    if t["tier"] == "HIGH":
        return (f"<div class='rec high'><span class='tier high'>HIGH</span>"
                f"<span class='pick'>{t['side'].upper()} {t['line']:g} ({t['odds']:+.0f})</span>"
                f"<span class='edge'>Edge: {t['edge']:+.1%}</span>{bullets}</div>")
    if t["tier"] == "MEDIUM":
        return (f"<div class='rec medium'><span class='tier medium'>MEDIUM</span>"
                f"<span class='pick'>{t['side'].upper()} {t['line']:g} ({t['odds']:+.0f})</span>"
                f"<span class='edge'>Edge: {t['edge']:+.1%}</span>{bullets}</div>")
    return (f"<div class='norec'>No clear value (model {t['model_total']:.1f} vs {t['line']:g}, "
            f"largest gap {t['edge']:+.1%})</div>")


def render_card(card):
    home, away = card["home"], card["away"]
    prob_pct = card["model_home_prob"] * 100

    reasons_html = ""
    if card["tier"] in ("HIGH", "MEDIUM"):
        top_for = [r for r in card["breakdown"]
                   if (r["contribution"] > 0) == card["side_is_home"]][:4]
        top_against = [r for r in card["breakdown"]
                       if (r["contribution"] > 0) != card["side_is_home"]][:2]
        side_a = abbr(card["side"])
        loc = "home" if card["side_is_home"] else "away"
        bullets = [
            f"<li>Model {card['side_model_prob']:.1%} vs Market {card['side_fair_prob']:.1%}</li>",
            f"<li>Edge {card['edge']:+.1%} on {loc} side ({side_a})</li>",
        ]
        bullets += [_reason_bullet(r, home, away) for r in top_for]
        bullets += [f"<span class='against'>{_reason_bullet(r, home, away)[4:-5]}</span>"
                    .join(["<li class='against'>", "</li>"]) for r in top_against]
        reasons_html = "<ul class='reasons'>" + "".join(bullets) + "</ul>"

    suppressed_html = ""
    if card["tier"] in ("HIGH", "MEDIUM") and not card.get("approved", True):
        items = "".join(f"<li>{r}</li>" for r in card.get("rejections", []))
        suppressed_html = (f"<div class='rec none'><b>Flag suppressed — not bet.</b>"
                           f"<ul class='reasons'>{items}</ul></div>")
        card = {**card, "tier": "SUPPRESSED"}

    if card["tier"] == "SUPPRESSED":
        rec = suppressed_html
    elif card["tier"] == "HIGH":
        rec = (f"<div class='rec high'><span class='tier high'>HIGH</span>"
               f"<span class='pick'>{abbr(card['side'])} ML "
               f"({card['side_odds']:+.0f} @ {card['side_book']})</span>"
               f"<span class='edge'>Edge: {card['edge']:+.1%}</span>{reasons_html}</div>")
    elif card["tier"] == "MEDIUM":
        rec = (f"<div class='rec medium'><span class='tier medium'>MEDIUM</span>"
               f"<span class='pick'>{abbr(card['side'])} ML "
               f"({card['side_odds']:+.0f} @ {card['side_book']})</span>"
               f"<span class='edge'>Edge: {card['edge']:+.1%}</span>{reasons_html}</div>")
    else:
        rec = (f"<div class='rec none'>Moneyline recommendation: <b>No clear value</b> "
               f"(largest gap {card['edge']:+.1%})</div>")

    dq = "Weather: real (live feed)" if card["weather_real"] else "Weather: placeholder (not posted yet)"
    dq += " &nbsp;·&nbsp; Lineups: " + ("confirmed" if card["lineups"] else "not posted")

    return f"""
    <div class='card'>
      <div class='head'>
        <div>
          <div class='abbrs'>{abbr(away)} @ {abbr(home)}</div>
          <div class='fullnames'>{away} at {home}</div>
        </div>
        <span class='meta'>{card['time_str']}{' · ' + card['venue'] if card['venue'] else ''}</span>
      </div>
      {render_markets(card)}
      <div class='probbar'><div style='width:{prob_pct:.1f}%'></div></div>
      <div class='problabel'><span>{abbr(away)} {100 - prob_pct:.1f}%</span><span>{abbr(home)} {prob_pct:.1f}%</span></div>
      <div class='rechead'>Moneyline Recommendation</div>
      {rec}
      <div class='rechead'>Total Recommendation</div>
      {render_totals_rec(card)}
      <div class='dq'>{dq}</div>
    </div>"""


def build_report(target_date, cards, no_odds_games):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    high = sum(1 for c in cards if c["tier"] == "HIGH" and c.get("approved", True))
    medium = sum(1 for c in cards if c["tier"] == "MEDIUM" and c.get("approved", True))

    missing_html = ""
    if no_odds_games:
        items = "".join(f"<li>{g}</li>" for g in no_odds_games)
        missing_html = (f"<div class='card'><b>No odds posted yet</b>"
                        f"<ul class='reasons'>{items}</ul></div>")

    html = f"""<!DOCTYPE html>
<html><head><meta charset='utf-8'>
<title>SportsQuant-AI — Edge Report {target_date}</title>
<style>{CSS}</style></head><body><div class='wrap'>
<h1>SportsQuant-AI — Game Cheat Sheet</h1>
<div class='sub'>{target_date} · generated {datetime.now().strftime('%Y-%m-%d %H:%M')} ·
moneyline model vs best available market price</div>
<div class='totals'>
  <div class='stat'><div class='n'>{len(cards) + len(no_odds_games)}</div><div class='l'>Games</div></div>
  <div class='stat'><div class='n'>{high + medium}</div><div class='l'>Recommended</div></div>
  <div class='stat'><div class='n'>{high} High · {medium} Medium</div><div class='l'>Confidence</div></div>
</div>
{''.join(render_card(c) for c in cards)}
{missing_html}
<div class='footer'>
Recommendations are simulated paper bets logged to bet_log.csv for model evaluation —
not wagering advice. Flat 1-unit stakes. "Why" bullets are the logistic regression's
exact per-feature contributions for this game (value shown is the model's input).
</div>
</div></body></html>"""

    path = REPORTS_DIR / f"edge_report_{target_date}.html"
    path.write_text(html, encoding="utf-8")
    return path
