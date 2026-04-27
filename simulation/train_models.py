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
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.model_selection import train_test_split, GridSearchCV, StratifiedKFold
from sklearn.metrics import (accuracy_score, classification_report,
                             confusion_matrix, ConfusionMatrixDisplay)

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

# ── Train / test split (binary labels — used by IF) ────────────────────────────
X_train, X_test, y_clf_train, y_clf_test = train_test_split(
    X, y_clf, test_size=0.2, random_state=42, stratify=y_clf
)

# ===============================================================================
# 1. Random Forest Multiclass Classifier — Fault Identification
#
#    Five classes: Normal | F1_Partial_Shading | F2_Inverter_Overload |
#                          F3_Deep_Discharge   | F5_Sensor_Dead
#
#    Training data is synthesised from the CSV's Normal rows by applying the
#    same fault-injection physics used in the simulator. The model learns what
#    each fault LOOKS LIKE in the normalized feature space.
#
#    Confidence from predict_proba() drives severity in the live pipeline:
#      conf >= 0.75  → Critical
#      0.5 ≤ conf < 0.75 → Warning  (fault identified, less certain)
#      conf < 0.5 + IF anomaly → Uncertain_Anomaly soft indicator
# ===============================================================================
print("\n--- Multiclass Fault Dataset Generation --------------------------------")

rng      = np.random.default_rng(42)
N_NORMAL = 50_000
N_FAULT  = 12_500

# Normal: sample from clean CSV rows
n_idx  = rng.choice(np.where(y_clf == 0)[0], N_NORMAL, replace=False)
X_norm = X.iloc[n_idx].copy(); y_norm = np.full(N_NORMAL, 'Normal')

# F1 Partial Shading — irradiance stays high but PV current collapses
f1_idx = rng.choice(np.where(y_clf == 0)[0], N_FAULT, replace=False)
X_f1   = X.iloc[f1_idx].copy()
X_f1['pv_current_norm'] = rng.uniform(0.0, 0.06, N_FAULT)
X_f1['pv_power_norm']   = X_f1['pv_voltage_norm'] * X_f1['pv_current_norm']
X_f1['net_flux_norm']   = X_f1['pv_power_norm'] - X_f1['ac_power_norm']
y_f1 = np.full(N_FAULT, 'F1_Partial_Shading')

# F2 Inverter Overload — AC load spikes, battery temp rises, voltage sags
f2_idx = rng.choice(np.where(y_clf == 0)[0], N_FAULT, replace=False)
X_f2   = X.iloc[f2_idx].copy()
X_f2['ac_power_norm']        = np.clip(X_f2['ac_power_norm']   * rng.uniform(2.0, 3.0, N_FAULT), 0, 1.5)
X_f2['ac_current_norm']      = np.clip(X_f2['ac_current_norm'] * rng.uniform(2.0, 3.0, N_FAULT), 0, 1.5)
X_f2['battery_temp_c']       = X_f2['battery_temp_c'] + rng.uniform(15, 25, N_FAULT)
X_f2['temp_delta_c']         = X_f2['battery_temp_c'] - X_f2['ambient_temp_c']
X_f2['battery_voltage_norm'] = np.clip(X_f2['battery_voltage_norm'] - rng.uniform(0.02, 0.05, N_FAULT), 0, 1)
X_f2['net_flux_norm']        = X_f2['pv_power_norm'] - X_f2['ac_power_norm']
y_f2 = np.full(N_FAULT, 'F2_Inverter_Overload')

# F3 Deep Discharge — battery below chemistry threshold, system goes dark
# battery_voltage_norm ~0.71 = 10.2V / 14.4V (below 10.5V threshold)
f3_idx = rng.choice(np.where(y_clf == 0)[0], N_FAULT, replace=False)
X_f3   = X.iloc[f3_idx].copy()
X_f3['battery_voltage_norm'] = rng.uniform(0.60, 0.73, N_FAULT)
X_f3['soc_percent']          = rng.uniform(0.0,  8.0,  N_FAULT)
X_f3['pv_current_norm']      = 0.0
X_f3['pv_power_norm']        = 0.0
X_f3['irradiance_norm']      = 0.0
X_f3['ac_power_norm']        = np.clip(X_f3['ac_power_norm'] * 0.3, 0, 1)
X_f3['ac_current_norm']      = np.clip(X_f3['ac_current_norm'] * 0.3, 0, 1)
X_f3['net_flux_norm']        = -X_f3['ac_power_norm']
y_f3 = np.full(N_FAULT, 'F3_Deep_Discharge')

# F5 Sensor Dead — current sensors blank while irradiance still present
f5_idx = rng.choice(np.where(y_clf == 0)[0], N_FAULT, replace=False)
X_f5   = X.iloc[f5_idx].copy()
X_f5['pv_current_norm']      = 0.0
X_f5['pv_power_norm']        = 0.0
X_f5['battery_current_norm'] = 0.0
X_f5['battery_power_norm']   = 0.0
X_f5['ac_power_norm']        = 0.0
X_f5['ac_current_norm']      = 0.0
X_f5['net_flux_norm']        = 0.0
y_f5 = np.full(N_FAULT, 'F5_Sensor_Dead')

X_multi = pd.concat([X_norm, X_f1, X_f2, X_f3, X_f5], ignore_index=True)
y_multi = np.concatenate([y_norm, y_f1, y_f2, y_f3, y_f5])
print(f"Multiclass dataset: {len(X_multi):,} rows")
for cls in np.unique(y_multi):
    print(f"  {cls:<28} {(y_multi == cls).sum():>6,}")

X_train_m, X_test_m, y_train_m, y_test_m = train_test_split(
    X_multi, y_multi, test_size=0.2, random_state=42, stratify=y_multi
)

