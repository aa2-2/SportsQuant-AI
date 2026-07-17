"""
MLBQuant live dashboard — the "project it on another screen" app.

Run from the project root:

    pip install streamlit
    streamlit run src/dashboard.py

Opens at http://localhost:8501 in your browser (drag to any monitor).
Three tabs:

  1. Season Results — live from bet_log.csv with the interactive
     filters from the reference design: market (All / ML / O/U),
     confidence tier, cumulative P&L chart, headline stats.
  2. Today's Cheat Sheet — the most recent edge report, embedded.
  3. Bet Log — the full ledger as a filterable, sortable table.

The dashboard READS what the pipeline produces; it never places or
logs bets itself. Refresh the page after running calculate_edge.py
or settle_bets.py to see new data.
"""
from pathlib import Path

import pandas as pd
import streamlit as st

# Make src/ imports work no matter where streamlit is launched from
import sys
SRC_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC_DIR))

from config import DATA_DIR  # noqa: E402
from bet_log import BET_LOG_PATH  # noqa: E402

st.set_page_config(page_title="MLBQuant", layout="wide")


def load_log():
    if not BET_LOG_PATH.exists():
        return pd.DataFrame()
    df = pd.read_csv(BET_LOG_PATH)
    if "bet_type" not in df.columns:
        df["bet_type"] = "moneyline"
    df["bet_type"] = df["bet_type"].fillna("moneyline")
    df["profit_num"] = pd.to_numeric(df.get("profit_units"), errors="coerce").fillna(0.0)
    return df


df = load_log()

st.title("MLBQuant")
st.caption("Paper-trading analytics — simulated 1-unit flat stakes, no real money. "
           "Every logged bet passed the six-gate policy in bet_policy.py.")

tab_results, tab_sheet, tab_log = st.tabs(["Season Results", "Today's Cheat Sheet", "Bet Log"])

# ----------------------------------------------------------------- results
with tab_results:
    if len(df) == 0:
        st.info("No bets logged yet — run calculate_edge.py on a game day.")
    else:
        fcol1, fcol2 = st.columns([2, 1])
        with fcol1:
            market = st.radio("Market", ["All", "ML", "O/U"], horizontal=True,
                              label_visibility="collapsed")
        with fcol2:
            tier = st.selectbox("Tier", ["All Tiers", "HIGH", "MEDIUM"],
                                label_visibility="collapsed")

        view = df.copy()
        if market == "ML":
            view = view[view["bet_type"] == "moneyline"]
        elif market == "O/U":
            view = view[view["bet_type"].str.startswith("total")]
        if tier != "All Tiers":
            view = view[view.get("confidence") == tier]

        settled = view[view["status"].isin(["won", "lost", "push"])]
        pending = view[view["status"] == "pending"]
        wins = int((settled["status"] == "won").sum())
        losses = int((settled["status"] == "lost").sum())
        pushes = int((settled["status"] == "push").sum())
        profit = settled["profit_num"].sum()
        staked = pd.to_numeric(settled.get("stake_units"), errors="coerce").fillna(0).sum()
        roi = profit / staked if staked > 0 else 0.0
        win_rate = wins / max(wins + losses, 1)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Record", f"{wins}-{losses}" + (f"-{pushes}" if pushes else ""))
        c2.metric("P&L", f"{profit:+.1f}u")
        c3.metric("ROI", f"{roi:+.1%}")
        c4.metric("Win Rate", f"{win_rate:.1%}")
        st.caption(f"{len(view)} bets ({len(pending)} pending)"
                   + ("" if len(settled) >= 30 else
                      f" — only {len(settled)} settled, far too few to conclude anything yet"))

        st.subheader("Cumulative P&L")
        if len(settled) == 0:
            st.info("Chart appears after the first settlement.")
        else:
            s = settled.reset_index(drop=True)
            chart = pd.DataFrame({
                "TOTAL": s["profit_num"].cumsum(),
                "ML": s["profit_num"].where(s["bet_type"] == "moneyline", 0.0).cumsum(),
                "O/U": s["profit_num"].where(s["bet_type"].str.startswith("total"), 0.0).cumsum(),
            })
            if "kelly_profit_units" in s.columns:
                chart["1/4-Kelly"] = pd.to_numeric(
                    s["kelly_profit_units"], errors="coerce").fillna(0.0).cumsum()
            chart.index = range(1, len(chart) + 1)
            st.line_chart(chart, height=340)
            st.caption("x-axis: settled bet number, in settlement order")

        by_tier = settled.groupby(settled.get("confidence"))["profit_num"] \
            .agg(["count", "sum"]) if len(settled) else None
        if by_tier is not None and len(by_tier) > 0:
            st.subheader("By confidence tier")
            by_tier.columns = ["settled bets", "net units"]
            st.dataframe(by_tier, use_container_width=False)

# --------------------------------------------------------------- cheat sheet
with tab_sheet:
    reports = sorted((DATA_DIR / "reports").glob("edge_report_*.html"))
    if not reports:
        st.info("No cheat sheets generated yet — run calculate_edge.py.")
    else:
        names = [p.name for p in reports][::-1]
        chosen = st.selectbox("Report", names)
        html = (DATA_DIR / "reports" / chosen).read_text(encoding="utf-8")
        st.components.v1.html(html, height=1400, scrolling=True)

# ------------------------------------------------------------------- bet log
with tab_log:
    if len(df) == 0:
        st.info("No bets logged yet.")
    else:
        show = df.drop(columns=["profit_num"], errors="ignore").iloc[::-1]
        st.dataframe(show, use_container_width=True, height=560)
        st.download_button("Download bet_log.csv",
                           data=show.to_csv(index=False),
                           file_name="bet_log.csv", mime="text/csv")
