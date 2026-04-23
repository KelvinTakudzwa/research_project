import pandas as pd
import numpy as np
import random
import math
import argparse
import os
from datetime import datetime, timedelta

# ==========================================
# CLI Arguments (Phase 1)
# ==========================================
parser = argparse.ArgumentParser(description="Solar mini-grid data generator")
parser.add_argument(
    '--month', type=int,
    default=datetime.now().month,
    help='Target month 1-12 for seasonal calibration. Defaults to current calendar month.'
)
args = parser.parse_args()
TARGET_MONTH = args.month

# Configuration
DAYS = 365
INTERVAL_MINUTES = 1
TOTAL_STEPS = DAYS * 24 * 60 // INTERVAL_MINUTES
START_TIME = datetime.now() - timedelta(days=DAYS)

print(f"Generating {DAYS} days of data ({TOTAL_STEPS} rows)...")

# ==========================================
# Seasonal Parameter Engine
# ==========================================
def _season_label(month: int) -> str:
    labels = {
        12: "Summer/Wet",  1: "Summer/Wet",  2: "Summer/Wet",
         3: "Late Summer",
         4: "Autumn/Dry",  5: "Autumn/Dry",
         6: "Winter/Dry",  7: "Winter/Dry",  8: "Winter/Dry",
         9: "Spring/Dry",  10: "Spring/Peak", 11: "Early Summer"
    }
    return labels.get(month, "Unknown")

def get_seasonal_params(month: int) -> dict:
    """
    Derives seasonal simulation parameters via cosine interpolation.
    Zimbabwe: Southern Hemisphere subtropical highland (~17°S).
    """
    S = 0.5 * (1 + math.cos(2 * math.pi * (month - 1) / 12))

    return {
        'irr_peak':      850  + S * (1100 - 850),    
        'temp_amb_low':  7    + S * (21   - 7),       
        'temp_amb_high': 23   + S * (38   - 23),      
        'cloud_prob':    0.05 + S * (0.45 - 0.05),    
        'day_length_h':  10.5 + S * (13.5 - 10.5),   
        'month':         month,
        'season_label':  _season_label(month),
    }

params = get_seasonal_params(TARGET_MONTH)
print(f"Seasonal profile: {params['season_label']} (month {TARGET_MONTH})")
print(f"  Peak GHI: {params['irr_peak']:.0f} W/m² | "
      f"Temp: {params['temp_amb_low']:.1f}–{params['temp_amb_high']:.1f}°C | "
      f"Cloud prob: {params['cloud_prob']*100:.0f}%")

def precompute_cloud_blocks(total_steps: int, params: dict) -> set:
    cloud_steps = set()
    step = 0
    while step < total_steps:
        if random.random() < params['cloud_prob'] / 60:
            duration = random.randint(15, 45)
            for s in range(step, min(step + duration, total_steps)):
                cloud_steps.add(s)
            step += duration
        else:
            step += 1
    return cloud_steps

cloud_steps = precompute_cloud_blocks(TOTAL_STEPS, params)
cloud_depths = {s: random.uniform(0.3, 0.75) for s in cloud_steps}

# ==========================================
# Dual Temperature Model (Sensor Fusion)
# ==========================================
def compute_temperatures(hour: float, net_current: float, params: dict, current_soh: float, is_fault_f3: bool = False) -> tuple:
    T_low  = params['temp_amb_low']
    T_high = params['temp_amb_high']
    
    diurnal_frac = math.sin(math.pi * max(0, (hour - 5)) / 18)
    diurnal_frac = max(0.0, min(1.0, diurnal_frac))
    
    temp_ambient = T_low + diurnal_frac * (T_high - T_low)
    temp_ambient += np.random.normal(0, 0.3) 

    R_internal = 0.35 if is_fault_f3 else 0.08
    
    # Simulate battery aging: as SoH drops, internal resistance increases
    aging_factor = max(0, (100.0 - current_soh) / 10.0) # 0.0 at 100% SoH, 1.0 at 90% SoH
    R_internal += aging_factor * 0.15 # Up to +0.15 ohms from aging
    
    i2r_rise   = (net_current ** 2) * R_internal
    i2r_rise   = max(0.0, i2r_rise)
    
    temp_probe = temp_ambient + i2r_rise
    temp_probe += np.random.normal(0, 0.15) 

    if abs(net_current) > 0.1:
        temp_probe = max(temp_probe, temp_ambient)
    else:
        temp_probe = temp_ambient 
    
    return round(temp_ambient, 2), round(temp_probe, 2)


# Lists to store data
timestamps = []
pv_voltage = []
pv_current = []
batt_voltage = []
load_current = []
temp_ambient_log = []   
temp_probe_log   = []   
irradiance_lux = [] 
labels = [] 
soh_percents = []

# Simulation State
current_batt_voltage = 12.6 
battery_capacity_ah = 100
dt_hours = INTERVAL_MINUTES / 60.0
current_soh = 100.0

