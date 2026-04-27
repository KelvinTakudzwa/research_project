"""
Solar Mini-Grid MQTT Simulator
Publishes the new Phase-1 sensor contract to 'solar/data' from the
365-day baseline CSV, preserving diurnal temporal integrity.

Usage:
    python mqtt_stream.py [--speed N]

    --speed N   Playback speed multiplier (default: 30).
                speed=1  → sleep(60 s) per row  — real-time (1 CSV minute = 1 real minute)
                speed=30 → sleep(2 s)  per row  — 30× speedup (default)
                speed=60 → sleep(1 s)  per row  — 60× speedup
                Formula: sleep_seconds = 60 / speed
"""

import argparse
import csv
import json
import os
import random
import ssl
import sys
import time
from datetime import datetime
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

import paho.mqtt.client as mqtt

# ── CLI ───────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description='Solar mini-grid MQTT simulator')
parser.add_argument(
    '--speed', type=float, default=30,
    help='Playback speed multiplier. speed=1=real-time (60 s/row), speed=30=2 s/row (default)'
)
args = parser.parse_args()

if args.speed <= 0:
    print('FATAL: --speed must be a positive number.')
    sys.exit(1)

SLEEP_INTERVAL = 60.0 / args.speed   # seconds to sleep between published rows

# ── Battery chemistry (Fail-Fast / Fail-Loud) ─────────────────────────────────
# Must mirror the table in backend/src/config/systemBounds.js exactly.
CHEMISTRY_TABLE = {
    'LEAD_ACID':   {'nominal_cell_v': 2.00, 'min_cell_v': 1.750},
    'AGM':         {'nominal_cell_v': 2.00, 'min_cell_v': 1.750},
    'LITHIUM':     {'nominal_cell_v': 3.20, 'min_cell_v': 2.500},
    'LIFEPO4':     {'nominal_cell_v': 3.20, 'min_cell_v': 2.500},
    'LITHIUM_ION': {'nominal_cell_v': 3.65, 'min_cell_v': 3.000},
    'NMC':         {'nominal_cell_v': 3.65, 'min_cell_v': 3.000},
}

CHEMISTRY_KEY = os.environ.get('BATTERY_CHEMISTRY', '').strip().upper()
if not CHEMISTRY_KEY or CHEMISTRY_KEY not in CHEMISTRY_TABLE:
    print('FATAL: BATTERY_CHEMISTRY not defined. Must be LITHIUM or LEAD_ACID.')
    sys.exit(1)

try:
    NOMINAL_V = float(os.environ.get('BATTERY_NOMINAL_VOLTAGE_V', '0'))
    if NOMINAL_V <= 0:
        raise ValueError
except ValueError:
    print('FATAL: BATTERY_NOMINAL_VOLTAGE_V must be a positive number (e.g. 12, 24, 48).')
    sys.exit(1)

chem       = CHEMISTRY_TABLE[CHEMISTRY_KEY]
CELL_COUNT = round(NOMINAL_V / chem['nominal_cell_v'])
DEEP_DISCHARGE_V = round(CELL_COUNT * chem['min_cell_v'], 2)

INVERTER_EFF = 0.90  # DC-to-AC inverter efficiency

print(f'[Config] Chemistry: {CHEMISTRY_KEY} | Pack: {NOMINAL_V}V | '
      f'{CELL_COUNT} cells | Deep-discharge threshold: {DEEP_DISCHARGE_V}V')
print(f'[Config] Playback speed: {args.speed}× ({SLEEP_INTERVAL:.1f} s/row)')

