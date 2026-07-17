"""
Publishes the project as a branded static website via GitHub Pages.

Generates docs/ :
  index.html   — homepage: live record baked from bet_log.csv, recent
                 graded bets as ledger rows, the eight gates, links
  method.html  — how the system works, honestly (pipeline, gates,
                 calibration, limitations)
  season.html  — copy of the season-results dashboard
  today.html   — copy of the newest daily cheat sheet
  style.css    — shared stylesheet

Usage after any run you want reflected online:
    python src/publish_site.py
    git add docs && git commit -m "Publish latest reports" && git push

One-time GitHub setup: repo -> Settings -> Pages -> Deploy from a
branch -> main, /docs. Everything in docs/ becomes PUBLIC.
"""
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd

from config import DATA_DIR, PROJECT_ROOT
from bet_log import BET_LOG_PATH
from teams import abbr

REPORTS_DIR = DATA_DIR / "reports"
DOCS_DIR = PROJECT_ROOT / "docs"

CSS = """
:root{--paper:#EFF3EC;--ink:#1E3A2F;--text:#2B2B28;--rule:#C9D4C6;--win:#1E6B3C;
--loss:#B3392E;--muted:#6E7A6E;--card:#F7FAF5;}
*{box-sizing:border-box;margin:0}
body{background:var(--paper);color:var(--text);font-family:'Public Sans',system-ui,sans-serif;
font-size:16px;line-height:1.6}
.mono{font-family:'IBM Plex Mono',monospace;font-variant-numeric:tabular-nums}
a{color:var(--ink)}
.wrap{max-width:960px;margin:0 auto;padding:0 20px}
header{border-bottom:2px solid var(--ink)}
.bar{display:flex;justify-content:space-between;align-items:center;padding:16px 0}
.mark{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:22px;
letter-spacing:.06em;color:var(--ink);text-decoration:none}
nav a{margin-left:22px;font-size:14px;text-decoration:none;color:var(--text)}
nav a:hover{text-decoration:underline}
.hero{padding:56px 0 40px;background:
repeating-linear-gradient(to bottom,transparent 0 27px,var(--rule) 27px 28px)}
h1{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:clamp(38px,6vw,58px);
line-height:1.05;color:var(--ink);text-transform:uppercase;letter-spacing:.01em;max-width:640px}
.sub{margin:14px 0 0;color:var(--muted);max-width:560px}
.ledger{background:var(--card);border:2px solid var(--ink);margin:36px 0 0}
.ledger-head{display:grid;grid-template-columns:repeat(4,1fr);border-bottom:2px solid var(--ink)}
.stat{padding:16px 18px;border-right:1px solid var(--rule)}
.stat:last-child{border-right:none}
.stat .l{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
.stat .n{font-size:30px;font-weight:600}
.n.win{color:var(--win)}.n.loss{color:var(--loss)}
.rows{font-size:14px}
.row{display:grid;grid-template-columns:88px 1fr 130px 70px 90px;gap:10px;
padding:9px 18px;border-top:1px solid var(--rule);align-items:baseline}
.row.headrow{color:var(--muted);font-size:11px;letter-spacing:.12em;text-transform:uppercase;border-top:none}
.grade{font-weight:600}
.grade.W{color:var(--win)}.grade.L{color:var(--loss)}.grade.P{color:var(--muted)}
.empty{padding:22px 18px;color:var(--muted)}
.actions{display:flex;gap:14px;margin:28px 0 0;flex-wrap:wrap}
.btn{display:inline-block;border:2px solid var(--ink);padding:12px 22px;text-decoration:none;
font-family:'Barlow Condensed',sans-serif;font-size:18px;letter-spacing:.05em;
text-transform:uppercase;color:var(--ink);background:var(--card)}
.btn.solid{background:var(--ink);color:var(--paper)}
.btn:focus-visible{outline:3px solid var(--loss);outline-offset:2px}
section{padding:48px 0;border-top:1px solid var(--rule)}
h2{font-family:'Barlow Condensed',sans-serif;font-weight:600;font-size:28px;color:var(--ink);
text-transform:uppercase;letter-spacing:.03em;margin-bottom:18px}
.gates{list-style:none;counter-reset:g}
.gates li{counter-increment:g;display:grid;grid-template-columns:52px 1fr;gap:14px;
padding:12px 0;border-bottom:1px solid var(--rule)}
.gates li::before{content:counter(g,decimal-leading-zero);font-family:'IBM Plex Mono',monospace;
color:var(--loss);font-size:18px;padding-top:2px}
.gates b{display:block;color:var(--ink)}
.gates span{color:var(--muted);font-size:14px}
p.body{max-width:640px;margin-bottom:14px}
footer{border-top:2px solid var(--ink);padding:26px 0;font-size:13px;color:var(--muted)}
@media(max-width:640px){.ledger-head{grid-template-columns:repeat(2,1fr)}
.stat:nth-child(2){border-right:none}.row{grid-template-columns:70px 1fr 60px;font-size:13px}
.row .hide-m{display:none}}
@media(prefers-reduced-motion:no-preference){.btn{transition:transform .12s ease}
.btn:hover{transform:translateY(-2px)}}
"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700'
         '&family=Public+Sans:wght@400;600&family=IBM+Plex+Mono:wght@400;600&display=swap" '
         'rel="stylesheet">')

GATES = [
    ("Minimum edge 3%", "Below that, model-vs-market disagreement is noise."),
    ("Expected value at the real price", "The edge must survive the vig — profit is computed at the posted odds, not the fair line."),
    ("Probability band 30–70%", "The side doesn't need to be favored, but it must sit where the model's calibration is proven."),
    ("Both starting pitchers posted", "A flag built on placeholder pitching isn't the model's real opinion."),
    ("Odds between −250 and +250", "Beyond that, \u201cedges\u201d are usually stale lines or payout traps."),
    ("Edge sanity cap 15%", "Too good to be true means a data bug, not market-beating insight."),
    ("Game not started", "A bet logged after first pitch is hindsight, and hindsight poisons a track record."),
    ("Model must beat its baseline", "The totals model failed this check — so the system refuses its bets, automatically."),
]


def page(title, body, active=""):
    def navlink(href, label):
        return f'<a href="{href}">{label}</a>'
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#1E3A2F">
<link rel="manifest" href="manifest.json">
<link rel="apple-touch-icon" href="icon-192.png">
<title>{title} — MLBQuant</title>{FONTS}
<link rel="stylesheet" href="style.css">
<script>if('serviceWorker' in navigator){{navigator.serviceWorker.register('sw.js');}}</script>
</head><body>
<header><div class="wrap bar">
<a class="mark" href="index.html">MLBQUANT</a>
<nav>{navlink("season.html", "Results")}{navlink("today.html", "Today")}{navlink("method.html", "Method")}</nav>
</div></header>
{body}
<footer><div class="wrap">All stakes are simulated 1-unit paper bets — a public, timestamped
model track record, not wagering advice. Built by a student; every pick is logged before
first pitch and graded after. <a href="https://github.com/aa2-2/SportsQuant-AI">Source on GitHub</a>.
</div></footer></body></html>"""


