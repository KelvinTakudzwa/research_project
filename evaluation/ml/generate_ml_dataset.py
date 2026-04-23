import pandas as pd
import numpy as np
import os
import random
import csv
from datetime import datetime, timedelta

"""
Chapter 4 Evaluation Suite — ML Sub-package
Script 1: generate_ml_dataset.py

Generates the deterministic test dataset with ground-truth labels for ML metrics
calculation. Covers Table 3.4 Fault Scenarios that are sensor-observable:
  F1 — Partial Shading
  F2 — Inverter Overload
  F3 — Deep Discharge
  F5 — Sensor Dead (blanking)

NOTE: F4 (Store-and-Forward / Network Outage) is intentionally excluded here.
F4 is a network-layer fault; its sensor readings are physically Normal and
carry zero signal for the ML models. F4 is evaluated in evaluation/pipeline/.
"""

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
EVAL_DIR   = os.path.dirname(OUTPUT_DIR)          # evaluation/
FILE_NAME  = "ml_test_dataset.csv"

# Load realistic daylight rows from the 365-day baseline CSV.
# These provide physics-accurate baselines that prevent IF from flagging
# artificial noise in the Normal windows.
CSV_PATH = os.path.join(OUTPUT_DIR, "..", "..", "ml_engine", "solar_data_365days.csv")

try:
    with open(CSV_PATH, 'r') as f:
        reader = csv.DictReader(f)
        daylight_rows = [r for r in reader if float(r['irradiance_lux']) > 10000]
except FileNotFoundError:
    print(f"[ERROR] Baseline CSV not found: {CSV_PATH}")
    exit(1)


def generate_block(fault_id: str, start_time: datetime, duration_mins: int = 48) -> pd.DataFrame:
    """
    Generates a contiguous block of `duration_mins` minutes of sensor data
    centred around a specific fault type.

    Fault window: minutes 14–34 of the 48-minute block (middle 20 minutes).
    Pre- and post-fault windows are clean Normal data from the baseline CSV.

    Returns a DataFrame with full feature engineering matching production.
    """
    records = []

    # Draw a contiguous slice of real daylight data so baseline physics are
    # preserved exactly — this prevents IF from flagging the Normal windows.
    start_idx = random.randint(0, len(daylight_rows) - duration_mins - 1)

    for i in range(duration_mins):
        t   = start_time + timedelta(minutes=i)
        row = daylight_rows[start_idx + i]

        # ── Baseline values from real physics ──────────────────────────────
        pv_v         = float(row['pv_voltage'])
        pv_i         = float(row['pv_current'])
        batt_v       = float(row['batt_voltage'])
        load_i       = float(row['load_current'])
        temp_ambient = float(row['temp_ambient'])
        temp_probe   = float(row['temp_probe'])
        lux          = float(row['irradiance_lux'])
        soh_percent  = float(row.get('soh_percent', 100.0))

        label = 0   # Default: Normal

        # ── Fault injection (middle 20 minutes only) ────────────────────────
        in_fault_window = (14 <= i <= 34)

        if fault_id == "F1" and in_fault_window:
            # Partial Shading: irradiance remains high but PV current collapses.
            # This is the "invisible" fault that static threshold systems miss
            # (Section 3.x.2 of thesis).
            pv_i  = 0.9 + random.uniform(-0.1, 0.1)
            label = 1

        elif fault_id == "F2" and in_fault_window:
            # Inverter Overload: load current spikes, temperature rises,
            # battery drains slightly.
            load_i     = 10.0 + random.uniform(-0.5, 0.5)
            temp_probe = 50.0 + random.uniform(-1.0, 1.0)
            batt_v    -= 0.5
            label      = 1

        elif fault_id == "F3" and in_fault_window:
            # Deep Discharge: battery voltage drops below safe threshold,
            # system goes dark (no PV generation, no irradiance).
            batt_v = 11.4 + random.uniform(-0.1, 0.0)
            pv_i   = 0.0
            lux    = 0.0
            label  = 1

        elif fault_id == "F5" and in_fault_window:
            # Sensor Dead / Blanking: current sensors report 0.0 while
            # irradiance is still high — the "silent failure" scenario.
            pv_i   = 0.0
            load_i = 0.0
            label  = 1

        # ── Feature Engineering (must match production pipeline exactly) ────
        power_watts         = pv_v * pv_i
        net_energy          = pv_i - load_i
        current_to_lux_ratio = round((pv_i / (lux + 1)) * 1000, 4)

        v_min, v_max = 10.5, 14.4
        soc = ((batt_v - v_min) / (v_max - v_min)) * 100
        soc = max(0.0, min(100.0, soc))

        records.append({
            "timestamp":          t.strftime("%Y-%m-%d %H:%M:%S"),
            "fault_id":           fault_id,
            "pv_voltage":         round(pv_v, 2),
            "pv_current":         round(pv_i, 2),
            "batt_voltage":       round(batt_v, 2),
            "load_current":       round(load_i, 2),
            "temp_ambient":       round(temp_ambient, 2),
            "temp_probe":         round(temp_probe, 2),
            "temp_delta":         round(temp_probe - temp_ambient, 2),
            "irradiance_lux":     round(lux, 2),
            "pv_power_watts":     round(power_watts, 2),
            "net_energy_flux":    round(net_energy, 2),
            "current_to_lux_ratio": current_to_lux_ratio,
            "soh_percent":        round(soh_percent, 2),
            "soc_percent":        round(soc, 2),
            "label":              label,
        })

    return pd.DataFrame(records)


def main():
    print("=" * 60)
    print("  ML Evaluation — Generating F1/F2/F3/F5 Test Dataset")
    print("=" * 60)
    print("NOTE: F4 (Network Outage) is excluded — see evaluation/pipeline/")
    print()

    start_anchor = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)

    blocks = [
        generate_block("NORMAL", start_anchor - timedelta(days=1)),
        generate_block("F1",     start_anchor - timedelta(days=2)),
        generate_block("F2",     start_anchor - timedelta(days=3)),
        generate_block("F3",     start_anchor - timedelta(days=4)),
        generate_block("F5",     start_anchor - timedelta(days=5)),
    ]

    df = pd.concat(blocks, ignore_index=True)

    # Rolling 10-minute moving average of battery voltage, grouped by fault_id
    # to prevent boundary leakage between blocks.
    df['batt_voltage_ma_10'] = (
        df.groupby('fault_id')['batt_voltage']
          .rolling(window=10, min_periods=1)
          .mean()
          .reset_index(0, drop=True)
          .round(2)
    )

    out_path = os.path.join(EVAL_DIR, "ml_test_dataset.csv")
    df.to_csv(out_path, index=False)

    print(f"Dataset saved: {out_path}")
    print(f"Total rows:    {len(df)}")
    print()
    print(df.groupby('fault_id')['label']
            .agg(Total='count', Anomaly_Rows='sum')
            .reset_index()
            .to_string(index=False))


if __name__ == "__main__":
    main()
