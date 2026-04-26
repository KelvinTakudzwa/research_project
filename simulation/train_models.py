"""
train_models.py — Trains RF and IF models on the new 15-feature normalized schema.

Derives normalized features from the original CSV (old column names) using the
same Ohm's Law bounds and chemistry-specific SoC bounds that systemBounds.js
computes at Node.js startup.  FEATURE_COLS here must stay in sync with:
  - ml_engine/api/main.py          FEATURE_COLS
  - ml_engine/jobs/retrainer.py    FEATURE_COLS
"""

import os
import joblib
import numpy as np
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())
import pandas as pd
import matplotlib
matplotlib.use('Agg')   # headless / no display required
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.ensemble import RandomForestRegressor, IsolationForest
from sklearn.model_selection import train_test_split, GridSearchCV, KFold
from sklearn.metrics import (mean_squared_error, r2_score, mean_absolute_error,
                             mean_absolute_percentage_error, confusion_matrix)

# -- Paths ---------------------------------------------------------------------
BASE      = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE, "..", "ml_engine", "solar_data_365days.csv")
MODEL_DIR = os.path.join(BASE, "..", "ml_engine", "models")
IMG_DIR   = os.path.join(BASE, "..", "docs", "images")
EVAL_DIR  = os.path.join(BASE, "..", "evaluation")
os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(IMG_DIR,   exist_ok=True)
os.makedirs(EVAL_DIR,  exist_ok=True)

# -- Bounds — mirror systemBounds.js resolution logic -------------------------
def _env(key, fallback):
    try:
        v = float(os.environ.get(key, ''))
        return v if v > 0 else fallback
    except (ValueError, TypeError):
        return fallback

NOMINAL_V   = _env('BATTERY_NOMINAL_VOLTAGE_V', 12.0)
RATED_PV_W  = _env('RATED_PV_WATTAGE_W',        200.0)
RATED_INV_W = _env('RATED_INVERTER_WATTAGE_W',  300.0)
MAX_PV_V    = _env('MAX_PV_VOLTAGE_V',           21.6)
MAX_PV_I    = _env('MAX_PV_CURRENT_A',           RATED_PV_W / NOMINAL_V)
MAX_PV_P    = _env('MAX_PV_POWER_W',             RATED_PV_W)
MAX_BATT_I  = _env('MAX_BATTERY_CURRENT_A',      RATED_PV_W / NOMINAL_V)
MAX_AC_P    = _env('MAX_AC_POWER_W',             RATED_INV_W)
MAX_AC_V    = _env('MAX_AC_VOLTAGE_V',           240.0)
MAX_AC_I    = _env('MAX_AC_CURRENT_A',           MAX_AC_P / MAX_AC_V)
MAX_IRR     = _env('MAX_IRRADIANCE_WM2',         1000.0)

# Chemistry table (mirrors systemBounds.js CHEMISTRY_TABLE)
CHEMISTRY_TABLE = {
    'LEAD_ACID':   {'nominal_cell_v': 2.00, 'bulk_cell_v': 2.400},
    'AGM':         {'nominal_cell_v': 2.00, 'bulk_cell_v': 2.350},
    'LITHIUM':     {'nominal_cell_v': 3.20, 'bulk_cell_v': 3.650},
    'LIFEPO4':     {'nominal_cell_v': 3.20, 'bulk_cell_v': 3.650},
    'LITHIUM_ION': {'nominal_cell_v': 3.65, 'bulk_cell_v': 4.200},
    'NMC':         {'nominal_cell_v': 3.65, 'bulk_cell_v': 4.200},
}
CHEM_KEY = os.environ.get('BATTERY_CHEMISTRY', 'LEAD_ACID').upper()
if CHEM_KEY not in CHEMISTRY_TABLE:
    print(f"FATAL: BATTERY_CHEMISTRY '{CHEM_KEY}' not recognised. Must be LITHIUM or LEAD_ACID.")
    raise SystemExit(1)

chem       = CHEMISTRY_TABLE[CHEM_KEY]
cells      = round(NOMINAL_V / chem['nominal_cell_v'])
MAX_BATT_V = cells * chem['bulk_cell_v']   # chemistry-derived bulk charge ceiling

INVERTER_EFF = 0.90

