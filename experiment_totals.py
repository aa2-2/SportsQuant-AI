import pandas as pd
import numpy as np
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.compose import TransformedTargetRegressor
import joblib
import sys
sys.path.append('src')
from config import DATA_DIR, TOTALS_FEATURE_COLUMNS
from train_totals_model import CUTOFF_DATE

# Load data
df = pd.read_csv(DATA_DIR / 'games_with_features_all_seasons.csv')
df['date'] = pd.to_datetime(df['date'])
df['total_runs'] = df['home_score'] + df['away_score']

# Train/test split
train = df[df['date'] < CUTOFF_DATE]
test = df[df['date'] >= CUTOFF_DATE]

print(f'Training set size: {len(train)}')
print(f'Test set size: {len(test)}')

# Base features
base_features = list(TOTALS_FEATURE_COLUMNS)
print(f'Base features ({len(base_features)}):')
for f in base_features:
    print(f'  {f}')

# Function to evaluate a model
def evaluate_model(model, X_train, y_train, X_test, y_test, model_name):
    model.fit(X_train, y_train)
    preds = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    
    # Calculate MAE for high and low scoring games
    high_mask = y_test >= 10
    low_mask = y_test <= 7
    if high_mask.any():
        mae_high = mean_absolute_error(y_test[high_mask], preds[high_mask])
    else:
        mae_high = np.nan
    if low_mask.any():
        mae_low = mean_absolute_error(y_test[low_mask], preds[low_mask])
    else:
        mae_low = np.nan
    
    print(f'{model_name}:')
    print(f'  Overall MAE: {mae:.3f}')
    print(f'  MAE (>=10 runs): {mae_high:.3f}' if not np.isnan(mae_high) else '  MAE (>=10 runs): N/A')
    print(f'  MAE (<=7 runs): {mae_low:.3f}' if not np.isnan(mae_low) else '  MAE (<=7 runs): N/A')
    return mae, mae_high, mae_low

# Prepare data
X_train = train[base_features]
y_train = train['total_runs']
X_test = test[base_features]
y_test = test['total_runs']

print('\n=== Baseline Models ===')
# Ridge regression (current model)
ridge = Pipeline([
    ('scaler', StandardScaler()),
    ('regressor', Ridge(alpha=1.0))
])
evaluate_model(ridge, X_train, y_train, X_test, y_test, 'Ridge (baseline)')

# Random Forest
rf = RandomForestRegressor(
    n_estimators=200,
    max_depth=5,
    min_samples_leaf=25,
    random_state=42
)
evaluate_model(rf, X_train, y_train, X_test, y_test, 'Random Forest')

# Gradient Boosting
gb = GradientBoostingRegressor(
    n_estimators=200,
    max_depth=3,
    min_samples_leaf=25,
    random_state=42
)
evaluate_model(gb, X_train, y_train, X_test, y_test, 'Gradient Boosting')

# Transformed target (log) with Ridge
print('\n=== Transformed Target Models ===')
log_ridge = TransformedTargetRegressor(
    regressor=Pipeline([
        ('scaler', StandardScaler()),
        ('regressor', Ridge(alpha=1.0))
    ]),
    func=np.log,
    inverse_func=np.exp
)
evaluate_model(log_ridge, X_train, y_train, X_test, y_test, 'Log-transformed Ridge')

# Transformed target with Random Forest
log_rf = TransformedTargetRegressor(
    regressor=RandomForestRegressor(
        n_estimators=200,
        max_depth=5,
        min_samples_leaf=25,
        random_state=42
    ),
    func=np.log,
    inverse_func=np.exp
)
evaluate_model(log_rf, X_train, y_train, X_test, y_test, 'Log-transformed Random Forest')

print('\n=== Feature Engineering ===')
# Create interaction features
def create_interaction_features(df):
    df = df.copy()
    # Temperature interaction with park factors
    df['temp_x_park'] = df['temp'] * df['park_run_factor']
    df['temp_x_hr_park'] = df['temp'] * df['hr_park_factor']
    # Wind interaction
    df['wind_x_park'] = df['signed_wind'] * df['park_run_factor']
    # Offensive/defensive balance
    # home team strength: runs scored - runs allowed
    df['home_team_net_runs'] = df['home_team_runs_scored_avg'] - df['home_team_runs_allowed_avg']
    df['away_team_net_runs'] = df['away_team_runs_scored_avg'] - df['away_team_runs_allowed_avg']
    # Offensive power
    df['home_offense_power'] = df['home_team_runs_scored_avg'] * df['home_team_hr_rate']
    df['away_offense_power'] = df['away_team_runs_scored_avg'] * df['away_team_hr_rate']
    return df

# Apply to train and test
train_feat = create_interaction_features(train)
test_feat = create_interaction_features(test)

# New feature set: base + interactions
interaction_features = [
    'temp_x_park', 'temp_x_hr_park', 'wind_x_park',
    'home_team_net_runs', 'away_team_net_runs',
    'home_offense_power', 'away_offense_power'
]
extended_features = base_features + interaction_features

print(f'Extended features ({len(extended_features)}): base + {len(interaction_features)} interactions')
for f in interaction_features:
    print(f'  {f}')

X_train_ext = train_feat[extended_features]
X_test_ext = test_feat[extended_features]

# Test extended features with Random Forest
rf_ext = RandomForestRegressor(
    n_estimators=200,
    max_depth=5,
    min_samples_leaf=25,
    random_state=42
)
print('\nRandom Forest with interaction features:')
evaluate_model(rf_ext, X_train_ext, y_train, X_test_ext, y_test, 'RF + Interactions')

# Test extended features with Gradient Boosting
gb_ext = GradientBoostingRegressor(
    n_estimators=200,
    max_depth=3,
    min_samples_leaf=25,
    random_state=42
)
print('\nGradient Boosting with interaction features:')
evaluate_model(gb_ext, X_train_ext, y_train, X_test_ext, y_test, 'GB + Interactions')

# Try a simpler interaction: just temp and wind with park
simple_interactions = [
    'temp_x_park', 'wind_x_park'
]
simple_features = base_features + simple_interactions
print(f'\nSimple interaction features ({len(simple_features)}):')
for f in simple_interactions:
    print(f'  {f}')

X_train_simple = train_feat[simple_features]
X_test_simple = test_feat[simple_features]

rf_simple = RandomForestRegressor(
    n_estimators=200,
    max_depth=5,
    min_samples_leaf=25,
    random_state=42
)
print('\nRandom Forest with simple interactions (temp*park, wind*park):')
evaluate_model(rf_simple, X_train_simple, y_train, X_test_simple, y_test, 'RF + Simple Interactions')

print('\nDone.')
