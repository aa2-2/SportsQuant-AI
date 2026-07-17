import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import cross_val_score, TimeSeriesSplit

df = pd.read_csv("data/games_with_features_all_seasons.csv")
df["date"] = pd.to_datetime(df["date"])

BASE_FEATURES = [
    "home_pitcher_era", "away_pitcher_era",
    "home_pitcher_whiff_rate", "away_pitcher_whiff_rate",
    "hr_park_factor", "temp", "wind_speed",
    "home_team_avg_exit_velo", "away_team_avg_exit_velo",
    "home_team_hr_rate", "away_team_hr_rate",
    "home_team_k_rate", "away_team_k_rate",
    "home_team_top_power_exit_velo", "away_team_top_power_exit_velo",
    "home_team_top_power_hr_rate", "away_team_top_power_hr_rate",
    "home_pitcher_vs_opp_era", "away_pitcher_vs_opp_era",
    "home_team_vs_away_pitcher_avg", "away_team_vs_home_pitcher_avg",
]

RUN_DIFF_ONLY = BASE_FEATURES + ["home_team_run_diff", "away_team_run_diff"]
ELO_ONLY = BASE_FEATURES + ["home_team_elo", "away_team_elo"]
BOTH = BASE_FEATURES + ["home_team_run_diff", "away_team_run_diff", "home_team_elo", "away_team_elo"]

y = df["home_win"]
tscv = TimeSeriesSplit(n_splits=5)

for name, features in [
    ("RUN_DIFF ONLY (current best)", RUN_DIFF_ONLY),
    ("ELO ONLY", ELO_ONLY),
    ("BOTH (run_diff + elo)", BOTH),
]:
    X = df[features]

    lr_pipeline = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
    lr_scores = cross_val_score(lr_pipeline, X, y, cv=tscv)

    rf_scores = cross_val_score(
        RandomForestClassifier(n_estimators=100, max_depth=3, min_samples_leaf=20, random_state=42),
        X, y, cv=tscv
    )

    print(f"\n{name} ({len(features)} features)")
    print(f"  Logistic Regression CV: {lr_scores.mean():.3f} (+/- {lr_scores.std():.3f})")
    print(f"  Random Forest CV:       {rf_scores.mean():.3f} (+/- {rf_scores.std():.3f})")