print(f"[Bounds] {CHEM_KEY} / {NOMINAL_V}V / {cells} cells")
print(f"         PV  : {MAX_PV_P}W / {MAX_PV_V}V / {MAX_PV_I:.2f}A")
print(f"         Batt: {MAX_BATT_V:.2f}V / {MAX_BATT_I:.2f}A")
print(f"         AC  : {MAX_AC_P}W / {MAX_AC_V}V / {MAX_AC_I:.3f}A")
print(f"         Irr : {MAX_IRR} W/m²")

# -- Load CSV ------------------------------------------------------------------
print("\nLoading CSV...")
df = pd.read_csv(DATA_PATH)
print(f"Loaded {len(df):,} rows | columns: {df.columns.tolist()}")

# -- Derive new physical fields from old CSV column names ----------------------
df['pv_voltage_v']      = df['pv_voltage']
df['pv_current_a']      = df['pv_current']
df['battery_voltage_v'] = df['batt_voltage']
df['ambient_temp_c']    = df['temp_ambient']
df['battery_temp_c']    = df['temp_probe']
df['temp_delta_c']      = df['temp_delta']
df['irradiance_wm2']    = df['irradiance_lux'] / 120.0

# Synthesise AC subsystem — same logic as mqtt_stream.py
# ac_power_w is the actual AC watts out after inverter conversion loss
df['ac_power_w']      = df['load_current'] * df['batt_voltage'] * INVERTER_EFF
df['ac_power_factor'] = 0.88   # representative mixed load average
df['ac_current_a']    = df['ac_power_w'] / (230.0 * df['ac_power_factor'])

# battery_current_a: thermodynamically correct net balance
# DC draw = ac_power_w / (batt_voltage * eff) = load_current  (simplifies)
df['battery_current_a'] = df['pv_current'] - df['load_current']
df['battery_power_w']   = df['battery_voltage_v'] * df['battery_current_a']
df['pv_power_w']        = df['pv_voltage_v'] * df['pv_current_a']
df['net_energy_flux_w'] = df['pv_power_w'] - df['ac_power_w']

# -- Min-Max normalization — must match dataProcessor.js exactly ---------------
df['pv_voltage_norm']      = df['pv_voltage_v']      / MAX_PV_V
df['pv_current_norm']      = df['pv_current_a']      / MAX_PV_I
df['pv_power_norm']        = df['pv_power_w']        / MAX_PV_P
df['battery_voltage_norm'] = df['battery_voltage_v'] / MAX_BATT_V
df['battery_current_norm'] = df['battery_current_a'] / MAX_BATT_I  # signed
df['battery_power_norm']   = df['battery_power_w']   / MAX_PV_P
df['ac_power_norm']        = df['ac_power_w']        / MAX_AC_P
df['ac_current_norm']      = df['ac_current_a']      / MAX_AC_I
df['net_flux_norm']        = df['net_energy_flux_w'] / MAX_PV_P
df['irradiance_norm']      = df['irradiance_wm2']    / MAX_IRR

# -- Feature set (sync with main.py + retrainer.py) ---------------------------
FEATURE_COLS = [
    'pv_voltage_norm',      'pv_current_norm',      'pv_power_norm',
    'battery_voltage_norm', 'battery_current_norm', 'battery_power_norm',
    'ac_power_norm',        'ac_current_norm',       'net_flux_norm',
    'irradiance_norm',
    'soc_percent',          'ac_power_factor',
    'ambient_temp_c',       'battery_temp_c',        'temp_delta_c',
]

X     = df[FEATURE_COLS].dropna()
y     = df.loc[X.index, 'soh_percent']
y_clf = df.loc[X.index, 'label']

print(f"\nFeature matrix : {X.shape}")
print(f"Anomaly count  : {int(y_clf.sum())} / {len(y_clf)} ({y_clf.mean()*100:.2f}%)")

# -- Train / test split --------------------------------------------------------
X_train, X_test, y_train, y_test, y_clf_train, y_clf_test = train_test_split(
    X, y, y_clf, test_size=0.2, random_state=42
)

# ===============================================================================
# 1. Random Forest Regressor — SoH prediction
#    Two-phase approach:
#      Phase 1: 5-fold GridSearchCV on a 10% CV sample to find best params
#      Phase 2: Final model trained on the full training partition
# ===============================================================================
print("\n--- Random Forest Regressor (5-fold GridSearchCV) ---------------------")

