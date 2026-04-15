import pandas as pd
import numpy as np
import os
import random
from datetime import datetime, timedelta

"""
Chapter 4 Evaluation Suite
Script 1: simulate_f1_f5_faults.py
Generates the deterministic test dataset with ground truth labels for metrics calculation.
Table 3.4 Fault Scenarios: F1 (Shading), F2 (Overload), F3 (Deep Discharge), F4 (Offline), F5 (Sensor Dead).
"""

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
FILE_NAME = "test_dataset_f1_f5.csv"

def generate_block(fault_id, start_time, duration_mins=48):
    """Generates a block of N minutes of data centered around a specific fault type."""
    records = []
    
    # Baseline normal values (High Noon)
    base_pv_v = 18.0
    base_pv_i = 4.5
    base_batt_v = 13.2
    base_load_i = 1.0
    base_temp = 35.0
    base_lux = 90000.0
    
    for i in range(duration_mins):
        t = start_time + timedelta(minutes=i)
        
        # Add slight natural noise
        pv_v = base_pv_v + random.uniform(-0.2, 0.2)
        pv_i = base_pv_i + random.uniform(-0.1, 0.1)
        batt_v = base_batt_v + random.uniform(-0.1, 0.1)
        load_i = base_load_i + random.uniform(-0.1, 0.1)
        temp = base_temp + random.uniform(-0.5, 0.5)
        lux = base_lux + random.uniform(-2000, 2000)
        
        # Default label is 0 (Normal)
        label = 0
        
        # Apply fault logic if in the middle 20 minutes of the 48-min block
        in_fault_window = (14 <= i <= 34)
        
        if fault_id == "F1" and in_fault_window:
            # F1 Partial Shading: Lux is high, but PV current drops by 80% (0.9A)
            pv_i = 0.9 + random.uniform(-0.1, 0.1)
            label = 1
            
        elif fault_id == "F2" and in_fault_window:
            # F2 Inverter Overload: Load Current spikes to 10A, Temp rises 15C
            load_i = 10.0 + random.uniform(-0.5, 0.5)
            temp = 50.0 + random.uniform(-1, 1)
            batt_v -= 0.5 # Voltage sags under heavy load
            label = 1
            
        elif fault_id == "F3" and in_fault_window:
            # F3 Deep Discharge: Battery drops to 11.4V
            batt_v = 11.4 + random.uniform(-0.1, 0.0)
            pv_i = 0.0 # Occurs when no sun
            lux = 0.0
            label = 1
            
        elif fault_id == "F4" and in_fault_window:
            # F4 Store & Forward Outage: System goes offline (simulated later via MQTT latency)
            # For data purposes, it's normal data
            pass 
            
        elif fault_id == "F5" and in_fault_window:
            # F5 Sensor Fault / Blanking: ACS712 reports dead 0.0 at high noon
            pv_i = 0.0
            load_i = 0.0
            label = 1
            
        # Feature Engineering (must match production precisely)
        power_watts = pv_v * pv_i
        net_energy = pv_i - load_i
        
        # Contextual discriminator — same formula as generate_data.py
        current_to_lux_ratio = round((pv_i / (lux + 1)) * 1000, 4)
        
        v_min, v_max = 10.5, 14.4
        soc = ((batt_v - v_min) / (v_max - v_min)) * 100
        soc = max(0, min(100, soc)) # Clamp 0-100
        
        records.append({
            "timestamp": t.strftime("%Y-%m-%d %H:%M:%S"),
            "fault_id": fault_id,
            "pv_voltage": round(pv_v, 2),
            "pv_current": round(pv_i, 2),
            "batt_voltage": round(batt_v, 2),
            "load_current": round(load_i, 2),
            "temperature": round(temp, 2),
            "irradiance_lux": round(lux, 2),
            "pv_power_watts": round(power_watts, 2),
            "net_energy_flux": round(net_energy, 2),
            "current_to_lux_ratio": current_to_lux_ratio,
            "soc_percent": round(soc, 2),
            "label": label # GROUND TRUTH
        })
        
    return pd.DataFrame(records)

def main():
    print("Generating Deterministic F1-F5 Test Dataset...")
    start_anchor = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)
    
    blocks = []
    
    # Generate 5 discrete blocks 
    blocks.append(generate_block("NORMAL", start_anchor - timedelta(days=1)))
    blocks.append(generate_block("F1", start_anchor - timedelta(days=2)))
    blocks.append(generate_block("F2", start_anchor - timedelta(days=3)))
    blocks.append(generate_block("F3", start_anchor - timedelta(days=4)))
    blocks.append(generate_block("F4", start_anchor - timedelta(days=5)))
    blocks.append(generate_block("F5", start_anchor - timedelta(days=6)))
    
    df = pd.concat(blocks, ignore_index=True)
    
    # Fake the rolling average (rolling 10)
    # We do a rolling mean, but group by fault_id so boundaries don't leak
    df['batt_voltage_ma_10'] = df.groupby('fault_id')['batt_voltage']\
                                 .rolling(window=10, min_periods=1).mean()\
                                 .reset_index(0, drop=True).round(2)
                                 
    out_path = os.path.join(OUTPUT_DIR, FILE_NAME)
    df.to_csv(out_path, index=False)
    
    print(f"Dataset generated successfully at: {out_path}")
    print(f"Total Rows: {len(df)}")
    print(df.groupby('fault_id')['label'].sum().reset_index().rename(columns={'label': 'Anomaly Count'}))

if __name__ == "__main__":
    main()