# ── 5-fold Stratified GridSearchCV on 10% sample ─────────────────────────────
print("\n--- RF Multiclass Classifier (5-fold CV, f1_weighted) -----------------")
_, X_cv_m, _, y_cv_m = train_test_split(
    X_train_m, y_train_m, test_size=0.10, random_state=42, stratify=y_train_m
)
print(f"CV sample  : {len(X_cv_m):,} rows | Full train: {len(X_train_m):,} rows")

param_grid  = {'n_estimators': [100, 150, 200, 250], 'max_depth': [10, 15, 20, 25]}
cv_splitter = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
print(f"GridSearchCV: 16 combos x 5 folds = 80 fits ...")

grid_search = GridSearchCV(
    RandomForestClassifier(class_weight='balanced', n_jobs=-1, random_state=42),
    param_grid=param_grid, cv=cv_splitter, scoring='f1_weighted',
    n_jobs=-1, verbose=1, refit=False,
)
grid_search.fit(X_cv_m, y_cv_m)

best_params = grid_search.best_params_
print(f"\nBest params   : {best_params}")
print(f"Best CV F1-wt : {grid_search.best_score_:.4f}")

# CV results table + heatmap
cv_results = pd.DataFrame(grid_search.cv_results_)
cv_table = (cv_results[['param_n_estimators','param_max_depth','mean_test_score','std_test_score']]
            .sort_values('mean_test_score', ascending=False)
            .rename(columns={'param_n_estimators':'n_estimators','param_max_depth':'max_depth',
                             'mean_test_score':'Mean CV F1-wt','std_test_score':'Std CV F1-wt'}))
cv_table['n_estimators'] = cv_table['n_estimators'].astype(int)
cv_table['max_depth']    = cv_table['max_depth'].astype(int)
cv_table.to_csv(os.path.join(EVAL_DIR, "rf_cv_results.csv"), index=False)
print(cv_table.head(5).to_string(index=False))

pivot = cv_results.pivot_table(values='mean_test_score',
                                index='param_max_depth', columns='param_n_estimators')
pivot.index = pivot.index.astype(int); pivot.columns = pivot.columns.astype(int)
fig, ax = plt.subplots(figsize=(8, 5))
sns.heatmap(pivot, annot=True, fmt='.3f', cmap='YlGn', ax=ax, linewidths=0.5)
ax.set_title('5-Fold CV F1-Weighted — RF Multiclass Fault Classifier (higher = better)')
ax.set_xlabel('n_estimators'); ax.set_ylabel('max_depth')
bc = list(pivot.columns).index(best_params['n_estimators'])
br = list(pivot.index).index(best_params['max_depth'])
ax.add_patch(plt.Rectangle((bc, br), 1, 1, fill=False, edgecolor='blue', lw=3))
plt.tight_layout(); plt.savefig(os.path.join(IMG_DIR, "rf_cv_heatmap.png"), dpi=150); plt.close()

# Final fit on full multiclass training set
print(f"\nRefitting on full {len(X_train_m):,}-row multiclass training set ...")
rf = RandomForestClassifier(**best_params, class_weight='balanced', n_jobs=-1, random_state=42)
rf.fit(X_train_m, y_train_m)

# Evaluation
y_pred_m = rf.predict(X_test_m)
acc = accuracy_score(y_test_m, y_pred_m)
print(f"\nOverall accuracy: {acc:.4f}")
print("\nPer-class report:")
print(classification_report(y_test_m, y_pred_m, zero_division=0))

cm_rf = confusion_matrix(y_test_m, y_pred_m, labels=rf.classes_)
fig, ax = plt.subplots(figsize=(8, 7))
ConfusionMatrixDisplay(confusion_matrix=cm_rf, display_labels=rf.classes_).plot(
    ax=ax, cmap='Greens', colorbar=False, xticks_rotation=20)
ax.set_title(f'RF Multiclass Fault Classifier — Confusion Matrix  (Accuracy={acc:.3f})')
plt.tight_layout(); plt.savefig(f"{IMG_DIR}/rf_confusion_matrix.png", dpi=150); plt.close()

imp_df = pd.DataFrame({'Feature': FEATURE_COLS, 'Importance': rf.feature_importances_})
imp_df = imp_df.sort_values('Importance', ascending=False)
print("Top 5 features:"); print(imp_df.head(5).to_string(index=False))
plt.figure(figsize=(10, 6))
sns.barplot(x='Importance', y='Feature', data=imp_df, palette='viridis')
plt.title('Feature Importance — RF Multiclass Fault Classifier')
plt.tight_layout(); plt.savefig(f"{IMG_DIR}/feature_importance.png", dpi=150); plt.close()

joblib.dump(rf, f"{MODEL_DIR}/rf_model.pkl")
joblib.dump({'X_test': X_test_m, 'y_test': y_test_m,
             'classes': list(rf.classes_), 'feature_cols': FEATURE_COLS},
            f"{MODEL_DIR}/rf_test_split.pkl")
print(f"RF multiclass classifier saved.  Classes: {list(rf.classes_)}")

# ===============================================================================
# 2. Isolation Forest — unsupervised anomaly detection (first stage gate)
# ===============================================================================
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
plt.title('Isolation Forest Confusion Matrix')
plt.ylabel('Actual'); plt.xlabel('Predicted')
plt.tight_layout(); plt.savefig(f"{IMG_DIR}/if_confusion_matrix.png")
plt.close()

joblib.dump(if_model, f"{MODEL_DIR}/if_model.pkl")
print("IF model saved.")

print(f"\nTraining complete. Models written to: {os.path.abspath(MODEL_DIR)}")
