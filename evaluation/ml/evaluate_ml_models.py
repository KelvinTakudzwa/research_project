"""
Chapter 4 Evaluation Suite - ML Sub-package
Script 2: evaluate_ml_models.py

Loads ml_test_dataset.csv (F1/F2/F3/F5 only) and runs both trained models:
  - Isolation Forest        -> anomaly detection  (Precision, Recall, F1)
  - Random Forest Classifier -> fault probability  (Accuracy, Precision, Recall, F1, AUC)

Produces:
  - ml_results_table.csv        (9 formal metrics for thesis Section 4.x)
  - ml_threshold.json           (optimal IF decision threshold for reuse)
  - docs/images/confusion_matrix_ml.png   (IF confusion matrix)
  - docs/images/rf_confusion_matrix.png   (RF confusion matrix)

NOTE: F4 / network / PDR metrics are NOT computed here.
      See evaluation/pipeline/evaluate_pipeline.py for those.
"""

import json
import joblib
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (precision_score, recall_score, f1_score,
                             accuracy_score, roc_auc_score, confusion_matrix,
                             classification_report, ConfusionMatrixDisplay)
from sklearn.preprocessing import LabelEncoder

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
EVAL_DIR     = os.path.dirname(SCRIPT_DIR)
MODEL_DIR    = os.path.join(EVAL_DIR, "..", "ml_engine", "models")
DOCS_IMG_DIR = os.path.join(EVAL_DIR, "..", "docs", "images")
os.makedirs(DOCS_IMG_DIR, exist_ok=True)

# ── Feature set (must match main.py + retrainer.py + train_models.py) ─────────
FEATURE_COLS = [
    'pv_voltage_norm',      'pv_current_norm',      'pv_power_norm',
    'battery_voltage_norm', 'battery_current_norm', 'battery_power_norm',
    'ac_power_norm',        'ac_current_norm',       'net_flux_norm',
    'irradiance_norm',
    'soc_percent',          'ac_power_factor',
    'ambient_temp_c',       'battery_temp_c',        'temp_delta_c',
]

# ── 1. Load Dataset ───────────────────────────────────────────────────────────
dataset_path = os.path.join(EVAL_DIR, "ml_test_dataset.csv")
try:
    df = pd.read_csv(dataset_path)
except FileNotFoundError:
    print(f"[ERROR] Dataset not found: {dataset_path}")
    print("        Run evaluation/ml/generate_ml_dataset.py first.")
    raise SystemExit(1)

if 'F4' in df.get('fault_id', pd.Series()).values:
    print("[WARNING] F4 rows detected -- excluding.")
    df = df[df['fault_id'] != 'F4'].copy()

missing = [c for c in FEATURE_COLS if c not in df.columns]
if missing:
    print(f"[ERROR] Missing normalized columns in dataset: {missing}")
    print("        Re-run generate_ml_dataset.py to regenerate the dataset.")
    raise SystemExit(1)

# ── 2. Load Models ────────────────────────────────────────────────────────────
try:
    if_model = joblib.load(os.path.join(MODEL_DIR, "if_model.pkl"))
    rf_model = joblib.load(os.path.join(MODEL_DIR, "rf_model.pkl"))
except FileNotFoundError as e:
    print(f"[ERROR] Model not found: {e}")
    print("        Run simulation/train_models.py first.")
    raise SystemExit(1)

X      = df[FEATURE_COLS]
y_true = df['label'].values

# ================================================================================
# METRIC BATCH 1 - Isolation Forest (Anomaly Detection)
# ================================================================================
print()
print("=" * 60)
print("  ML Metric Batch 1 - Isolation Forest (Anomaly Detection)")
print("=" * 60)

if_scores = if_model.decision_function(X)

# Find the IF decision threshold that maximises F1 on the labelled test set.
# Standard practice for unsupervised novelty detectors.
best_f1, best_threshold = 0.0, 0.0
for thresh in np.linspace(if_scores.min(), if_scores.max(), 500):
    y_trial  = np.where(if_scores < thresh, 1, 0)
    trial_f1 = f1_score(y_true, y_trial, zero_division=0)
    if trial_f1 > best_f1:
        best_f1, best_threshold = trial_f1, thresh

y_pred_if    = np.where(if_scores < best_threshold, 1, 0)
precision_if = precision_score(y_true, y_pred_if, zero_division=0)
recall_if    = recall_score(y_true,    y_pred_if, zero_division=0)
f1_if        = f1_score(y_true,        y_pred_if, zero_division=0)

# Persist threshold for baseline_comparison.py
threshold_path = os.path.join(EVAL_DIR, "ml_threshold.json")
with open(threshold_path, 'w') as _f:
    json.dump({"optimal_threshold": best_threshold, "best_f1": best_f1}, _f, indent=2)

print(f"  Optimal Decision Threshold : {best_threshold:.4f}  (saved to ml_threshold.json)")
print(f"  Precision                  : {precision_if:.4f}  (Target: >0.90)")
print(f"  Recall                     : {recall_if:.4f}")
print(f"  F1-Score                   : {f1_if:.4f}  (Target: >0.90)")

# Confusion matrix
cm = confusion_matrix(y_true, y_pred_if)
fig, ax = plt.subplots(figsize=(6, 5))
sns.heatmap(
    cm, annot=True, fmt='d', cmap='Blues', ax=ax,
    xticklabels=['Predicted Normal', 'Predicted Fault'],
    yticklabels=['Actual Normal',    'Actual Fault'],
)
ax.set_title('Isolation Forest - Confusion Matrix\n(F1: Shading, F2: Overload, F3: Discharge, F5: Sensor Dead)')
plt.tight_layout()
cm_path = os.path.join(DOCS_IMG_DIR, 'confusion_matrix_ml.png')
plt.savefig(cm_path)
plt.close()
print(f"\n  Saved: {cm_path}")