for step in range(TOTAL_STEPS):
    current_time = START_TIME + timedelta(minutes=step*INTERVAL_MINUTES)
    timestamps.append(current_time)
    
    hour = current_time.hour + current_time.minute/60.0
    
    # 1. Irradiance (Seasonal sine arch with duration clouds)
    sunrise_h = 6.0 - (params['day_length_h'] - 12) / 2
    sunset_h  = sunrise_h + params['day_length_h']

    if sunrise_h <= hour <= sunset_h:
        solar_frac = (hour - sunrise_h) / (sunset_h - sunrise_h)
        irradiance = params['irr_peak'] * math.sin(math.pi * solar_frac)
        irradiance = max(0, irradiance)
        
        if step in cloud_steps:
            irradiance *= (1 - cloud_depths[step])
    else:
        irradiance = 0.0

    irradiance += np.random.normal(0, params['irr_peak'] * 0.005)
    irradiance = max(0, irradiance)

    lux_val = irradiance * 116.0 
    irradiance_lux.append(round(max(0, lux_val), 1))
    
    # 2. PV Output
    if irradiance > 10:
        p_volts = np.random.normal(18.0, 0.5) 
        p_amps = (irradiance / 1000.0) * 5.0 
        p_amps += np.random.normal(0, 0.1) 
    else:
        p_volts = np.random.normal(0.5, 0.1) 
        p_amps = 0.0

    p_amps = max(0, p_amps)
    p_volts = max(0, p_volts)
    
    # 3. Load Profile
    base_load = 0.5 
    if 18 <= hour <= 22:
        user_load = random.uniform(1.0, 3.0) 
    else:
        user_load = random.uniform(0.0, 0.5)
        
    l_amps = base_load + user_load
    load_current.append(round(l_amps, 2))
    
    # --- SOH Degradation Simulation (Moved UP) ---
    decay_rate = 10.0 / TOTAL_STEPS
    # Add minor baseline decay 
    current_soh -= decay_rate
    current_soh += np.random.normal(0, 0.005) # Measurement noise
    
    # 4. Battery Logic
    net_current = p_amps - l_amps
    delta_ah = net_current * dt_hours
    
    # Degradation effect on capacity
    effective_capacity = battery_capacity_ah * (current_soh / 100.0)
    
    if net_current > 0:
        current_batt_voltage += (delta_ah / effective_capacity) * 5.0
    else:
        current_batt_voltage += (delta_ah / effective_capacity) * 10.0
        
    target_v = 12.7 if net_current == 0 else (14.0 if net_current > 0 else 11.5)
    
    # Voltage sag increases as SoH drops
    sag_swell = max(0, (100.0 - current_soh) * 0.03)
    if net_current > 0:
        target_v += sag_swell
    elif net_current < 0:
        target_v -= sag_swell
        
    current_batt_voltage = current_batt_voltage * 0.99 + target_v * 0.01 
    
    current_batt_voltage += np.random.normal(0, 0.02)
    current_batt_voltage = max(10.5, min(14.8, current_batt_voltage))
    batt_voltage.append(round(current_batt_voltage, 2))
    
    # 5. Fault Injection (Anomaly Label)
    is_anomaly = 0
    
    # Scenario A: Shading/Dust
    if 11 <= hour <= 13 and irradiance > 600 and random.random() < 0.05:
        p_amps *= 0.20
        is_anomaly = 1 
        
    # Scenario B: Battery degradation by voltage drop
    if current_batt_voltage < 11.0:
        is_anomaly = 1

    # Scenario C: Battery thermal degradation (elevated I²R heating)
    is_fault_f3 = False
    if irradiance > 200 and random.random() < 0.02:
        is_fault_f3 = True
        is_anomaly = 1
        
    # Finalize arrays
    pv_voltage.append(round(p_volts, 2))
    pv_current.append(round(p_amps, 2))
    labels.append(is_anomaly)

    # 6. Temperatures
    t_amb, t_probe = compute_temperatures(hour, net_current, params, current_soh, is_fault_f3=is_fault_f3)
    temp_ambient_log.append(t_amb)
    temp_probe_log.append(t_probe)

    # 7. Fault-based SOH Degradation Simulation
    if is_fault_f3 or is_anomaly:
        current_soh -= (decay_rate * 4) # Accelerated degradation during faults/thermal events
        
    current_soh = max(0.0, min(100.0, current_soh))
    soh_percents.append(round(current_soh, 2))

# DataFrame Compilation
df = pd.DataFrame({
    'timestamp':       timestamps,
    'pv_voltage':      pv_voltage,
    'pv_current':      pv_current,
    'batt_voltage':    batt_voltage,
    'load_current':    load_current,
    'temp_ambient':    temp_ambient_log,
    'temp_probe':      temp_probe_log,
    'irradiance_lux':  irradiance_lux,
    'soh_percent':     soh_percents,
    'label':           labels
})

# Feature Engineering
print("Adding derived features...")
df['pv_power_watts'] = df['pv_voltage'] * df['pv_current']
df['net_energy_flux'] = df['pv_current'] - df['load_current']
df['current_to_lux_ratio'] = (df['pv_current'] / (df['irradiance_lux'] + 1)) * 1000

df['temp_delta'] = (df['temp_probe'] - df['temp_ambient']).round(2)

df['batt_voltage_ma_10'] = df['batt_voltage'].rolling(window=10, min_periods=1).mean().round(2)

v_min = 10.5
v_max = 14.4
df['soc_percent'] = ((df['batt_voltage'] - v_min) / (v_max - v_min)) * 100
df['soc_percent'] = df['soc_percent'].clip(0, 100).round(2)

df['pv_power_watts'] = df['pv_power_watts'].round(2)
df['net_energy_flux'] = df['net_energy_flux'].round(2)
df['current_to_lux_ratio'] = df['current_to_lux_ratio'].round(4)

df = df[[
    'timestamp', 'pv_voltage', 'pv_current', 'pv_power_watts',
    'batt_voltage', 'batt_voltage_ma_10', 'soc_percent',
    'load_current', 'net_energy_flux',
    'irradiance_lux', 'current_to_lux_ratio',
    'temp_ambient', 'temp_probe', 'temp_delta',
    'soh_percent',
    'label'
]]

# Save
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
# Note: Saving alongside train_models.py standard expectation
filename = os.path.join(OUTPUT_DIR, "..", "ml_engine", "solar_data_365days.csv")
df.to_csv(filename, index=False)
print(f"Saved cleanly to {filename}")
print(df.head())
print(f"Anomalies: {df['label'].sum()} / {len(df)}")