def load_record():
    if not BET_LOG_PATH.exists():
        return None
    df = pd.read_csv(BET_LOG_PATH)
    if len(df) == 0:
        return None
    df["profit_num"] = pd.to_numeric(df.get("profit_units"), errors="coerce").fillna(0.0)
    return df


def ledger_html(df):
    if df is None:
        return ('<div class="ledger"><div class="empty mono">Ledger opens with the first '
                'graded slate.</div></div>')

    settled = df[df["status"].isin(["won", "lost", "push"])]
    pending = df[df["status"] == "pending"]
    wins = int((settled["status"] == "won").sum())
    losses = int((settled["status"] == "lost").sum())
    pushes = int((settled["status"] == "push").sum())
    profit = settled["profit_num"].sum()
    staked = pd.to_numeric(settled.get("stake_units"), errors="coerce").fillna(0).sum()
    roi = profit / staked if staked > 0 else 0.0
    cls = "win" if profit > 0 else ("loss" if profit < 0 else "")

    record = f"{wins}-{losses}" + (f"-{pushes}" if pushes else "")
    head = f"""<div class="ledger-head mono">
<div class="stat"><div class="l">Record</div><div class="n">{record}</div></div>
<div class="stat"><div class="l">P&amp;L</div><div class="n {cls}">{profit:+.1f}u</div></div>
<div class="stat"><div class="l">ROI</div><div class="n {cls}">{roi:+.1%}</div></div>
<div class="stat"><div class="l">Pending</div><div class="n">{len(pending)}</div></div>
</div>"""

    def pick_label(bet):
        bt = str(bet.get("bet_type") or "moneyline")
        if bt.startswith("total"):
            try:
                return f"{str(bet['side']).upper()} {float(bet['line']):g}"
            except (TypeError, ValueError):
                return str(bet["side"]).upper()
        return f"{abbr(str(bet['side']))} ML"

    rows = ('<div class="row headrow mono"><div>Date</div><div>Pick</div>'
            '<div class="hide-m">Odds / Model</div><div>Grade</div>'
            '<div class="hide-m">Units</div></div>')
    recent = df.iloc[::-1].head(6)
    for _, bet in recent.iterrows():
        status = str(bet["status"])
        grade = {"won": "W", "lost": "L", "push": "P"}.get(status, "·")
        units = f"{bet['profit_num']:+.2f}u" if status in ("won", "lost", "push") else "pending"
        rows += (f'<div class="row mono"><div>{bet["game_date"]}</div>'
                 f'<div>{pick_label(bet)} <span style="color:var(--muted)">'
                 f'({bet["matchup"]})</span></div>'
                 f'<div class="hide-m">{float(bet["odds"]):+.0f} / {float(bet["model_prob"]):.0%}</div>'
                 f'<div class="grade {grade}">{grade}</div>'
                 f'<div class="hide-m">{units}</div></div>')

    return f'<div class="ledger">{head}<div class="rows">{rows}</div></div>'


