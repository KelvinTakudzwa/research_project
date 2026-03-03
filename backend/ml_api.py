from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pickle
import pandas as pd
import os

app = FastAPI(title="Solar ML API", description="Microservice for predicting solar mini-grid anomalies.")

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')

# Load Models globally on startup (improves latency significantly)
try:
    with open(f"{MODEL_DIR}/rf_model.pkl", 'rb') as f:
        rf_model = pickle.load(f)
    print("Random Forest model loaded.")
except Exception as e:
    rf_model = None
    print(f"Error loading RF model: {e}")

try:
    with open(f"{MODEL_DIR}/if_model.pkl", 'rb') as f:
        if_model = pickle.load(f)
    print("Isolation Forest model loaded.")
except Exception as e:
    if_model = None
    print(f"Error loading IF model: {e}")

# Pydantic schema for incoming sensor data
class SensorData(BaseModel):
    pv_voltage: float
    pv_current: float
    batt_voltage: float
    load_current: float
    temperature: float
    pv_power_watts: float
    net_energy_flux: float
    batt_voltage_ma_10: float
    soc_percent: float

@app.get("/")
def read_root():
    return {"status": "ML API is running."}

@app.post("/predict")
def predict_anomaly(data: SensorData):
    if not rf_model or not if_model:
        raise HTTPException(status_code=500, detail="Models not loaded properly.")

    # Prepare DataFrame matching training shape
    feature_cols = [
        'pv_voltage', 'pv_current', 'batt_voltage', 'load_current', 'temperature',
        'pv_power_watts', 'net_energy_flux', 'batt_voltage_ma_10', 'soc_percent'
    ]
    
    # Create DataFrame from request body
    df = pd.DataFrame([data.model_dump()])
    
    # Select ordered features (just to be safe)
    X = df[feature_cols]

    # 1. Random Forest Prediction (Health Class)
    rf_pred = rf_model.predict(X)[0] # 0 = Normal, 1 = Anomaly
    
    # 2. Isolation Forest Prediction (Outlier Check)
    # IF returns 1 for Inlier (Normal), -1 for Outlier
    if_pred = if_model.predict(X)[0] 
    is_outlier = True if if_pred == -1 else False

    # Logic: If RF says Anomaly OR IF says Outlier -> Flag it
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
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