# ── Phase 1: Hyperparameter search on 10% sample ──────────────────────────────
# Running GridSearchCV on 420k rows × 80 fits would take ~60 min.
# A 10% stratified sample (~42k rows) is statistically representative and
# keeps the search under 5 minutes while preserving the target distribution.
_, X_cv, _, y_cv = train_test_split(
    X_train, y_train, test_size=0.10, random_state=42
)
print(f"CV sample  : {len(X_cv):,} rows  (10% of training partition)")
print(f"Full train : {len(X_train):,} rows  (used for final fit)")

param_grid = {
    'n_estimators': [100, 150, 200, 250],
    'max_depth':    [10,  15,  20,  25],
}
cv_splitter = KFold(n_splits=5, shuffle=True, random_state=42)

print(f"\nRunning GridSearchCV: {len(param_grid['n_estimators']) * len(param_grid['max_depth'])} "
      f"combinations x 5 folds = "
      f"{len(param_grid['n_estimators']) * len(param_grid['max_depth']) * 5} fits ...")

grid_search = GridSearchCV(
    RandomForestRegressor(min_samples_leaf=5, n_jobs=-1, random_state=42),
    param_grid   = param_grid,
    cv           = cv_splitter,
    scoring      = 'neg_root_mean_squared_error',
    n_jobs       = -1,
    verbose      = 1,
    refit        = False,   # final fit uses full X_train — done explicitly below
)
grid_search.fit(X_cv, y_cv)

best_params = grid_search.best_params_
best_cv_rmse = -grid_search.best_score_
print(f"\nBest params : {best_params}")
print(f"Best CV RMSE: {best_cv_rmse:.4f}%  (mean across 5 folds)")

# ── Save full CV results table (thesis Table X) ────────────────────────────────
cv_results = pd.DataFrame(grid_search.cv_results_)
cv_results['mean_rmse'] = -cv_results['mean_test_score']
cv_results['std_rmse']  =  cv_results['std_test_score']
cv_table = (
    cv_results[['param_n_estimators', 'param_max_depth', 'mean_rmse', 'std_rmse']]
    .sort_values('mean_rmse')
    .rename(columns={
        'param_n_estimators': 'n_estimators',
        'param_max_depth':    'max_depth',
        'mean_rmse':          'Mean CV RMSE (%)',
        'std_rmse':           'Std CV RMSE (%)',
    })
)
cv_table['n_estimators'] = cv_table['n_estimators'].astype(int)
cv_table['max_depth']    = cv_table['max_depth'].astype(int)
cv_csv_path = os.path.join(EVAL_DIR, "rf_cv_results.csv")
cv_table.to_csv(cv_csv_path, index=False)
print(f"\nFull CV results ({len(cv_table)} rows) saved to {cv_csv_path}")
print(cv_table.head(5).to_string(index=False))

# ── Heatmap: mean RMSE by n_estimators x max_depth (thesis Figure) ─────────────
pivot = cv_results.pivot_table(
    values='mean_rmse',
    index='param_max_depth',
    columns='param_n_estimators',
)
pivot.index   = pivot.index.astype(int)
pivot.columns = pivot.columns.astype(int)

fig, ax = plt.subplots(figsize=(8, 5))
sns.heatmap(
    pivot, annot=True, fmt='.3f', cmap='YlOrRd_r', ax=ax,
    linewidths=0.5, annot_kws={'size': 10},
)
ax.set_title('5-Fold Cross-Validation RMSE (%) — Random Forest\nn_estimators vs max_depth  (lower = better)')
ax.set_xlabel('n_estimators'); ax.set_ylabel('max_depth')
# Mark the winning cell
best_col = list(pivot.columns).index(best_params['n_estimators'])
best_row = list(pivot.index).index(best_params['max_depth'])
ax.add_patch(plt.Rectangle((best_col, best_row), 1, 1, fill=False,
                             edgecolor='blue', lw=3, label='Best'))
ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, fill=False, edgecolor='blue', lw=2)],
          labels=[f"Best: {best_params}"], loc='upper right', fontsize=9)
plt.tight_layout()
heatmap_path = os.path.join(IMG_DIR, "rf_cv_heatmap.png")
plt.savefig(heatmap_path, dpi=150)
plt.close()
print(f"CV heatmap saved to {heatmap_path}")

