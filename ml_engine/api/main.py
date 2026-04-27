import os
import sys
import joblib
import threading

import pandas as pd
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel
from apscheduler.schedulers.background import BackgroundScheduler

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'jobs'))
from retrainer import retrain_isolation_forest

app = FastAPI(title="Solar ML API", description="Microservice for predicting solar mini-grid anomalies.")

MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', 'models')
JWT_SERVICE_SECRET = os.environ.get("JWT_SERVICE_SECRET")

# ── Security ──────────────────────────────────────────────────────────────────
security = HTTPBearer()

def verify_service_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not JWT_SERVICE_SECRET:
        raise HTTPException(status_code=500, detail="JWT_SERVICE_SECRET not configured.")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SERVICE_SECRET, algorithms=["HS256"])
        if payload.get("role") != "ml-client":
            raise HTTPException(status_code=401, detail="Unauthorized")
    except JWTError:
        raise HTTPException(status_code=401, detail="Unauthorized")

# ── Model loading ─────────────────────────────────────────────────────────────
model_lock = threading.Lock()

def load_models():
    global rf_model, if_model
    with model_lock:
        print("[ML_API] Loading models from disk...")
        try:
            rf_model = joblib.load(f"{MODEL_DIR}/rf_model.pkl")
            print("[ML_API] Random Forest model loaded.")
        except Exception as e:
            rf_model = None
            print(f"[ML_API] Error loading RF model: {e}")
        try:
            if_model = joblib.load(f"{MODEL_DIR}/if_model.pkl")
            print("[ML_API] Isolation Forest model loaded.")
        except Exception as e:
            if_model = None
            print(f"[ML_API] Error loading IF model: {e}")

load_models()

# ── Pydantic schema — normalized 15-feature vector ────────────────────────────
class SensorData(BaseModel):
    # Normalized — all [0, 1]; battery_current_norm is signed [-1, +1]
    pv_voltage_norm:      float
    pv_current_norm:      float
    pv_power_norm:        float
    battery_voltage_norm: float
    battery_current_norm: float
    battery_power_norm:   float
    ac_power_norm:        float
    ac_current_norm:      float
    net_flux_norm:        float
    irradiance_norm:      float
    # Dimensionless — no normalization needed
    soc_percent:          float   # 0–100
    ac_power_factor:      float   # 0–1
    # Raw temps — contextual, not capacity-dependent
    ambient_temp_c:       float
    battery_temp_c:       float
    temp_delta_c:         float

# ── Health check (public — Docker health checks need this) ────────────────────
@app.get("/")
def read_root():
    return {"status": "ML API is running."}

# ── Retraining ────────────────────────────────────────────────────────────────
def background_training_task():
    success = retrain_isolation_forest()
    if success:
        load_models()

@app.post("/trigger_retraining")
def trigger_retraining(background_tasks: BackgroundTasks, _=Depends(verify_service_token)):
    print("[ML_API] Manual retraining triggered.")
    background_tasks.add_task(background_training_task)
    return {"status": "Accepted", "message": "Retraining started in the background."}

# ── Scheduler (7-day periodic retraining) ────────────────────────────────────
scheduler = BackgroundScheduler()
scheduler.add_job(background_training_task, 'interval', days=7)
scheduler.start()

@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()

# ── Prediction ────────────────────────────────────────────────────────────────
FEATURE_COLS = [
    'pv_voltage_norm', 'pv_current_norm', 'pv_power_norm',
    'battery_voltage_norm', 'battery_current_norm', 'battery_power_norm',
    'ac_power_norm', 'ac_current_norm', 'net_flux_norm', 'irradiance_norm',
    'soc_percent', 'ac_power_factor',
    'ambient_temp_c', 'battery_temp_c', 'temp_delta_c',
]

@app.post("/predict")
def predict_anomaly(data: SensorData, _=Depends(verify_service_token)):
    with model_lock:
        if not rf_model or not if_model:
            raise HTTPException(status_code=500, detail="Models not loaded properly.")

        df = pd.DataFrame([data.model_dump()])
        X  = df[FEATURE_COLS]

        try:
            rf_pred_class = rf_model.predict(X)[0]           # e.g. "F2_Inverter_Overload"
            rf_proba      = rf_model.predict_proba(X)[0]      # prob per class
            class_names   = list(rf_model.classes_)
            confidence    = float(max(rf_proba))              # confidence in predicted class

            # health_score = P(Normal) × 100:  100 = healthy, 0 = definite fault
            normal_idx    = class_names.index('Normal')
            health_score  = round(float(rf_proba[normal_idx]) * 100, 2)

            if_pred  = if_model.predict(X)[0]
            if_score = float(if_model.decision_function(X)[0])
        except Exception as e:
            print(f"[ML_API] Model mismatch (retrain needed): {e}")
            raise HTTPException(status_code=503, detail="Models are stale — retrain in progress.")

        is_outlier = (if_pred == -1)

    # Two-stage decision with confidence-driven severity:
    #   Stage 1 — IF: unsupervised anomaly gate (fast, no labels needed)
    #   Stage 2 — RF: identifies specific fault class + confidence
    #
    #   confidence >= 0.75 → specific fault label (Critical)
    #   0.50 ≤ conf < 0.75 → specific fault label (Warning — less certain)
    #   conf < 0.50 + IF anomaly → Uncertain_Anomaly soft indicator
    if not is_outlier and rf_pred_class == 'Normal':
        final_status = "Normal"
    elif rf_pred_class != 'Normal' and confidence >= 0.50:
        final_status = rf_pred_class        # F1_Partial_Shading, F2_Inverter_Overload, etc.
    elif is_outlier:
        final_status = "Uncertain_Anomaly"  # IF flagged but RF not confident
    else:
        final_status = "Normal"

    return {
        "status":        final_status,
        "soh_percent":   health_score,          # P(Normal)×100 — dashboard ring
        "confidence":    round(confidence, 4),  # confidence in the predicted class
        "is_outlier":    bool(is_outlier),
        "anomaly_score": round(if_score, 6),
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
