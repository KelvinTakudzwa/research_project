"""
Chapter 4 Evaluation Suite - ML Sub-package
Script 1: generate_ml_dataset.py

Generates the deterministic test dataset with ground-truth labels for ML metrics
calculation. Covers Table 3.4 Fault Scenarios that are sensor-observable:
  F1 - Partial Shading
  F2 - Inverter Overload
  F3 - Deep Discharge
  F5 - Sensor Dead (blanking)

NOTE: F4 (Store-and-Forward / Network Outage) is intentionally excluded here.
F4 is a network-layer fault; its sensor readings are physically Normal and
carry zero signal for the ML models. F4 is evaluated in evaluation/pipeline/.

Output columns include BOTH raw physical values (for the static threshold
baseline in baseline_comparison.py) AND the 15 normalized features the ML
models were trained on (for evaluate_ml_models.py and baseline_comparison.py).
"""

import pandas as pd
import numpy as np
import os
import random
import csv
from datetime import datetime, timedelta
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# Seed for reproducible dataset — locks in Chapter 5 results across runs.
random.seed(42)
np.random.seed(42)

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
EVAL_DIR   = os.path.dirname(OUTPUT_DIR)
CSV_PATH   = os.path.join(OUTPUT_DIR, "..", "..", "ml_engine", "solar_data_365days.csv")

# ── Bounds (mirror systemBounds.js + train_models.py) ────────────────────────
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

CHEMISTRY_TABLE = {
    'LEAD_ACID':   {'nominal_cell_v': 2.00, 'min_cell_v': 1.750, 'max_cell_v': 2.115, 'bulk_cell_v': 2.400},
    'AGM':         {'nominal_cell_v': 2.00, 'min_cell_v': 1.750, 'max_cell_v': 2.115, 'bulk_cell_v': 2.350},
    'LITHIUM':     {'nominal_cell_v': 3.20, 'min_cell_v': 2.500, 'max_cell_v': 3.350, 'bulk_cell_v': 3.650},
    'LIFEPO4':     {'nominal_cell_v': 3.20, 'min_cell_v': 2.500, 'max_cell_v': 3.350, 'bulk_cell_v': 3.650},
    'LITHIUM_ION': {'nominal_cell_v': 3.65, 'min_cell_v': 3.000, 'max_cell_v': 4.000, 'bulk_cell_v': 4.200},
    'NMC':         {'nominal_cell_v': 3.65, 'min_cell_v': 3.000, 'max_cell_v': 4.000, 'bulk_cell_v': 4.200},
}
CHEM_KEY = os.environ.get('BATTERY_CHEMISTRY', 'LEAD_ACID').upper()
chem       = CHEMISTRY_TABLE.get(CHEM_KEY, CHEMISTRY_TABLE['LEAD_ACID'])
cells      = round(NOMINAL_V / chem['nominal_cell_v'])
V_MIN_SOC  = cells * chem['min_cell_v']    # 0% SoC
V_MAX_SOC  = cells * chem['max_cell_v']    # 100% SoC
MAX_BATT_V = cells * chem['bulk_cell_v']   # normalization bound
DEEP_DISCHARGE_V = V_MIN_SOC               # deterministic alarm threshold

INVERTER_EFF = 0.90
AC_PF_AVG    = 0.88

try:
    with open(CSV_PATH, 'r') as f:
        reader = csv.DictReader(f)
        daylight_rows = [r for r in reader if float(r['irradiance_lux']) > 10000]
except FileNotFoundError:
    print(f"[ERROR] Baseline CSV not found: {CSV_PATH}")
    raise SystemExit(1)


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _normalize(rec):
    """Compute the 15 normalized features from raw physical values."""
    batt_v  = rec['battery_voltage_v']
    pv_v    = rec['pv_voltage_v']
    pv_i    = rec['pv_current_a']
    batt_i  = rec['battery_current_a']
    ac_p    = rec['ac_power_w']
    ac_i    = rec['ac_current_a']
    irr     = rec['irradiance_wm2']
    pv_p    = rec['pv_power_w']
    batt_p  = batt_v * batt_i
    net_p   = pv_p - ac_p

    soc = _clamp(((batt_v - V_MIN_SOC) / (V_MAX_SOC - V_MIN_SOC)) * 100, 0, 100)

    return {
        'pv_voltage_norm':      pv_v   / MAX_PV_V,
        'pv_current_norm':      pv_i   / MAX_PV_I,
        'pv_power_norm':        pv_p   / MAX_PV_P,
        'battery_voltage_norm': batt_v / MAX_BATT_V,
        'battery_current_norm': batt_i / MAX_BATT_I,
        'battery_power_norm':   batt_p / MAX_PV_P,
        'ac_power_norm':        ac_p   / MAX_AC_P,
        'ac_current_norm':      ac_i   / MAX_AC_I,
        'net_flux_norm':        net_p  / MAX_PV_P,
        'irradiance_norm':      irr    / MAX_IRR,
        'soc_percent':          round(soc, 2),
        'ac_power_factor':      AC_PF_AVG,
        'ambient_temp_c':       rec['ambient_temp_c'],
        'battery_temp_c':       rec['battery_temp_c'],
        'temp_delta_c':         rec['temp_delta_c'],
    }


