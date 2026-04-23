import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt

"""
Chapter 4 Evaluation Suite — Pipeline Sub-package
Script 2: evaluate_pipeline.py

Reads f4_outage_log.csv produced by simulate_f4_outage.py and computes
the formal pipeline reliability metrics for thesis Section 4.x.3:

  - PDR     (Packet Delivery Ratio)
  - Mean End-to-End Latency (ms)
  - Latency Jitter (std deviation, ms)
  - Store-and-Forward Recovery Rate (OUTAGE-phase packets re-delivered)

Produces:
  - pipeline_results_table.csv
  - docs/images/f4_latency_profile.png
"""

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
EVAL_DIR     = os.path.dirname(SCRIPT_DIR)          # evaluation/
DOCS_IMG_DIR = os.path.join(EVAL_DIR, "..", "docs", "images")
os.makedirs(DOCS_IMG_DIR, exist_ok=True)

LOG_PATH = os.path.join(EVAL_DIR, "f4_outage_log.csv")

# ── 1. Load Log ───────────────────────────────────────────────────────────────
try:
    df = pd.read_csv(LOG_PATH)
except FileNotFoundError:
    print(f"[ERROR] Log not found: {LOG_PATH}")
    print("        Run evaluation/pipeline/simulate_f4_outage.py first.")
    exit(1)

mode = df['mode'].iloc[0]   # LIVE or SYNTHETIC

print()
print("=" * 60)
print("  Pipeline Evaluation — F4 MQTT QoS 1 Reliability Metrics")
print(f"  Test Mode : {mode}")
print("=" * 60)

# ── 2. Core Metrics ───────────────────────────────────────────────────────────
total_sent   = len(df)
total_deliv  = df['delivered'].sum()
pdr_percent  = (total_deliv / total_sent) * 100

# Latency stats (exclude undelivered packets which have NaN latency)
delivered_df    = df[df['delivered'] == 1].copy()
mean_latency_ms = delivered_df['latency_ms'].mean()
jitter_ms       = delivered_df['latency_ms'].std()

# Store-and-Forward recovery: packets sent during OUTAGE phase that were
# still delivered (QoS 1 re-delivery on reconnect).
outage_df    = df[df['phase'] == 'OUTAGE']
outage_sent  = len(outage_df)
outage_deliv = outage_df['delivered'].sum()
sf_recovery_rate = (outage_deliv / outage_sent * 100) if outage_sent > 0 else 100.0

print(f"\n  Packet Delivery Ratio        : {pdr_percent:.1f}%       (Target: 100%)")
print(f"  Total Sent / Delivered       : {total_sent} / {total_deliv}")
print(f"  Mean End-to-End Latency      : {mean_latency_ms:.2f} ms  (Target: <30,000 ms)")
print(f"  Latency Jitter (std dev)     : {jitter_ms:.2f} ms")
print(f"  Store-and-Forward Recovery   : {sf_recovery_rate:.1f}%       (OUTAGE-phase re-delivery)")

# ── 3. Per-Phase Breakdown ────────────────────────────────────────────────────
print()
print("  Per-Phase Breakdown:")
phase_summary = (
    df.groupby('phase')
      .agg(
          Sent=('delivered', 'count'),
          Delivered=('delivered', 'sum'),
          Mean_Latency_ms=('latency_ms', 'mean'),
      )
      .round(2)
      .reset_index()
)
phase_summary['PDR (%)'] = (phase_summary['Delivered'] / phase_summary['Sent'] * 100).round(1)
print(phase_summary.to_string(index=False))

# ── 4. Latency Profile Chart ──────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(10, 5))

colors = {'NORMAL': '#2ca02c', 'OUTAGE': '#d62728', 'RECOVERY': '#ff7f0e'}
for phase, grp in delivered_df.groupby('phase'):
    ax.scatter(
        grp['packet_id'], grp['latency_ms'],
        label=phase, color=colors.get(phase, '#7f7f7f'),
        s=50, zorder=3,
    )

ax.axvspan(25, 36, alpha=0.1, color='red',    label='Outage Window')
ax.axvspan(37, 48, alpha=0.1, color='orange', label='Recovery Window')
ax.axhline(y=30000, color='red', linestyle='--', linewidth=0.8, label='30 s SLA Limit')

ax.set_xlabel('Packet ID')
ax.set_ylabel('End-to-End Latency (ms)')
ax.set_title(f'F4 MQTT QoS 1 — Latency Profile [{mode} Test]\n'
             f'PDR: {pdr_percent:.1f}% | Mean Latency: {mean_latency_ms:.2f} ms')
ax.legend(loc='upper right')
ax.grid(True, alpha=0.3)
plt.tight_layout()

chart_path = os.path.join(DOCS_IMG_DIR, 'f4_latency_profile.png')
plt.savefig(chart_path)
plt.close()
print(f"\n  Saved chart : {chart_path}")

# ── 5. Export Formal Results ──────────────────────────────────────────────────
out_csv = os.path.join(EVAL_DIR, "pipeline_results_table.csv")
pd.DataFrame({
    "Metric": [
        "PDR (%)",
        "Mean E2E Latency (ms)",
        "Latency Jitter (ms)",
        "Store-and-Forward Recovery (%)",
        "Test Mode",
    ],
    "Value": [
        f"{pdr_percent:.1f}",
        f"{mean_latency_ms:.2f}",
        f"{jitter_ms:.2f}",
        f"{sf_recovery_rate:.1f}",
        mode,
    ],
    "Target Promise": [
        "100%",
        "<30,000 ms",
        "N/A",
        "100%",
        "LIVE preferred",
    ],
}).to_csv(out_csv, index=False)

print(f"  Saved table : {out_csv}")
print()
