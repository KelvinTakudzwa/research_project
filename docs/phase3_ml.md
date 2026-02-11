# Phase 3: Machine Learning Model Development

## 1. Model Selection Strategy
To meet the "Predictive Maintenance" objective, we employ two complementary Machine Learning models.

| Model | Type | Purpose | Advantages for Undergraduate Project |
| :--- | :--- | :--- | :--- |
| **Random Forest** | Supervised | **Battery Health Prediction**. Classifies system state as "Normal", "Low Voltage", or "Shading". | High accuracy, resistant to overfitting, provides **Feature Importance** (explainability). |
| **Isolation Forest** | Unsupervised | **Anomaly Detection**. Flags "Unknown" faults that deviate from normal patterns. | Does not require labeled data for every possible fault type. Good for detecting new, unseen problems. |

## 2. Feature Engineering (Input Data)
The models are trained on the following features (Engineering Parameters):
*   **Raw Sensors**: `pv_voltage`, `pv_current`, `batt_voltage`, `load_current`, `temp`.
*   **Derived Features**:
    *   `pv_power_watts` ($V \times I$)
    *   `net_energy_flux` (Charging vs Draining)
    *   `soH_percent` (State of Charge proxy)
    *   `batt_voltage_ma_10` (Smoothed trends)

## 3. Distinction-Level Analysis: Feature Importance
One of the key deliverables of this phase is the **Feature Importance Chart**.
*   **Analysis**: The Random Forest model calculates which sensor contributes most to the decision making.
*   **Expected Result**: `batt_voltage` and `net_energy_flux` should be the top predictors for Battery Health, while `pv_current` should be the top predictor for Shading events.
*   **Why this matters**: It proves you aren't just "black-boxing" the AI; you understand the physical correlation between the sensor readings and the faults.

## 4. Model Deployment
The trained models are exported as `.pkl` (Pickle) files to the `backend/models/` directory.
In **Phase 4**, the Node.js backend will call a Python script to load these models and make real-time predictions on incoming IoT data.
