import pandas as pd
import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import cross_val_score, TimeSeriesSplit
from sklearn.metrics import accuracy_score

from config import DATA_DIR, FEATURE_COLUMNS, TARGET_COLUMN


def load_training_data():
    df = pd.read_csv(DATA_DIR / "games_with_features_all_seasons.csv")
    df["date"] = pd.to_datetime(df["date"])
    X = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]
    return X, y, df


def validate_no_missing_values(X):
    """
    Explicit, loud check before any training happens. Without this,
    a NaN slipping into any feature (e.g. the missing add_batting_strength
    fallback found earlier this project) crashes training with a
    confusing sklearn stack trace instead of a clear, actionable message.
    """
    missing = X.isna().sum()
    missing = missing[missing > 0]

    if len(missing) > 0:
        raise ValueError(
            f"Training data contains missing values in {len(missing)} column(s):\n"
            f"{missing.to_string()}\n"
            f"Every feature-building function should have a fillna() safety net. "
            f"Check the feature that produced these NaNs before training."
        )

    print("Missing-value check passed: no NaNs in any feature column.")


def train_test_split_by_date(X, y, df, cutoff_date):
    cutoff_date = pd.to_datetime(cutoff_date)
    is_train = df["date"] < cutoff_date
    return X[is_train], X[~is_train], y[is_train], y[~is_train]


def train_logistic_regression(X_train, y_train):
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    model = LogisticRegression(max_iter=1000)
    model.fit(X_train_scaled, y_train)
    return model, scaler


def train_random_forest(X_train, y_train):
    model = RandomForestClassifier(n_estimators=100, max_depth=3, min_samples_leaf=20, random_state=42)
    model.fit(X_train, y_train)
    return model


def calibrate_model(model, scaler, X_train, y_train):
    """
    Wraps the trained model with a calibration layer using sigmoid
    (Platt scaling) - isotonic was tried first and made things worse
    by overfitting a sparse high-confidence bucket (only 51 games at
    70%+ probability). Sigmoid's simpler correction curve is the right
    choice for a dataset this size.
    """
    X_train_scaled = scaler.transform(X_train)
    calibrated = CalibratedClassifierCV(model, method="sigmoid", cv=5)
    calibrated.fit(X_train_scaled, y_train)
    return calibrated


if __name__ == "__main__":
    X, y, df = load_training_data()
    print(f"Loaded {len(X)} games")
    print(f"Date range: {df['date'].min().date()} to {df['date'].max().date()}")
    print(f"Home win rate overall: {y.mean():.3f}")

    validate_no_missing_values(X)

    cutoff = "2026-03-25"
    X_train, X_test, y_train, y_test = train_test_split_by_date(X, y, df, cutoff)

    print(f"\nCutoff date: {cutoff}")
    print(f"Training games: {len(X_train)}")
    print(f"Testing games: {len(X_test)}")

    print("\n" + "=" * 50)
    print("LOGISTIC REGRESSION")
    print("=" * 50)

    model, scaler = train_logistic_regression(X_train, y_train)
    X_train_scaled = scaler.transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    print(f"Training accuracy: {accuracy_score(y_train, model.predict(X_train_scaled)):.3f}")
    print(f"Testing accuracy: {accuracy_score(y_test, model.predict(X_test_scaled)):.3f}")
    print(f"Baseline (always predict home team wins): {y_test.mean():.3f}")

    joblib.dump(model, DATA_DIR / "trained_model.joblib")
    joblib.dump(scaler, DATA_DIR / "feature_scaler.joblib")

    print("\nCalibrating model (sigmoid/Platt scaling)...")
    calibrated_model = calibrate_model(model, scaler, X_train, y_train)
    joblib.dump(calibrated_model, DATA_DIR / "calibrated_model.joblib")
    print("Calibrated model saved to data/calibrated_model.joblib")

    print("\n" + "=" * 50)
    print("RANDOM FOREST")
    print("=" * 50)

    rf_model = train_random_forest(X_train, y_train)
    print(f"Training accuracy: {accuracy_score(y_train, rf_model.predict(X_train)):.3f}")
    print(f"Testing accuracy: {accuracy_score(y_test, rf_model.predict(X_test)):.3f}")

    print("\nFeature importance:")
    importances = sorted(zip(FEATURE_COLUMNS, rf_model.feature_importances_), key=lambda x: -x[1])
    for name, importance in importances:
        print(f"  {name}: {importance:.4f}")

    joblib.dump(rf_model, DATA_DIR / "random_forest_model.joblib")

    print("\n" + "=" * 50)
    print("CROSS-VALIDATION (5-fold, time-based)")
    print("=" * 50)

    tscv = TimeSeriesSplit(n_splits=5)
    lr_pipeline = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
    lr_cv_scores = cross_val_score(lr_pipeline, X, y, cv=tscv)
    print(f"Logistic Regression CV accuracy: {lr_cv_scores.mean():.3f} (+/- {lr_cv_scores.std():.3f})")
    print(f"  Individual folds: {[round(s, 3) for s in lr_cv_scores]}")

    rf_cv_scores = cross_val_score(
        RandomForestClassifier(n_estimators=100, max_depth=3, min_samples_leaf=20, random_state=42),
        X, y, cv=tscv
    )
    print(f"Random Forest CV accuracy: {rf_cv_scores.mean():.3f} (+/- {rf_cv_scores.std():.3f})")
    print(f"  Individual folds: {[round(s, 3) for s in rf_cv_scores]}")

    print("\nModels saved to data/")