# ── Phase 2: Final model on full training partition ────────────────────────────
print(f"\nRefitting with best params on full {len(X_train):,}-row training set ...")
rf = RandomForestRegressor(
    **best_params,
    min_samples_leaf=5,
    n_jobs=-1,
    random_state=42,
)
rf.fit(X_train, y_train)

# ── Evaluation on held-out test set ───────────────────────────────────────────
y_pred = rf.predict(X_test)
rmse = np.sqrt(mean_squared_error(y_test, y_pred))
mae  = mean_absolute_error(y_test, y_pred)
mape = mean_absolute_percentage_error(y_test, y_pred)
r2   = r2_score(y_test, y_pred)
print(f"\nTest-set metrics (20% held-out, CV-tuned model):")
print(f"  RMSE : {rmse:.4f}%  (Target: <5.0%)")
print(f"  MAE  : {mae:.4f}%")
print(f"  MAPE : {mape*100:.4f}%")
print(f"  R2   : {r2:.4f}   (Target: >0.50)")

plt.figure(figsize=(8, 8))
plt.scatter(y_test, y_pred, alpha=0.3, color='indigo', s=8)
plt.plot([y.min(), y.max()], [y.min(), y.max()], 'r--', lw=2, label='Perfect Prediction')
plt.title(f'Random Forest: Actual vs Predicted SoH\n'
          f'Best params: n_estimators={best_params["n_estimators"]}, '
          f'max_depth={best_params["max_depth"]}  |  R2={r2:.4f}')
plt.xlabel('Actual SoH (%)'); plt.ylabel('Predicted SoH (%)')
plt.legend(); plt.grid(True, alpha=0.3); plt.tight_layout()
plt.savefig(f"{IMG_DIR}/soh_regression_scatter.png", dpi=150)
plt.close()

imp_df = pd.DataFrame({'Feature': FEATURE_COLS, 'Importance': rf.feature_importances_})
imp_df = imp_df.sort_values('Importance', ascending=False)
print("\nTop 5 features:")
print(imp_df.head(5).to_string(index=False))

plt.figure(figsize=(10, 6))
sns.barplot(x='Importance', y='Feature', data=imp_df, palette='viridis')
plt.title(f'Feature Importance (Random Forest — CV-tuned, n_est={best_params["n_estimators"]}, '
          f'depth={best_params["max_depth"]})')
plt.tight_layout()
plt.savefig(f"{IMG_DIR}/feature_importance.png", dpi=150)
plt.close()

joblib.dump(rf, f"{MODEL_DIR}/rf_model.pkl")
joblib.dump({'X_test': X_test, 'y_test': y_test, 'feature_cols': FEATURE_COLS},
            f"{MODEL_DIR}/rf_test_split.pkl")
print("RF model + test split saved.")

# ═══════════════════════════════════════════════════════════════════════════════
# 2. Isolation Forest — unsupervised anomaly detection
# ═══════════════════════════════════════════════════════════════════════════════
print("\n--- Isolation Forest --------------------------------------------------")
X_normal = X_train[y_clf_train == 0]
print(f"Training on {len(X_normal):,} normal samples only (label=0).")

contamination = round(float(y_clf_train.mean()), 4)
print(f"Empirical contamination rate: {contamination:.4f}")

if_model = IsolationForest(contamination=contamination, random_state=42, n_jobs=-1)
if_model.fit(X_normal)

if_preds  = if_model.predict(X_test)
y_test_if = np.where(y_clf_test == 0, 1, -1)
accuracy  = (if_preds == y_test_if).mean()
print(f"IF Accuracy on test set: {accuracy:.4f}")

cm = confusion_matrix(y_test_if, if_preds, labels=[1, -1])
plt.figure(figsize=(6, 5))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
            xticklabels=['Normal', 'Anomaly'], yticklabels=['Normal', 'Anomaly'])
plt.title('Isolation Forest Confusion Matrix (new schema)')
plt.ylabel('Actual'); plt.xlabel('Predicted')
plt.tight_layout(); plt.savefig(f"{IMG_DIR}/if_confusion_matrix.png")

joblib.dump(if_model, f"{MODEL_DIR}/if_model.pkl")
print("IF model saved.")

print(f"\nTraining complete. Models written to: {os.path.abspath(MODEL_DIR)}")
