const express = require('express');
const mysql = require('mysql2');
const cors = require('cors');

const path = require('path');

const app = express();
const PORT = 5000;

// Middleware
app.use(express.json());
app.use(cors()); // Allow Frontend access

// Database Connection
// TODO: Update with your credentials
const db = mysql.createPool({
    host: 'localhost',
    user: 'root',
    password: '0786682192@Tk', // <--- User to update this
    database: 'solar_monitoring',
    waitForConnections: true,
    connectionLimit: 10,
    queueLimit: 0
});

// Helper: Fetch Prediction from Python FastAPI Service
const checkAnomaly = async (dataPacket) => {
    try {
        const response = await fetch('http://127.0.0.1:8000/predict', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(dataPacket)
        });

        if (!response.ok) {
            console.error(`ML API Error: ${response.status} ${response.statusText}`);
            return { status: "Error", error: "ML API Error" };
        }

        const data = await response.json();
        return data;
    } catch (error) {
        console.error("Failed to connect to ML FastAPI service:", error.message);
        return { status: "Error", error: "ML Service Offline" };
    }
};

// --- ENDPOINTS ---

// 1. Data Ingest (From ESP32 Live or Burst)
app.post('/api/data', async (req, res) => {
    let payload = req.body;

    // Normalize to array to handle both single and burst readings
    if (!Array.isArray(payload)) {
        payload = [payload];
    }

    let processedCount = 0;

    // Process each reading
    for (const raw of payload) {
        // Distributed Computing: Calculate Features
        const v_min = 10.5;
        const v_max = 14.4;
        let soc = ((raw.batt_voltage - v_min) / (v_max - v_min)) * 100;
        soc = Math.min(Math.max(soc, 0), 100);

        const power_watts = raw.pv_voltage * raw.pv_current;
        const batt_ma = raw.batt_voltage;

        const enrichedData = {
            pv_voltage: raw.pv_voltage,
            pv_current: raw.pv_current,
            batt_voltage: raw.batt_voltage,
            load_current: raw.load_current,
            temperature: raw.temp,
            irradiance_lux: raw.irradiance_lux || 0,
            pv_power_watts: power_watts,
            net_energy_flux: raw.pv_current - raw.load_current,
            batt_voltage_ma_10: batt_ma,
            soc_percent: soc
        };

        console.log(`Processing Data. SoC: ${soc.toFixed(1)}%`);

        // 2. Call ML Engine
        const mlResult = await checkAnomaly(enrichedData);
        console.log("ML Prediction:", mlResult);

        const predLabel = mlResult.status || "Normal";

        // Handle custom timestamp from store & forward (if exists)
        // If timestamp_unix is > 0, we convert it to DATETIME string for MySQL
        let timeVal = "NOW()";
        if (raw.timestamp_unix && raw.timestamp_unix > 0) {
            // Convert UNIX timestamp to SQL DATETIME string
            timeVal = `FROM_UNIXTIME(${raw.timestamp_unix})`;
        }

        // 3. Save to SQL
        const sql = `
            INSERT INTO solar_readings 
            (timestamp, pv_voltage, pv_current, batt_voltage, load_current, temperature, irradiance_lux, pv_power_watts, net_energy_flux, soc_percent, pred_label) 
            VALUES (${timeVal}, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `;
        const values = [
            raw.pv_voltage, raw.pv_current, raw.batt_voltage, raw.load_current, raw.temp, raw.irradiance_lux || 0,
            power_watts, enrichedData.net_energy_flux, soc, predLabel
        ];

        db.query(sql, values, (err, result) => {
            if (err) {
                console.error("DB Insert Error:", err);
            } else {
                // If Anomaly, log to Alerts table
                if (predLabel !== "Normal") {
                    const alertSql = `INSERT INTO system_alerts (timestamp, alert_type, details, severity) VALUES (${timeVal}, ?, ?, ?)`;
                    db.query(alertSql, [predLabel, `SoC: ${soc.toFixed(1)}%, V: ${raw.batt_voltage}`, 'Warning']);
                }
            }
        });
        processedCount++;
    }

    res.json({ status: "Saved", processed_count: processedCount });
});

// 2. Dashboard: Get Recent Readings
app.get('/api/readings', (req, res) => {
    // Get last 100 readings
    db.query("SELECT * FROM solar_readings ORDER BY timestamp DESC LIMIT 100", (err, results) => {
        if (err) return res.status(500).send(err);
        res.json(results.reverse()); // Send oldest to newest for graph
    });
});

// 3. Dashboard: Get Alerts
app.get('/api/alerts', (req, res) => {
    db.query("SELECT * FROM system_alerts ORDER BY timestamp DESC LIMIT 10", (err, results) => {
        if (err) return res.status(500).send(err);
        res.json(results);
    });
});

app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
    console.log("Ensure MySQL is running and database 'solar_monitoring' exists.");
});
