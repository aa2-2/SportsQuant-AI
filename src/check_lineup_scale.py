"""
DIAGNOSTIC: is live lineup power on the same scale as training?

Tonight's slate showed live top-power exit velos of 82.5-85.5 while the
calibrated placeholder (= training mean) sits ~91 — and four flags over
11%, the fake-edge signature. This script settles it with data:

  A. Distribution check: training CSV's top-power columns vs the values
     get_lineup_power produces for current teams.
  B. Formula check: for the 10 highest-volume batters, training's
     rolling(10).shift(1) value vs live's tail(10).mean() on the SAME
     batter_stats frame — any gap here is computation, not selection.

    python src/check_lineup_scale.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DATA_DIR  # noqa: E402
from live_features import get_lineup_power, load_prediction_context  # noqa: E402

feats = pd.read_csv(DATA_DIR / "games_with_features_all_seasons.csv")
train_vals = pd.concat([feats["home_team_top_power_exit_velo"],
                        feats["away_team_top_power_exit_velo"]])
print("A. TRAINING top-power exit velo:  "
      f"mean {train_vals.mean():.2f}  std {train_vals.std():.2f}  "
      f"p10 {train_vals.quantile(.1):.2f}  p90 {train_vals.quantile(.9):.2f}")

ctx = load_prediction_context(DATA_DIR)
bs = ctx["batter_stats"]
print(f"   live batter_stats: {len(bs):,} batter-games, "
      f"avg_exit_velo mean {bs['avg_exit_velo'].mean():.2f}")

# B. Same-frame formula comparison for high-volume batters
top_batters = bs["batter"].value_counts().head(10).index
print("\nB. Per-batter: training rolling(10, shift 1) vs live tail(10).mean() — same data")
gaps = []
for b in top_batters:
    g = bs[bs["batter"] == b].sort_values("game_date")
    rolling = g["avg_exit_velo"].shift(1).rolling(10, min_periods=1).mean().iloc[-1]
    live = g["avg_exit_velo"].tail(10).mean()
    gaps.append(rolling - live)
    print(f"   batter {b}: rolling {rolling:.2f}  live {live:.2f}  gap {rolling - live:+.2f}")
print(f"   mean formula gap: {sum(gaps) / len(gaps):+.2f} mph "
      "(near 0 = formulas agree; the skew is elsewhere)")

# C. What live produces for a real 9-man sample vs training distribution
sample = bs.groupby("batter").size().sort_values(ascending=False).head(60).index
demo_lineup = [{"id": int(b)} for b in sample[:9]]
velo, hr = get_lineup_power(demo_lineup, bs)
print(f"\nC. get_lineup_power on 9 high-volume batters: exit velo {velo:.2f}, hr {hr:.3f}")
print(f"   vs training mean {train_vals.mean():.2f} -> "
      f"gap {velo - train_vals.mean():+.2f} mph")
print("\nVERDICT GUIDE: |gap| in C under ~1 mph = scale fine, tonight's edges real.")
print("Gap of -4 to -7 mph = live values systematically low -> every posted lineup")
print("reads 'weak' -> fake edges -> tonight's HIGH flags are bug artifacts:")
print("purge tonight's logged bets per the July 16 precedent and we fix the source.")
