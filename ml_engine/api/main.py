from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import pickle
import pandas as pd
import os
import threading
from apscheduler.schedulers.background import BackgroundScheduler
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'jobs'))
from retrainer import retrain_isolation_forest

app = FastAPI(title="Solar ML API", description="Microservice for predicting solar mini-grid anomalies.")

MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', 'models')

# Global Thread Lock to prevent prediction crashes during hot-swaps
model_lock = threading.Lock()

def load_models():
    """Dynamically loads or reloads the ML models from disk"""
    global rf_model, if_model
    with model_lock:
        print("[ML_API] Loading models from disk...")
        try:
            with open(f"{MODEL_DIR}/rf_model.pkl", 'rb') as f:
                rf_model = pickle.load(f)
            print("[ML_API] Random Forest model loaded.")
        except Exception as e:
            rf_model = None
            print(f"[ML_API] Error loading RF model: {e}")

        try:
            with open(f"{MODEL_DIR}/if_model.pkl", 'rb') as f:
                if_model = pickle.load(f)
            print("[ML_API] Isolation Forest model loaded.")
        except Exception as e:
            if_model = None
            print(f"[ML_API] Error loading IF model: {e}")

# Initial load on startup
load_models()

# Pydantic schema for incoming sensor data
class SensorData(BaseModel):
    pv_voltage: float
    pv_current: float
    batt_voltage: float
    load_current: float
    temp_ambient: float
    temp_probe: float
    irradiance_lux: float
    pv_power_watts: float
    net_energy_flux: float
    batt_voltage_ma_10: float
    soc_percent: float
    # Derived by server.js before forwarding — the key contextual discriminator
    current_to_lux_ratio: float = 0.0

@app.get("/")
def read_root():
    return {"status": "ML API is running."}

# ==========================================================
# RETRAINING PIPELINE (Background Task preventing event-loop blocks)
# ==========================================================
def background_training_task():
    """Runs the CPU-heavy Scikit-learn fit off the main event loop"""
    success = retrain_isolation_forest()
    if success:
        # Hot-reload the new model dynamically into memory!
        load_models()

@app.post("/trigger_retraining")
def trigger_retraining(background_tasks: BackgroundTasks):
    """Manual endpoint for demonstration / admin force-retrain"""
    print("[ML_API] Manual retraining triggered.")
    background_tasks.add_task(background_training_task)
    return {"status": "Accepted", "message": "Retraining started in the background."}

# ==========================================================
# SCHEDULER (APScheduler handles the 7-day periodic logic)
# ==========================================================
scheduler = BackgroundScheduler()
# Run background_training_task every 7 days quietly inside this process
scheduler.add_job(background_training_task, 'interval', days=7)
scheduler.start()

# Shutdown handler for scheduler
@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()

@app.post("/predict")
def predict_anomaly(data: SensorData):
    # Engage Thread Lock for predictions
    with model_lock:
        if not rf_model or not if_model:
            raise HTTPException(status_code=500, detail="Models not loaded properly.")

        # Prepare DataFrame matching training shape
        feature_cols = [
            'pv_voltage', 'pv_current', 'pv_power_watts', 'batt_voltage', 
            'batt_voltage_ma_10', 'soc_percent', 'load_current', 'net_energy_flux',
            'irradiance_lux', 'current_to_lux_ratio',
            'temp_ambient', 'temp_probe', 'temp_delta'
        ]
        
        # Create DataFrame from request body
        df = pd.DataFrame([data.model_dump()])
        
        # Calculate live if not provided by sender (belt-and-suspenders)
        if 'current_to_lux_ratio' not in df.columns or df['current_to_lux_ratio'].iloc[0] == 0.0:
            df['current_to_lux_ratio'] = (df['pv_current'] / (df['irradiance_lux'] + 1)) * 1000
            
        # Dynamically calculate sensor fusion metric
        df['temp_delta'] = (df['temp_probe'] - df['temp_ambient']).round(2)
        
        # Select ordered features (just to be safe)
        X = df[feature_cols]

        # 1. Random Forest Prediction (Health Class)
        rf_pred = rf_model.predict(X)[0] # 0 = Normal, 1 = Anomaly
        
        # 2. Isolation Forest Prediction (Outlier Check)
        # IF returns 1 for Inlier (Normal), -1 for Outlier
        if_pred  = if_model.predict(X)[0]           # 1=Normal, -1=Outlier
        if_score = float(if_model.decision_function(X)[0])  # Raw score: >0 = normal, <0 = anomaly
        is_outlier = (if_pred == -1)

    # Decision Logic:
    # Primary gate = Isolation Forest (unsupervised, version-stable)
    # RF only upgrades severity when BOTH models agree on an anomaly
    if not is_outlier:
        final_status = "Normal"            # IF says healthy -> trust it
    elif rf_pred == 1:
        final_status = "Known_Fault"       # Both agree -> high-confidence fault
    else:
        final_status = "Unknown_Anomaly"   # Only IF flags it -> contextual anomaly

    return {
        "status":        final_status,
        "rf_pred":       int(rf_pred),
        "is_outlier":    bool(is_outlier),
        "anomaly_score": round(if_score, 6)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