# ── CSV loading ───────────────────────────────────────────────────────────────
CSV_PATH = os.path.join(os.path.dirname(__file__), '..', 'ml_engine', 'solar_data_365days.csv')
daylight_rows = []
try:
    with open(CSV_PATH, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Keep only rows with meaningful irradiance (> 83 W/m² ≡ > 10 000 lux)
            if float(row['irradiance_lux']) > 10000:
                daylight_rows.append(row)
except Exception as e:
    print(f'FATAL: Could not read CSV at {CSV_PATH}: {e}')
    sys.exit(1)

print(f'[Config] Loaded {len(daylight_rows):,} daylight rows from CSV.')

# ── MQTT client ───────────────────────────────────────────────────────────────
BROKER_HOST = os.environ.get('MQTT_BROKER_HOST', 'localhost')
BROKER_PORT = int(os.environ.get('MQTT_BROKER_PORT', 8883))

# TLS: locate the CA cert relative to this script (mosquitto/certs/ca.crt in project root)
_base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CA_CERT   = os.path.join(_base_dir, 'mosquitto', 'certs', 'ca.crt')

try:
    client = mqtt.Client(
        client_id='PythonSimulator',
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        protocol=mqtt.MQTTv311
    )
except AttributeError:
    client = mqtt.Client(client_id='PythonSimulator', protocol=mqtt.MQTTv311)

if os.path.exists(CA_CERT):
    client.tls_set(ca_certs=CA_CERT, tls_version=ssl.PROTOCOL_TLSv1_2)
    print(f'[TLS] Using CA cert: {CA_CERT}')
else:
    print(f'[TLS] WARNING: CA cert not found at {CA_CERT}')
    print('      Run scripts/generate_certs.sh first, then restart.')
    sys.exit(1)

try:
    client.connect(BROKER_HOST, BROKER_PORT, 60)
    client.loop_start()
except Exception as e:
    print(f'FATAL: Could not connect to broker at {BROKER_HOST}:{BROKER_PORT}: {e}')
    sys.exit(1)

print(f'[MQTT] Connected to {BROKER_HOST}:{BROKER_PORT}')
print(f'[MQTT] Publishing to solar/data every {SLEEP_INTERVAL:.1f} s ...')
print('       Fault injection: 1 event every ~60 s (every 30 rows at default speed).')
print('       Press Ctrl-C to stop.\n')

# ── Main loop ─────────────────────────────────────────────────────────────────
fault_counter = 0
row_idx       = 0

try:
    while True:
        fault_counter += 1
        is_fault = (fault_counter % 30 == 0)

        current_row = daylight_rows[row_idx % len(daylight_rows)]
        row_idx += 1

        # Timestamp: plain current UTC time.
        # The DB uses NOW() for all inserts so this value is display-only
        # (frontend chart X-axis). No timezone conversion happens in the pipeline.
        iso_timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

        # ── B2 + B3: Field renames + irradiance unit conversion ───────────────
        pv_voltage_v      = round(float(current_row['pv_voltage']),    2)
        pv_current_a      = round(float(current_row['pv_current']),    2)
        battery_voltage_v = round(float(current_row['batt_voltage']),  2)
        ambient_temp_c    = round(float(current_row['temp_ambient']),  2)
        battery_temp_c    = round(float(current_row['temp_probe']),    2)
        irradiance_wm2    = round(float(current_row['irradiance_lux']) / 120.0, 2)

        # Raw DC draw from CSV (inverter input side)
        load_current = float(current_row['load_current'])

        # ── B5: AC subsystem (PZEM-004T synthesis) ───────────────────────────
        # ac_power_w is the actual AC output after inverter conversion loss.
        ac_power_w      = round(load_current * battery_voltage_v * INVERTER_EFF, 2)
        ac_voltage_v    = round(230.0 + random.uniform(-2.0, 2.0),    2)
        ac_power_factor = round(random.uniform(0.82, 0.95),            3)
        ac_current_a    = round(ac_power_w / (ac_voltage_v * ac_power_factor), 3)

        # ── B4: battery_current_a — thermodynamically correct ────────────────
        # The inverter draws MORE from the battery than it delivers to the AC
        # side because of heat loss:
        #   DC draw = ac_power_w / (batt_voltage * eff)
        # Substituting:
        #   DC draw = (load_current * batt_voltage * eff) / (batt_voltage * eff)
        #           = load_current          ← clean simplification
        # Positive → charging (PV surplus); Negative → discharging (load > PV).
        battery_current_a = round(pv_current_a - load_current, 2)

        # ── B6: Fault injection (chemistry-aware thresholds) ──────────────────
        fault_name = None
        if is_fault:
            fault_cycle = int((fault_counter / 30) % 4)

            if fault_cycle == 1:
                # F1: Partial Shading — PV current collapses while irradiance stays HIGH.
                # This is the defining physics violation: sun is shining on the panel
                # but shaded cells block current flow. Do NOT reduce irradiance —
                # the high irr + near-zero current mismatch is exactly what the IF
                # flags and what the RF was trained to recognise as F1.
                pv_current_a      = round(0.9 + random.uniform(-0.1, 0.1), 2)
                battery_current_a = round(pv_current_a - load_current, 2)
                fault_name = 'F1 Partial Shading'

            elif fault_cycle == 2:
                # F2: Inverter Overload — AC load spikes; PZEM-004T detects it
                ac_power_w      = round(ac_power_w * 2.5, 2)
                battery_temp_c  = round(battery_temp_c + 20.0, 2)
                battery_voltage_v = round(battery_voltage_v - 0.5, 2)
                # Recompute consistent dependent fields
                overload_dc_draw  = ac_power_w / max(battery_voltage_v * INVERTER_EFF, 0.01)
                battery_current_a = round(pv_current_a - overload_dc_draw, 2)
                ac_current_a      = round(ac_power_w / (ac_voltage_v * ac_power_factor), 3)
                fault_name = 'F2 Inverter Overload'

            elif fault_cycle == 3:
                # F3: Deep Discharge — voltage falls below chemistry threshold
                battery_voltage_v = round(DEEP_DISCHARGE_V - 0.2, 2)
                pv_current_a      = 0.0
                irradiance_wm2    = 0.0
                ac_power_w        = round(ac_power_w * 0.3, 2)   # inverter throttles
                throttle_dc_draw  = ac_power_w / max(battery_voltage_v * INVERTER_EFF, 0.01)
                battery_current_a = round(0.0 - throttle_dc_draw, 2)  # discharging only
                ac_current_a      = round(ac_power_w / (ac_voltage_v * ac_power_factor), 3)
                fault_name = 'F3 Deep Discharge'

            elif fault_cycle == 0:
                # F5: Sensor Dead — generation and load readings go to zero
                pv_current_a      = 0.0
                ac_power_w        = 0.0
                ac_current_a      = 0.0
                battery_current_a = 0.0
                fault_name = 'F5 Sensor Dead'

        # ── Assemble payload ──────────────────────────────────────────────────
        payload = {
            'pv_voltage_v':      pv_voltage_v,
            'pv_current_a':      pv_current_a,
            'battery_voltage_v': battery_voltage_v,
            'battery_current_a': battery_current_a,
            'ac_voltage_v':      ac_voltage_v,
            'ac_current_a':      ac_current_a,
            'ac_power_w':        ac_power_w,
            'ac_power_factor':   ac_power_factor,
            'irradiance_wm2':    irradiance_wm2,
            'ambient_temp_c':    ambient_temp_c,
            'battery_temp_c':    battery_temp_c,
            'timestamp':         iso_timestamp,
            'is_offline_buffered': False,
        }

        if fault_name:
            print(f'\n[FAULT INJECTED] {fault_name}')
            print(f'  batt={battery_voltage_v}V  pv={pv_current_a}A  '
                  f'ac={ac_power_w}W  batt_i={battery_current_a}A')
        else:
            print(f'[OK] {iso_timestamp}  '
                  f'batt={battery_voltage_v}V ({battery_current_a:+.2f}A)  '
                  f'pv={pv_current_a}A  ac={ac_power_w}W  irr={irradiance_wm2}W/m²')

        client.publish('solar/data', json.dumps(payload), qos=1)
        time.sleep(SLEEP_INTERVAL)

except KeyboardInterrupt:
    print('\n[Simulator] Stopped.')
    client.disconnect()
