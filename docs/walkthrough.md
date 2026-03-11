# Solar Mini-Grid Predictive Maintenance System - Final Walkthrough

## 1. Project Overview
This project successfully implemented a **Machine Learning-Based Predictive Maintenance System** for Solar Mini-Grids.
It demonstrates a full IoT-to-AI pipeline, capable of predicting Battery Health and detecting Anomalies in real-time.

**Key Achievements:**
- **Synthetic Data**: Generated ~43,000 realistic data points with injected faults.
- **IoT Firmware**: "Virtual ESP32" firmware with **Store & Forward** resilience via LittleFS.
- **Distributed Computing**: Edge-Fog architecture where Node.js calculates SoC.
- **ML Engine**: Random Forest (>99% accuracy) and Isolation Forest via **FastAPI Microservice**.
- **Dashboard**: Real-time **PWA (Progressive Web App)** with offline local storage caching.

## 2. System Architecture

```mermaid
graph LR
    ESP32[IoT Node (Virtual)] -->|HTTP POST| Server[Node.js Backend]
    ESP32 -.->|Offline Fallback| LittleFS[(Flash Memory)]
    Server -->|Store| DB[(MySQL Database)]
    Server -->|HTTP POST| ML[Python FastAPI Service]
    ML -->|Prediction| Server
    User[React PWA Dashboard] -->|Poll| Server
    User -.->|Offline Fallback| LocalStorage[(Browser Cache)]
```

## 3. Component Details

### A. Data Simulation (Phase 1)
- **Script**: `simulation/generate_data.py`
- **Output**: `solar_data_30days.csv`
- **Features**: PV Voltage, Current, Temp, *Derived Power*, *Net Flux*, *SoC*.

### B. IoT Node (Phase 2 & 6)
- **Firmware**: `firmware/esp32_main.ino`
- **Logic**: Simulates sensor reading -> JSON Serialization -> HTTP POST.
- **Resilience**: Implements *Store & Forward*. If Wi-Fi fails, stores readings as NDJSON in LittleFS with relative NTP timestamps via `millis()`.
- **Circuit**: See `docs/phase2_circuit.md`.

### C. Machine Learning (Phase 3)
- **Training**: `simulation/train_models.py`
- **Models**:
    - `rf_model.pkl`: Classifier for **Battery Health** (Normal, Low Voltage, Shading).
    - `if_model.pkl`: Anomaly Detector for unknown patterns.
- **Insights**: `feature_importance.png` shows Voltage and Net Flux are key health indicators.

### D. Full-Stack App (Phase 4 & 6)
- **Backend**: `backend/server.js` (Express + MySQL). Handles single objects and batch JSON arrays.
- **Frontend**: `frontend/` (React + Tailwind + Recharts). Converted to an offline-capable **PWA**.
- **Bridge**: `backend/ml_api.py` runs as a standalone FastAPI microservice.

### E. Evaluation (Phase 5)
- **Metrics**: High accuracy verified in `docs/phase5_results.md`.
- **Latency**: End-to-end response time ~2.7s.

## 4. How to Run the Demo

> [!IMPORTANT]
> Services must be started in this order. Open **3 separate terminals**.

**Terminal 1 — Python ML API:**
```powershell
cd backend; python ml_api.py
```
**Terminal 2 — Node.js Backend:**
```powershell
cd backend; node server.js
```
**Terminal 3 — React Dashboard:**
```powershell
cd frontend; npm run dev
```
Open the dashboard at **http://localhost:5173**

---

## 5. Live Test Scenarios (PowerShell Commands)

Open a **4th terminal** in the project root and run any of the commands below.  
After each command, watch the Dashboard at **http://localhost:5173** update in real time.

---

### ✅ Scenario 1 — Bright Sunny Day (Normal)
**Expected Label:** `Normal`
> High Irradiance + High PV Current = healthy panel, good battery.
```powershell
Invoke-RestMethod -Uri 'http://localhost:5000/api/data' -Method Post -ContentType 'application/json' -Body '{
  "pv_voltage": 18.8,
  "pv_current": 4.5,
  "batt_voltage": 13.9,
  "load_current": 1.2,
  "temp": 37.5,
  "irradiance_lux": 95000
}'
```

---

### ☁️ Scenario 2 — Overcast / Cloudy Day (Normal)
**Expected Label:** `Normal`
> Low Irradiance + Low PV Current — both low simultaneously = just a cloudy day, NOT a fault.
```powershell
Invoke-RestMethod -Uri 'http://localhost:5000/api/data' -Method Post -ContentType 'application/json' -Body '{
  "pv_voltage": 16.5,
  "pv_current": 1.2,
  "batt_voltage": 12.8,
  "load_current": 1.5,
  "temp": 28.0,
  "irradiance_lux": 30000
}'
```

---

### 🌞⚠️ Scenario 3 — Shading / Dust Fault (Anomaly)
**Expected Label:** `Unknown_Anomaly` or `Known_Fault`
> **High Irradiance + Low PV Current** = the sun is out but the panel isn't generating power. Confirmed physical fault (dust, shading, degradation).
```powershell
Invoke-RestMethod -Uri 'http://localhost:5000/api/data' -Method Post -ContentType 'application/json' -Body '{
  "pv_voltage": 17.9,
  "pv_current": 0.5,
  "batt_voltage": 11.8,
  "load_current": 2.6,
  "temp": 34.0,
  "irradiance_lux": 96000
}'
```

---

### 🔋⚠️ Scenario 4 — Critical Battery (Low Voltage Fault)
**Expected Label:** `Known_Fault` or `Unknown_Anomaly`
> Battery voltage fallen below safe threshold. Sustained heavy load with insufficient solar charging.
```powershell
Invoke-RestMethod -Uri 'http://localhost:5000/api/data' -Method Post -ContentType 'application/json' -Body '{
  "pv_voltage": 0.5,
  "pv_current": 0.0,
  "batt_voltage": 10.6,
  "load_current": 3.5,
  "temp": 22.0,
  "irradiance_lux": 500
}'
```

---

### 📡 Scenario 5 — Store & Forward Batch (Simulated Offline Burst)
**ExpectedLabelled Count:** `processed_count: 3`
> Simulates the ESP32 coming back online after being disconnected. It sends a JSON array of 3 readings captured offline (with their original `timestamp_unix` values).
```powershell
Invoke-RestMethod -Uri 'http://localhost:5000/api/data' -Method Post -ContentType 'application/json' -Body '[
  {"pv_voltage":18.2,"pv_current":3.8,"batt_voltage":13.6,"load_current":1.4,"temp":33.0,"irradiance_lux":80000,"timestamp_unix":1741647600},
  {"pv_voltage":17.8,"pv_current":3.5,"batt_voltage":13.4,"load_current":1.5,"temp":34.0,"irradiance_lux":75000,"timestamp_unix":1741647660},
  {"pv_voltage":17.9,"pv_current":0.4,"batt_voltage":12.1,"load_current":2.2,"temp":33.5,"irradiance_lux":94000,"timestamp_unix":1741647720}
]'
```

---

### 🗄️ Verify in Database
Run this at any time to see the last 5 rows with their ML-generated labels:
```powershell
mysql -u root -p solar_monitoring -e "SELECT DATE_FORMAT(timestamp,'%H:%i:%s') as time, irradiance_lux, pv_current, ROUND(soc_percent,1) as soc, pred_label FROM solar_readings ORDER BY timestamp DESC LIMIT 5;"
```