def build_index(cheat_label):
    df = load_record()
    updated = datetime.now().strftime("%B %d, %Y %H:%M")
    body = f"""
<div class="hero"><div class="wrap">
<h1>Every call logged before first&nbsp;pitch. Graded&nbsp;after.</h1>
<p class="sub">A student-built MLB model that compares its win probabilities against the
betting market, bets on paper under an eight-gate policy, and publishes the graded ledger —
wins, losses, and everything it refused to bet. Daily cards now carry a per-batter HR board:
calibrated home-run probabilities (platoon, park, and weather adjusted) with the minimum
odds worth taking.</p>
{ledger_html(df)}
<div class="actions">
<a class="btn solid" href="season.html">Full season ledger</a>
<a class="btn" href="today.html">{cheat_label}</a>
<a class="btn" href="method.html">How it works</a>
</div>
</div></div>
<section><div class="wrap">
<h2>Eight gates between a flag and a bet</h2>
<p class="body">The model disagreeing with the market is not enough. Every prospective bet
passes this checklist or is published as <em>suppressed, with the reason</em> — a system
that hides its rejections can't be audited.</p>
<ol class="gates">{''.join(f'<li><div><b>{t}</b><span>{d}</span></div></li>' for t, d in GATES)}</ol>
</div></section>
"""
    return page("Live ledger", body) .replace("Updated —", f"Updated {updated}")


