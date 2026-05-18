"""
Chapter 4 Evaluation Suite - ML Sub-package
Script 3: baseline_comparison.py

Implements the Nassar et al. (2024) static-threshold approach and compares
its physical detection rates against the trained Isolation Forest to prove
AI superiority for F1 (Partial Shading) and F5 (Sensor Dead) - the two
fault types that static thresholds cannot reliably distinguish.

Static threshold rules use the new raw physical column names
(battery_voltage_v, ac_power_w, irradiance_wm2, etc.) while the IF
model uses the 15 normalized features.

Produces:
  - baseline_vs_ml_comparison.csv
  - docs/images/baseline_vs_ml_bar.png
"""

import json
import joblib
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
EVAL_DIR     = os.path.dirname(SCRIPT_DIR)
MODEL_DIR    = os.path.join(EVAL_DIR, "..", "ml_engine", "models")
DOCS_IMG_DIR = os.path.join(EVAL_DIR, "..", "docs", "images")
os.makedirs(DOCS_IMG_DIR, exist_ok=True)

# ── Feature set for IF model (normalized - must match evaluate_ml_models.py) ──
FEATURE_COLS = [
    'pv_voltage_norm',      'pv_current_norm',      'pv_power_norm',
    'battery_voltage_norm', 'battery_current_norm', 'battery_power_norm',
    'ac_power_norm',        'ac_current_norm',       'net_flux_norm',
    'irradiance_norm',
    'soc_percent',          'ac_power_factor',
    'ambient_temp_c',       'battery_temp_c',        'temp_delta_c',
]

# ── 1. Load Data & Model ──────────────────────────────────────────────────────
dataset_path = os.path.join(EVAL_DIR, "ml_test_dataset.csv")
try:
    df = pd.read_csv(dataset_path)
except FileNotFoundError:
    print(f"[ERROR] Dataset not found: {dataset_path}")
    print("        Run evaluation/ml/generate_ml_dataset.py first.")
    raise SystemExit(1)

try:
    if_model = joblib.load(os.path.join(MODEL_DIR, "if_model.pkl"))
except FileNotFoundError:
    print(f"[ERROR] if_model.pkl not found in {MODEL_DIR}")
    raise SystemExit(1)

missing = [c for c in FEATURE_COLS if c not in df.columns]
if missing:
    print(f"[ERROR] Missing normalized columns in dataset: {missing}")
    print("        Re-run generate_ml_dataset.py to regenerate the dataset.")
    raise SystemExit(1)

# ── 2. Static Threshold Baseline (Nassar et al., 2024) ───────────────────────
def static_threshold_detect(row) -> int:
    """
    Static threshold rules representing the Nassar et al. (2024) approach,
    adapted to this system's physical units. Each rule reflects a single-variable
    or two-variable engineering heuristic typical of non-AI monitoring systems.

    Calibration notes (why each threshold was chosen):
    - F2 (Overload)  : 60 W = 20% of rated inverter capacity (300 W). Standard
                       load-factor heuristic. Fails here because this system's
                       actual operating load (7-12 W) means even a 2.5x surge
                       only reaches ~29 W — below the threshold. The heuristic
                       is not wrong; the system's operating point is not known
                       to the threshold rule without site-specific data.
    - F3 (Discharge) : 11.5 V is a widely-used lead-acid low-voltage alarm.
                       Reliable because the fault pushes voltage to ~10.3 V.
    - F1 (Shading)   : Irradiance > 667 W/m2 (two-thirds peak) gates for
                       clear-sky conditions; pv_current < 0.5 A flags the
                       collapse. Catches F1 because the simulated fault forces
                       current to 0.3 A.
    - F5 (Sensor Dead): Three-way cross-check — irradiance > 200 W/m2 confirms
                        the sun is shining; pv_voltage > 15 V confirms the panel
                        is responding (PV open-circuit voltage stays near 18–21 V
                        even at moderate irradiance; dropping below 15 V implies
                        night-time or a panel fault, not sensor blanking);
                        pv_current < 0.1 A flags the current sensor as dead.
                        All three together are unambiguous: external light is
                        present, the panel is active, but the current measurement
                        has failed. No temperature gate; sub-zero conditions do
                        not occur in the deployment climate.
    """
    # F2 proxy — Overload (2× the 95th-percentile of observed normal AC load,
    # ~25 W for this 12 V / 220 V system). Conservative system-aware heuristic:
    # double the measured high-water mark, giving a 2× safety margin before
    # flagging. Rated-capacity rules (e.g. 20% of 300 W = 60 W) are unsuitable
    # when the system operates far below its rated ceiling.
    if row['ac_power_w'] > 25.0:
        return 1
    # F3 proxy — Deep Discharge (lead-acid low-voltage alarm)
    if row['battery_voltage_v'] < 11.5:
        return 1
    # F1 proxy — Partial Shading (clear-sky + current collapse)
    if row['irradiance_wm2'] > 667 and row['pv_current_a'] < 0.5:
        return 1
    # F5 proxy — Sensor Blanking (three-way cross-check)
    # irradiance > 200 W/m2 : sun is shining
    # pv_voltage > 15 V     : panel is responding (VOC stays high even at low irradiance)
    # pv_current < 0.1 A    : current sensor reads near-zero (dead sensor, not a cloudy day)
    if (row['irradiance_wm2'] > 200
            and row['pv_voltage_v'] > 15.0
            and row['pv_current_a'] < 0.1):
        return 1
    return 0

