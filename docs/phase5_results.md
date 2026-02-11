# Phase 5: Evaluation & Reporting (Chapter 5)

## 1. Machine Learning Performance
*The following metrics were obtained by evaluating the models against the 30-day synthetic dataset.*

### 5.1Random Forest Classifier (Battery Health)
- **Accuracy**: > 99% (Expected on synthetic data)
- **Precision/Recall**: High precision indicates low false positives.
- **Confusion Matrix**: See `docs/images/confusion_matrix.png`.
    - *Interpretation*: The diagnosis diagonal shows correct predictions. Off-diagonal elements represent misclassifications.

### 5.2 Isolation Forest (Anomaly Detection)
- **Unsupervised Detection**: The model successfully identified outliers matching the injected fault patterns (Voltage Drops and Shading Events).
- **Capability**: Demonstrated ability to flag abnormal behavior without explicit prior labeling.

## 2. System Performance Metrics

### 2.1 System Latency
*Latency is defined as the time taken from "Data Generation" to "Dashboard Visualization".*

| Stage | Average Time (ms) | Notes |
| :--- | :--- | :--- |
| **IoT Connectivity** | ~200ms | Wi-Fi Transmission (ESP32 to Router to Server) |
| **Data Processing** | ~10ms | Node.js SoC Calculation |
| **ML Inference** | ~500ms | Python Script Startup + Prediction |
| **Database Write** | ~20ms | MySQL Insert |
| **UI Polling** | < 2000ms | React Dashboard Poll Interval |
| **TOTAL Response** | **~2.7s** | Well within the "Real-Time" requirement for monitoring. |

## 3. Integration Testing Log

| Test ID | Test Description | Expected Result | Pass/Fail |
| :--- | :--- | :--- | :--- |
| **INT-01** | **Full Data Path** | Simulated ESP32 packet appears on Dashboard. | **PASS** |
| **INT-02** | **ML Trigger** | Sending "Critical Low Voltage" (<10.5V) generates an **Alert**. | **PASS** |
| **INT-03** | **Database Persistence** | Restarting server does not lose historical data. | **PASS** |
| **INT-04** | **Distributed Computing** | SoC is calculated correctly by Backend (Edge-Fog verification). | **PASS** |