def build_method():
    body = """
<div class="hero"><div class="wrap"><h1>How the system works</h1>
<p class="sub">And, just as deliberately, what it refuses to do.</p></div></div>
<section><div class="wrap">
<h2>The pipeline</h2>
<p class="body">Six seasons of MLB results, starting pitchers, Statcast batted-ball data, and
game-time weather feed 25 leakage-safe features — every rolling statistic uses only
information available <em>before</em> the game it describes. A calibrated logistic regression
produces win probabilities; those are compared against vig-removed consensus odds from nine
sportsbooks; disagreements above threshold become flags; flags that clear all eight gates
become simulated 1-unit paper bets, logged with their odds, probability, expected value,
and the model's top reasons. Final scores grade every bet automatically.</p>
<h2>Why the probabilities can be trusted (and where they can't)</h2>
<p class="body">Calibration analysis on held-out 2026 games shows predicted probabilities in
the 30–70% band track observed win rates. Outside that band the samples are thin and the
model measurably overconfident — so the policy simply refuses to bet there. The betting gates
are derived from the project's own validation findings, not borrowed thresholds.</p>
<h2>What it refuses to do</h2>
<p class="body">A second model that predicts run totals failed to beat the naive
always-predict-the-average baseline in cross-validation. The system reads that verdict from
the model's own saved report card and disables O/U betting automatically — the model exists,
and is not allowed to act, until it earns it. There is also no real-money automation anywhere:
the ledger's job is to establish, in public, whether the edges are real. Sizing stays at a
flat 1 unit; quarter-Kelly stakes are recorded in parallel for comparison but never used,
because Kelly trusts the model's probabilities and that trust is exactly what's being tested.</p>
<h2>The HR board</h2>
<p class="body">Each game card lists every confirmed batter's probability of homering —
built bottom-up from per-plate-appearance rates (validated on 109,000 held-out plate
appearances), his lineup slot's measured trips to the plate, the platoon matchup against
tonight's starter, the park's HR factor, and a weather multiplier fitted on this project's
own games. The board shows one action number: the minimum sportsbook price worth taking.
The model's fair odds are the break-even; any price at or above them is value if the
calibration holds — and the calibration tables are public. No EV percentages are shown
against a "consensus" this site doesn't ingest; a comparison that can't be made honestly
isn't made.</p>
<h2>Honest limitations</h2>
<p class="body">Cross-validated accuracy is ~0.55 against a 0.52 home-team baseline — a real
but thin signal, nowhere near guaranteed to survive closing-line vig. Some prediction inputs
fall back to training-mean placeholders when lineups or weather aren't posted (a fallback
scheme rebuilt after a placeholder bias was caught flagging every road team on one slate —
graded honestly in the project log). The sample of settled bets is small; nothing here is a
conclusion yet. That's what the ledger is for.</p>
</div></section>
"""
    return page("Method", body)


MANIFEST = """{
  "name": "MLBQuant",
  "short_name": "MLBQuant",
  "description": "MLBQuant — an MLB model paper-trading ledger. Every call logged before first pitch, graded after.",
  "start_url": "index.html",
  "display": "standalone",
  "background_color": "#EFF3EC",
  "theme_color": "#1E3A2F",
  "icons": [
    {"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
    {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"}
  ]
}"""

# Network-first: always show fresh ledger data when online, fall back
# to the last cached copy when offline.
SERVICE_WORKER = """const CACHE='mlbq-v1';
self.addEventListener('install',e=>{self.skipWaiting();});
self.addEventListener('activate',e=>{e.waitUntil(clients.claim());});
self.addEventListener('fetch',e=>{
  if(e.request.method!=='GET')return;
  e.respondWith(
    fetch(e.request).then(r=>{
      const copy=r.clone();
      caches.open(CACHE).then(c=>c.put(e.request,copy));
      return r;
    }).catch(()=>caches.match(e.request))
  );
});"""


if __name__ == "__main__":
    DOCS_DIR.mkdir(exist_ok=True)
    published = []

    (DOCS_DIR / "style.css").write_text(CSS, encoding="utf-8")
    published.append("style.css")

    (DOCS_DIR / "manifest.json").write_text(MANIFEST, encoding="utf-8")
    (DOCS_DIR / "sw.js").write_text(SERVICE_WORKER, encoding="utf-8")
    published.append("manifest.json + sw.js (installable app support)")

    assets = PROJECT_ROOT / "assets"
    for icon in ["icon-192.png", "icon-512.png"]:
        if (assets / icon).exists():
            shutil.copy(assets / icon, DOCS_DIR / icon)
            published.append(icon)

    season = REPORTS_DIR / "season_results.html"
    if season.exists():
        shutil.copy(season, DOCS_DIR / "season.html")
        published.append("season.html")

    edge_reports = sorted(REPORTS_DIR.glob("edge_report_*.html"))
    cheat_label = "Today's card"
    if edge_reports:
        latest = edge_reports[-1]
        shutil.copy(latest, DOCS_DIR / "today.html")
        cheat_label = latest.stem.replace("edge_report_", "Card: ")
        published.append(f"today.html ({latest.name})")

    (DOCS_DIR / "index.html").write_text(build_index(cheat_label), encoding="utf-8")
    published.append("index.html")
    (DOCS_DIR / "method.html").write_text(build_method(), encoding="utf-8")
    published.append("method.html")

    print("Published to docs/:")
    for item in published:
        print(f"  - {item}")
    print('\nNow run:  git add docs && git commit -m "Publish site" && git push')