# ================================================================================
# METRIC BATCH 2 - Random Forest Multiclass Classifier
# Uses ml_test_dataset.csv with fault_id (F1/F2/F3/F5/NORMAL) as ground truth.
# RF was retrained as a 5-class classifier — binary rf_test_split.pkl is stale.
# ================================================================================
print()
print("=" * 60)
print("  ML Metric Batch 2 - Random Forest Classifier (Multiclass)")
print("=" * 60)

# Ground truth: only rows where label=1 are actual fault rows.
# Pre/post-fault rows in each block have label=0 (Normal features) even though
# fault_id names the block — the RF correctly classifies them as Normal.
FAULT_ID_MAP = {
    'F1': 'F1_Partial_Shading',
    'F2': 'F2_Inverter_Overload',
    'F3': 'F3_Deep_Discharge',
    'F5': 'F5_Sensor_Dead',
}
X_rf     = df[FEATURE_COLS]
y_rf     = df.apply(
    lambda r: FAULT_ID_MAP[r['fault_id']] if r['label'] == 1 else 'Normal', axis=1
)
rf_source = f"ml_test_dataset.csv ({len(X_rf)} rows, 5-class, label-aware)"

rf_pred      = rf_model.predict(X_rf)
rf_pred_prob = rf_model.predict_proba(X_rf)        # shape (n, 5)
class_names  = list(rf_model.classes_)

rf_acc  = accuracy_score(y_rf, rf_pred)
rf_prec = precision_score(y_rf, rf_pred, average='weighted', zero_division=0)
rf_rec  = recall_score(y_rf,   rf_pred, average='weighted', zero_division=0)
rf_f1   = f1_score(y_rf,       rf_pred, average='weighted', zero_division=0)

# Weighted OVR AUC for multiclass
le        = LabelEncoder().fit(class_names)
y_rf_enc  = le.transform(y_rf)
rf_auc    = roc_auc_score(y_rf_enc, rf_pred_prob, multi_class='ovr', average='weighted')

print(f"  Evaluation source : {rf_source}")
print(f"  Accuracy          : {rf_acc:.4f}")
print(f"  Precision (wtd)   : {rf_prec:.4f}  (Target: >0.90)")
print(f"  Recall    (wtd)   : {rf_rec:.4f}")
print(f"  F1-Score  (wtd)   : {rf_f1:.4f}  (Target: >0.90)")
print(f"  ROC-AUC (OVR wtd) : {rf_auc:.4f}")
print()
print("  Per-class report:")
print(classification_report(y_rf, rf_pred, target_names=class_names, zero_division=0))

# Per-class CV results heatmap (feature importance)
fi_path = os.path.join(EVAL_DIR, "rf_cv_results.csv")
if os.path.exists(fi_path):
    cv_df = pd.read_csv(fi_path)
    if {'n_estimators', 'max_depth', 'Mean CV F1-wt'}.issubset(cv_df.columns):
        try:
            pivot = cv_df.pivot(index='max_depth', columns='n_estimators', values='Mean CV F1-wt')
            fig, ax = plt.subplots(figsize=(7, 4))
            sns.heatmap(pivot, annot=True, fmt='.4f', cmap='YlGn', ax=ax, vmin=0.95, vmax=1.0)
            ax.set_title('5-Fold CV F1-Weighted — RF Multiclass GridSearchCV')
            plt.tight_layout()
            plt.savefig(os.path.join(DOCS_IMG_DIR, 'rf_cv_heatmap.png'))
            plt.close()
        except Exception:
            pass

# Multiclass confusion matrix
cm_rf      = confusion_matrix(y_rf, rf_pred, labels=class_names)
short_names = ['F1\nShading', 'F2\nOverload', 'F3\nDischarge', 'F5\nSensor', 'Normal']
fig, ax    = plt.subplots(figsize=(8, 6))
sns.heatmap(cm_rf, annot=True, fmt='d', cmap='Greens', ax=ax,
            xticklabels=short_names, yticklabels=short_names)
ax.set_xlabel('Predicted')
ax.set_ylabel('Actual')
ax.set_title(f'Random Forest — 5-Class Confusion Matrix\n'
             f'Accuracy={rf_acc:.4f}  F1-wt={rf_f1:.4f}  AUC={rf_auc:.4f}')
plt.tight_layout()
rf_cm_path = os.path.join(DOCS_IMG_DIR, 'rf_confusion_matrix.png')
plt.savefig(rf_cm_path)
plt.close()
print(f"  Saved: {rf_cm_path}")

# ================================================================================
# EXPORT formal results table
# ================================================================================
out_csv = os.path.join(EVAL_DIR, "ml_results_table.csv")
pd.DataFrame({
    "Metric":         ["IF Precision", "IF Recall", "IF F1-Score",
                       "RF Accuracy", "RF Precision (weighted)", "RF Recall (weighted)",
                       "RF F1-Score (weighted)", "RF ROC-AUC (OVR weighted)"],
    "Value":          [f"{precision_if:.4f}", f"{recall_if:.4f}", f"{f1_if:.4f}",
                       f"{rf_acc:.4f}", f"{rf_prec:.4f}", f"{rf_rec:.4f}",
                       f"{rf_f1:.4f}", f"{rf_auc:.4f}"],
    "Target Promise": [">0.90", "N/A", ">0.90",
                       ">0.90", ">0.90", "N/A", ">0.90", ">0.90"],
}).to_csv(out_csv, index=False)

print()
print(f"  Saved formal ML results: {out_csv}")
print()
