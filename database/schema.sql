-- Database Initialization
CREATE DATABASE IF NOT EXISTS solar_monitoring;
USE solar_monitoring;

-- 1. Main Data Table (Time-Series)
-- Stores the raw 1-minute interval data from the IoT Node
CREATE TABLE IF NOT EXISTS solar_readings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    pv_voltage FLOAT,
    pv_current FLOAT,
    batt_voltage FLOAT,
    load_current FLOAT,
    temperature FLOAT,
    -- Derived Features (Calculated by Node.js before insert)
    pv_power_watts FLOAT,
    net_energy_flux FLOAT,
    soc_percent FLOAT,
    pred_label VARCHAR(20) DEFAULT 'Normal' -- 'Normal', 'Shading', 'Low_Batt'
);

-- 2. Alerts Table
-- Logs specific events/anomalies detected by the ML Engine
CREATE TABLE IF NOT EXISTS system_alerts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    alert_type VARCHAR(50), -- e.g., 'Anomaly_Detected', 'Battery_Critical'
    details TEXT,
    severity VARCHAR(10) -- 'Info', 'Warning', 'Critical'
);

-- Indexing for performance on time-range queries
CREATE INDEX idx_timestamp ON solar_readings(timestamp);