def generate_block(fault_id: str, start_time: datetime, duration_mins: int = 48) -> pd.DataFrame:
    """
    Generates a contiguous block of `duration_mins` minutes of sensor data
    centred around a specific fault type.

    Fault window: minutes 14-34 (middle 20 minutes).
    Pre- and post-fault windows are clean Normal data from the baseline CSV.
    """
    records = []
    start_idx = random.randint(0, len(daylight_rows) - duration_mins - 1)

    for i in range(duration_mins):
        t   = start_time + timedelta(minutes=i)
        row = daylight_rows[start_idx + i]

        # Baseline physical values from real CSV
        pv_v         = float(row['pv_voltage'])
        pv_i         = float(row['pv_current'])
        batt_v       = float(row['batt_voltage'])
        load_i       = float(row['load_current'])
        ambient_temp = float(row['temp_ambient'])
        battery_temp = float(row['temp_probe'])
        lux          = float(row['irradiance_lux'])
        soh_pct      = float(row.get('soh_percent', 100.0))

        label = 0

        in_fault_window = (14 <= i <= 34)

        if fault_id == "F1" and in_fault_window:
            # Partial Shading: irradiance stays high but PV current collapses.
            # 0.3A → norm ≈ 0.018 — matches training range [0.01, 0.04] and simulator.
            pv_i  = 0.3 + random.uniform(-0.05, 0.05)
            label = 1

        elif fault_id == "F2" and in_fault_window:
            # Inverter Overload: AC load spikes (PZEM detects it).
            # Set load_i to 2.5x so ac_power_w = load_i * batt_v * eff spikes.
            load_i       = load_i * 2.5 + random.uniform(-0.2, 0.2)
            battery_temp = battery_temp + 20.0 + random.uniform(-1.0, 1.0)
            batt_v       = batt_v - 0.5
            label        = 1

        elif fault_id == "F3" and in_fault_window:
            # Deep Discharge: battery drops below chemistry-specific threshold.
            batt_v = DEEP_DISCHARGE_V - 0.2 + random.uniform(-0.05, 0.0)
            pv_i   = 0.0
            lux    = 0.0
            load_i = load_i * 0.3   # inverter throttles
            label  = 1

        elif fault_id == "F5" and in_fault_window:
            # Sensor Dead: current sensors blank while irradiance is still high.
            pv_i   = 0.0
            load_i = 0.0
            label  = 1

        # Derive AC subsystem (same as mqtt_stream.py + train_models.py)
        ac_power_w   = round(load_i * batt_v * INVERTER_EFF, 4)
        ac_current_a = round(ac_power_w / (230.0 * AC_PF_AVG), 4)
        batt_i       = round(pv_i - load_i, 4)
        pv_power_w   = round(pv_v * pv_i, 4)
        irr_wm2      = round(lux / 120.0, 4)
        temp_delta   = round(battery_temp - ambient_temp, 2)

        raw = {
            # Raw physical fields (used by static threshold baseline)
            'timestamp':        t.strftime("%Y-%m-%d %H:%M:%S"),
            'fault_id':         fault_id,
            'pv_voltage_v':     round(pv_v, 2),
            'pv_current_a':     round(pv_i, 2),
            'pv_power_w':       round(pv_power_w, 2),
            'battery_voltage_v': round(batt_v, 2),
            'battery_current_a': round(batt_i, 2),
            'ac_power_w':       round(ac_power_w, 2),
            'ac_current_a':     round(ac_current_a, 4),
            'ac_power_factor':  AC_PF_AVG,
            'irradiance_wm2':   round(irr_wm2, 2),
            'ambient_temp_c':   round(ambient_temp, 2),
            'battery_temp_c':   round(battery_temp, 2),
            'temp_delta_c':     temp_delta,
            'soh_percent':      round(soh_pct, 2),
            'label':            label,
        }

        # Add normalized ML features
        norm = _normalize({**raw, 'pv_power_w': pv_power_w})
        records.append({**raw, **norm})

    return pd.DataFrame(records)


def main():
    print("=" * 60)
    print("  ML Evaluation - Generating F1/F2/F3/F5 Test Dataset")
    print(f"  Chemistry: {CHEM_KEY} / {NOMINAL_V}V / {cells} cells")
    print(f"  Deep-discharge threshold: {DEEP_DISCHARGE_V}V")
    print("=" * 60)
    print("NOTE: F4 (Network Outage) excluded - see evaluation/pipeline/")
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

    out_path = os.path.join(EVAL_DIR, "ml_test_dataset.csv")
    df.to_csv(out_path, index=False)

    print(f"Dataset saved : {out_path}")
    print(f"Total rows    : {len(df)}")
    print(f"Columns       : {len(df.columns)}")
    print()
    print(df.groupby('fault_id')['label']
            .agg(Total='count', Anomaly_Rows='sum')
            .reset_index()
            .to_string(index=False))


if __name__ == "__main__":
    main()
