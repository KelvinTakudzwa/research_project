-- ============================================================
-- Solar Mini-Grid Predictive Maintenance System
-- Database Schema v3.0 — Agnostic Pipeline
-- Matches: T.K Mukaro (c21145793s) ML-Pdms Thesis ERD (Chapter 3)
-- ============================================================
CREATE DATABASE IF NOT EXISTS solar_monitoring;
USE solar_monitoring;

-- ============================================================
-- TABLE 1: telemetry_data
-- Raw sensor readings from the ESP32 edge node via MQTT QoS 1.
-- Physical values stored; normalization is done in Node.js before
-- the ML vector is sent — raw values persist here for auditability.
-- ============================================================
CREATE TABLE IF NOT EXISTS telemetry_data (
    telemetry_id        INT AUTO_INCREMENT PRIMARY KEY,
    timestamp_utc       DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT 'ISO 8601 from DS3231 RTC',

    -- Generation subsystem (PV array)
    pv_voltage_v        FLOAT COMMENT 'Voltage divider ADC',
    pv_current_a        FLOAT COMMENT 'ACS712 #1',
    pv_power_w          FLOAT COMMENT 'Derived: pv_voltage_v * pv_current_a',

    -- Storage subsystem (battery bank)
    battery_voltage_v   FLOAT COMMENT 'Voltage divider ADC',
    battery_current_a   FLOAT COMMENT 'ACS712 #2 — positive=charging, negative=discharging',
    battery_power_w     FLOAT COMMENT 'Derived: battery_voltage_v * battery_current_a',

    -- Consumption subsystem (PZEM-004T)
    ac_voltage_v        FLOAT COMMENT 'PZEM-004T RMS voltage',
    ac_current_a        FLOAT COMMENT 'PZEM-004T RMS current',
    ac_power_w          FLOAT COMMENT 'PZEM-004T active power',
    ac_power_factor     FLOAT COMMENT 'PZEM-004T power factor 0–1',

    -- Environment
    irradiance_wm2      FLOAT COMMENT 'BH1750 I2C (W/m²)',
    ambient_temp_c      FLOAT COMMENT 'Internal thermistor enclosure air temp',
    battery_temp_c      FLOAT COMMENT 'DS18B20 waterproof battery surface temp',

    -- Derived contextual
    net_energy_flux_w   FLOAT COMMENT 'pv_power_w - ac_power_w (true DC gen minus AC consumption)',
    temp_delta_c        FLOAT COMMENT 'battery_temp_c - ambient_temp_c (thermal runaway discriminator)',
    soc_percent         FLOAT COMMENT 'Voltage-based SoC, agnostic formula, 0–100',

    -- Integrity
    is_offline_buffered TINYINT(1) DEFAULT 0 COMMENT 'LittleFS store-and-forward flag',
    record_source       VARCHAR(20) DEFAULT 'realtime' COMMENT 'realtime | store_forward'
);

-- ============================================================
-- TABLE 2: inference_results
-- ML model outputs for each telemetry record (1:1 with telemetry_data).
-- ============================================================
CREATE TABLE IF NOT EXISTS inference_results (
    inference_id    INT AUTO_INCREMENT PRIMARY KEY,
    telemetry_id    INT NOT NULL,
    soh_percent     FLOAT          COMMENT 'Random Forest SoH Output (0–100)',
    anomaly_score   FLOAT          COMMENT 'Isolation Forest decision score',
    pred_label      VARCHAR(30) DEFAULT 'Normal' COMMENT 'Normal | Unknown_Anomaly | Known_Fault_Degradation',
    FOREIGN KEY (telemetry_id) REFERENCES telemetry_data(telemetry_id) ON DELETE CASCADE
);

-- ============================================================
-- TABLE 3: system_alerts
-- Triggered 1:N from inference_results when pred_label != 'Normal'.
-- fault_category maps to F1–F5 fault taxonomy in Chapter 3.
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
-- Written by retrainer.py after each automated 7-day retraining cycle.
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
CREATE INDEX idx_telemetry_timestamp ON telemetry_data(timestamp_utc);
CREATE INDEX idx_inference_telemetry ON inference_results(telemetry_id);
CREATE INDEX idx_alerts_timestamp    ON system_alerts(alert_timestamp);
