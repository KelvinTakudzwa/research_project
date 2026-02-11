import sys
import json
import pickle
import pandas as pd
import numpy as np
import os

# Configuration
MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')

# Load Models (Global to avoid reloading on every call if checking via direct shell, 
# but for CLI args we verify each time)
# Note: In a high-scale production, we'd wrap this in a Flask microservice.
# For this prototype, loading pickle per request is acceptable (latency ~0.5s).

def load_models():
    try:
        with open(f"{MODEL_DIR}/rf_model.pkl", 'rb') as f:
            rf = pickle.load(f)
        with open(f"{MODEL_DIR}/if_model.pkl", 'rb') as f:
            iso = pickle.load(f)
        return rf, iso
    except Exception as e:
        return None, None

def predict(data_packet):
    rf_model, if_model = load_models()
    
    if not rf_model or not if_model:
        return {"error": "Models not found"}

    # Prepare DataFrame matching training shape
    # Expected keys: pv_voltage, pv_current, batt_voltage, load_current, temperature,
    #                pv_power_watts, net_energy_flux, batt_voltage_ma_10, soc_percent
    
    # We must ensure feature order matches training exactly
    feature_cols = [
        'pv_voltage', 'pv_current', 'batt_voltage', 'load_current', 'temperature',
        'pv_power_watts', 'net_energy_flux', 'batt_voltage_ma_10', 'soc_percent'
    ]
    
    # Create DF
    df = pd.DataFrame([data_packet])
    
    # Ensure all columns exist (fill 0 if missing, though Node.js should provide all)
    for col in feature_cols:
        if col not in df.columns:
            df[col] = 0
            
    # Select ordered features
    X = df[feature_cols]

    # 1. Random Forest Prediction (Health Class)
    rf_pred = rf_model.predict(X)[0] # 0 = Normal, 1 = Anomaly
    
    # 2. Isolation Forest Prediction (Outlier Check)
    # IF returns 1 for Inlier (Normal), -1 for Outlier
    if_pred = if_model.predict(X)[0] 
    is_outlier = True if if_pred == -1 else False

    # Logic: If RF says Anomaly OR IF says Outlier -> Flag it
    # We prioritize RF for specific labels if we had multiclass, 
    # but here 1=Anomaly.
    
    final_status = "Normal"
    if rf_pred == 1:
        final_status = "Known_Fault"
    elif is_outlier:
        final_status = "Unknown_Anomaly"

    return {
        "status": final_status,
        "rf_pred": int(rf_pred),
        "is_outlier": bool(is_outlier)
    }

if __name__ == "__main__":
    # Input: JSON string as first argument
    try:
        raw_json = sys.argv[1]
        data = json.loads(raw_json)
        result = predict(data)
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