df['baseline_pred'] = df.apply(static_threshold_detect, axis=1)

# ── 3. IF Predictions (calibrated threshold from evaluate_ml_models.py) ───────
threshold_path = os.path.join(EVAL_DIR, "ml_threshold.json")
try:
    with open(threshold_path) as _f:
        best_threshold = json.load(_f)['optimal_threshold']
    print(f"  Loaded calibrated IF threshold: {best_threshold:.4f}  (from ml_threshold.json)")
except FileNotFoundError:
    print("[WARNING] ml_threshold.json not found -- run evaluate_ml_models.py first.")
    print("          Falling back to 10th-percentile score threshold.")
    if_scores_all  = if_model.decision_function(df[FEATURE_COLS])
    best_threshold = float(np.percentile(if_scores_all, 10))

if_scores    = if_model.decision_function(df[FEATURE_COLS])
df['ml_pred'] = np.where(if_scores < best_threshold, 1, 0)

# ── 4. Detection Rate per Fault Scenario (fault windows only) ─────────────────
faults_only = df[df['label'] == 1].copy()

results = []
for fault_id, group in faults_only.groupby('fault_id'):
    total     = len(group)
    ml_hits   = group['ml_pred'].sum()
    base_hits = group['baseline_pred'].sum()
    results.append({
        "Fault Type":                  fault_id,
        "ML Detection Rate (%)":       round((ml_hits   / total) * 100, 1),
        "Baseline Detection Rate (%)": round((base_hits / total) * 100, 1),
    })

results_df = pd.DataFrame(results)

NAME_MAP = {
    "F1": "Partial Shading (F1)",
    "F2": "Inverter Overload (F2)",
    "F3": "Deep Discharge (F3)",
    "F5": "Sensor Blanking (F5)",
}
results_df['Fault Type'] = results_df['Fault Type'].map(NAME_MAP).fillna(results_df['Fault Type'])

print()
print("=" * 60)
print("  Comparative Analysis: Isolation Forest vs. Static Baseline")
print("=" * 60)
print(results_df.to_string(index=False))

# ── 5. Bar Chart ──────────────────────────────────────────────────────────────
ax = results_df.set_index('Fault Type').plot(
    kind='bar', figsize=(9, 6),
    color=['#2ca02c', '#1f77b4'],
)
plt.title('Fault Detection Superiority: Isolation Forest vs. Static Thresholding\n(Nassar et al., 2024 Baseline)')
plt.ylabel('Detection Rate (%)')
plt.ylim(0, 115)
plt.xticks(rotation=15, ha='right')
plt.axhline(y=100, color='r', linestyle='--', alpha=0.5, label='100% detection')
plt.legend()
plt.tight_layout()

chart_path = os.path.join(DOCS_IMG_DIR, 'baseline_vs_ml_bar.png')
plt.savefig(chart_path)
plt.close()

out_csv = os.path.join(EVAL_DIR, "baseline_vs_ml_comparison.csv")
results_df.to_csv(out_csv, index=False)

print(f"\n  Saved chart : {chart_path}")
print(f"  Saved table : {out_csv}")
print()
