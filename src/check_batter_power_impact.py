import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import cross_val_score, TimeSeriesSplit

df = pd.read_csv("data/games_with_features.csv")
df["date"] = pd.to_datetime(df["date"])

TRIMMED_FEATURES = [
    "home_team_run_diff", "away_team_run_diff",
    "home_pitcher_era", "away_pitcher_era",
    "home_pitcher_whiff_rate", "away_pitcher_whiff_rate",
    "hr_park_factor", "temp", "wind_speed",
    "home_team_avg_exit_velo", "away_team_avg_exit_velo",
    "home_team_hr_rate", "away_team_hr_rate",
    "home_team_k_rate", "away_team_k_rate",
]

WITH_BATTER_POWER = TRIMMED_FEATURES + [
    "home_team_top_power_exit_velo", "away_team_top_power_exit_velo",
    "home_team_top_power_hr_rate", "away_team_top_power_hr_rate",
]

y = df["home_win"]
tscv = TimeSeriesSplit(n_splits=5)

for name, features in [("TRIMMED (15 features, no batter power)", TRIMMED_FEATURES),
                        ("TRIMMED + BATTER POWER (19 features)", WITH_BATTER_POWER)]:
    X = df[features]

    lr_pipeline = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
    lr_scores = cross_val_score(lr_pipeline, X, y, cv=tscv)

    rf_scores = cross_val_score(
        RandomForestClassifier(n_estimators=100, max_depth=3, min_samples_leaf=20, random_state=42),
        X, y, cv=tscv
    )

    print(f"\n{name}")
    print(f"  Logistic Regression CV: {lr_scores.mean():.3f} (+/- {lr_scores.std():.3f})")
    print(f"  Random Forest CV:       {rf_scores.mean():.3f} (+/- {rf_scores.std():.3f})")