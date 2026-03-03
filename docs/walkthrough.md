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

1.  **Start MySQL**: Ensure `solar_monitoring` database exists (use `database/schema.sql`).
2.  **Start Python ML API**:
    ```bash
    cd backend
    python ml_api.py
    ```
    (Or `uvicorn ml_api:app --host 127.0.0.1 --port 8000`)
3.  **Start Backend**:
    ```bash
    cd backend
    node server.js
    ```
4.  **Start Dashboard**:
    ```bash
    cd frontend
    npm run dev
    ```
4.  **Simulate Data**:
    Open a new terminal and send a test packet:
    ```powershell
    Invoke-RestMethod -Uri 'http://localhost:5000/api/data' -Method Post -ContentType 'application/json' -Body '{"pv_voltage": 18.5, "pv_current": 4.2, "batt_voltage": 12.8, "load_current": 1.5, "temp": 35.0}'
    ```
5.  **Observe**: Check the Dashboard at `http://localhost:5173`.
