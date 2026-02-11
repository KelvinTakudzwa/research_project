import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

# Configuration
DAYS = 30
INTERVAL_MINUTES = 1
TOTAL_STEPS = DAYS * 24 * 60 // INTERVAL_MINUTES
START_TIME = datetime.now() - timedelta(days=DAYS)

print(f"Generating {DAYS} days of data ({TOTAL_STEPS} rows)...")

# Lists to store data
timestamps = []
pv_voltage = []
pv_current = []
batt_voltage = []
load_current = []
temperature = []
labels = [] # 0 = Normal, 1 = Anomaly

# Simulation State
current_batt_voltage = 12.6 # Start full
battery_capacity_ah = 100
dt_hours = INTERVAL_MINUTES / 60.0

for step in range(TOTAL_STEPS):
    current_time = START_TIME + timedelta(minutes=step*INTERVAL_MINUTES)
    timestamps.append(current_time)
    
    hour = current_time.hour + current_time.minute/60.0
    
    # 1. Simulate Solar Irradiance (Parabolic curve from 6am to 6pm)
    irradiance = 0
    if 6 <= hour <= 18:
        # Peak at noon (12), width approx 6 hours either side
        # Simple parabola: -a*(x-h)^2 + k
        irradiance = max(0, 1000 * np.sin((hour - 6) * np.pi / 12)) 
        
        # Add random cloud cover noise
        if random.random() < 0.1: # 10% chance of clouds
            irradiance *= random.uniform(0.2, 0.8)
    
    # 2. PV Output (Voltage is roughly constant when sun is up, Current ~ Irradiance)
    if irradiance > 10:
        p_volts = np.random.normal(18.0, 0.5) # Approx 18V Vmp panel
        p_amps = (irradiance / 1000.0) * 5.0 # Max 5A panel
        p_amps += np.random.normal(0, 0.1) # Noise
    else:
        p_volts = np.random.normal(0.5, 0.1) # Noise at night
        p_amps = 0.0

    # Ensure non-negative
    p_amps = max(0, p_amps)
    p_volts = max(0, p_volts)
    
    pv_voltage.append(round(p_volts, 2))
    pv_current.append(round(p_amps, 2))
    
    # 3. Load Profile (Higher in evening)
    # Base load + evening peak
    base_load = 0.5 # 0.5A constant (fridge etc)
    if 18 <= hour <= 22: # Evening lights/TV
        user_load = random.uniform(1.0, 3.0) 
    else:
        user_load = random.uniform(0.0, 0.5)
        
    l_amps = base_load + user_load
    load_current.append(round(l_amps, 2))
    
    # 4. Battery Logic (Coulomb Counting)
    # Net current = Solar Input - Load Output
    # Simple model: V = V_nominal + (StateOfCharge * Coeff) - (NetCurrent * R_internal)
    net_current = p_amps - l_amps
    
    # Change in charge (Amp-hours)
    delta_ah = net_current * dt_hours
    
    # Update fake "Voltage" based on net flow (simplified lead-acid curve proxy)
    # Charge increases voltage, Discharge decreases it
    # Clamp between 11.0V (empty) and 14.4V (charging)
    
    # "Resting" change
    if net_current > 0:
        current_batt_voltage += (delta_ah * 0.05) # Charging rises fast
    else:
        current_batt_voltage += (delta_ah * 0.1) # Discharging drops
        
    # Natural bounce back or sag
    target_v = 12.7 if net_current == 0 else (14.0 if net_current > 0 else 11.5)
    current_batt_voltage = current_batt_voltage * 0.99 + target_v * 0.01 # Drift to steady state
    
    # Add noise
    current_batt_voltage += np.random.normal(0, 0.02)
    
    # Limits
    current_batt_voltage = max(10.5, min(14.8, current_batt_voltage))
    batt_voltage.append(round(current_batt_voltage, 2))
    
    # 5. Temperature (Ambient follows sun, Battery heats on high current)
    ambient = 25 - 5 * np.cos((hour - 4) * np.pi / 12) # Coldest at 4am
    batt_heat = abs(net_current) * 0.5 # I^2R heating proxy
    temp_val = ambient + batt_heat + np.random.normal(0, 0.5)
    temperature.append(round(temp_val, 2))
    
    # 6. Fault Injection (Anomaly Label)
    is_anomaly = 0
    
    # Scenario A: Shading/Dust (Low PV Current at noon)
    if 11 <= hour <= 13 and irradiance > 800 and p_amps < 1.0:
        is_anomaly = 1 # Anomaly
        
    # Scenario B: Battery degradation (Voltage drops too fast under load)
    # (Not explicitly modeled in physics here, but we can flag low voltage events)
    if current_batt_voltage < 11.0:
        is_anomaly = 1
        
    labels.append(is_anomaly)

# DataFrame
df = pd.DataFrame({
    'timestamp': timestamps,
    'pv_voltage': pv_voltage,
    'pv_current': pv_current,
    'batt_voltage': batt_voltage,
    'load_current': load_current,
    'temperature': temperature,
    'label': labels
})

# Feature Engineering
print("Adding derived features...")
# 1. Power (W) = V * I (Using PV input as primary power source)
df['pv_power_watts'] = df['pv_voltage'] * df['pv_current']

# 2. Net Energy Flux = Solar Current - Load Current
df['net_energy_flux'] = df['pv_current'] - df['load_current']

# 3. Rolling Averages (10-minute moving average of battery voltage)
df['batt_voltage_ma_10'] = df['batt_voltage'].rolling(window=10, min_periods=1).mean().round(2)

# 4. State of Charge (SoC) Estimation
# Using simple Voltage-SoC linear lookup
# V_min = 10.5V (0%), V_max = 14.4V (100%)
v_min = 10.5
v_max = 14.4
df['soc_percent'] = ((df['batt_voltage'] - v_min) / (v_max - v_min)) * 100
df['soc_percent'] = df['soc_percent'].clip(0, 100).round(2)

# Round new columns
df['pv_power_watts'] = df['pv_power_watts'].round(2)
df['net_energy_flux'] = df['net_energy_flux'].round(2)

# Save
filename = "solar_data_30days.csv"
df.to_csv(filename, index=False)
print(f"saved to {filename}")
print(df.head())
print(f"Anomalies: {df['label'].sum()} / {len(df)}")
