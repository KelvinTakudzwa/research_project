-- ============================================================
-- Solar Mini-Grid Predictive Maintenance System
-- Database Schema v2.0 — Normalized 4-Table Design
-- Matches: T.K Mukaro (c21145793s) ML-Pdms Thesis ERD (Chapter 3)
-- ============================================================
CREATE DATABASE IF NOT EXISTS solar_monitoring;
USE solar_monitoring;

-- ============================================================
-- TABLE 1: telemetry_data
-- Raw sensor readings from the ESP32 edge node via MQTT QoS 1.
-- record_source distinguishes real-time vs store-and-forward packets.
-- ============================================================
CREATE TABLE IF NOT EXISTS telemetry_data (
    telemetry_id    INT AUTO_INCREMENT PRIMARY KEY,
    timestamp_unix  DATETIME DEFAULT CURRENT_TIMESTAMP,
    pv_voltage      FLOAT,
    pv_current      FLOAT,
    batt_voltage    FLOAT,
    load_current    FLOAT,
    temperature     FLOAT,
    irradiance_lux  FLOAT,
    -- Derived features calculated by Node.js before insert
    pv_power_watts  FLOAT,
    net_energy_flux FLOAT,
    soc_percent     FLOAT,
    record_source   VARCHAR(20) DEFAULT 'realtime' -- 'realtime' | 'store_forward'
);

-- ============================================================
-- TABLE 2: inference_results
-- ML model outputs for each telemetry record (1:1 with telemetry_data).
-- Keeps raw sensor data separate from ML analysis results.
-- ============================================================
CREATE TABLE IF NOT EXISTS inference_results (
    inference_id    INT AUTO_INCREMENT PRIMARY KEY,
    telemetry_id    INT NOT NULL,
    soh_percent     FLOAT          COMMENT 'Random Forest SoH Output (0-100)',
    anomaly_score   FLOAT          COMMENT 'Isolation Forest decision score',
    pred_label      VARCHAR(30) DEFAULT 'Normal', -- 'Normal' | 'Unknown_Anomaly' | 'Known_Fault'
    FOREIGN KEY (telemetry_id) REFERENCES telemetry_data(telemetry_id) ON DELETE CASCADE
);

-- ============================================================
-- TABLE 3: system_alerts
-- Triggered 1:N from inference_results when pred_label != 'Normal'.
-- fault_category maps directly to F1-F5 fault taxonomy in Chapter 3.
-- ============================================================
CREATE TABLE IF NOT EXISTS system_alerts (
    alert_id        INT AUTO_INCREMENT PRIMARY KEY,
    inference_id    INT NOT NULL,
    alert_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    fault_category  VARCHAR(50)    COMMENT 'e.g. F1 Partial Shading',
    severity        VARCHAR(10)    COMMENT 'Warning | Critical',
    FOREIGN KEY (inference_id) REFERENCES inference_results(inference_id) ON DELETE CASCADE
);

-- ============================================================
-- TABLE 4: calibration_log
-- Written by ml_runner.py after each automated 7-day retraining cycle.
-- Tracks concept drift mitigation performance over time.
-- ============================================================
CREATE TABLE IF NOT EXISTS calibration_log (
    calibration_id      INT AUTO_INCREMENT PRIMARY KEY,
    retrain_timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP,
    rmse_score          FLOAT  COMMENT 'Root Mean Square Error of retrained model',
    mae_score           FLOAT  COMMENT 'Mean Absolute Error of retrained model',
    days_elapsed        INT    COMMENT 'Days since last retraining cycle'
);

-- ============================================================
-- INDEXES for time-range dashboard queries
-- ============================================================
CREATE INDEX idx_telemetry_timestamp ON telemetry_data(timestamp_unix);
CREATE INDEX idx_inference_telemetry ON inference_results(telemetry_id);
CREATE INDEX idx_alerts_timestamp    ON system_alerts(alert_timestamp);

