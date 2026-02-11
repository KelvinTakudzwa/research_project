const express = require('express');
const mysql = require('mysql2');
const cors = require('cors');
const { spawn } = require('child_process');
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

// Helper: Run Python ML Script
const checkAnomaly = (dataPacket) => {
    return new Promise((resolve, reject) => {
        // Path to python script
        const scriptPath = path.join(__dirname, 'ml_runner.py');
        const pythonProcess = spawn('python', [scriptPath, JSON.stringify(dataPacket)]);

        let result = '';
        pythonProcess.stdout.on('data', (data) => {
            result += data.toString();
        });

        pythonProcess.stderr.on('data', (data) => {
            console.error(`ML Error: ${data}`);
        });

        pythonProcess.on('close', (code) => {
            if (code !== 0) {
                resolve({ status: "Error", error: "ML Script Failed" });
            } else {
                try {
                    resolve(JSON.parse(result));
                } catch (e) {
                    resolve({ status: "Error", error: "Invalid JSON" });
                }
            }
        });
    });
};

// --- ENDPOINTS ---

// 1. Data Ingest (From ESP32)
app.post('/api/data', async (req, res) => {
    const raw = req.body;

    // Distributed Computing: Calculate Features
    const v_min = 10.5;
    const v_max = 14.4;
    let soc = ((raw.batt_voltage - v_min) / (v_max - v_min)) * 100;
    soc = Math.min(Math.max(soc, 0), 100);

    const power_watts = raw.pv_voltage * raw.pv_current;

    // Simplification for prototype: we don't have historical smooth here easily 
    // without querying DB. For now, use raw batt_voltage as approximation or 0.
    const batt_ma = raw.batt_voltage;

    const enrichedData = {
        pv_voltage: raw.pv_voltage,
        pv_current: raw.pv_current,
        batt_voltage: raw.batt_voltage,
        load_current: raw.load_current,
        temperature: raw.temp, // ESP32 sends "temp"
        pv_power_watts: power_watts,
        net_energy_flux: raw.pv_current - raw.load_current,
        batt_voltage_ma_10: batt_ma,
        soc_percent: soc
    };

    console.log(`Received Data. SoC: ${soc.toFixed(1)}%`);

    // 2. Call ML Engine
    const mlResult = await checkAnomaly(enrichedData);
    console.log("ML Prediction:", mlResult);

    const predLabel = mlResult.status || "Normal";

    // 3. Save to SQL
    const sql = `
        INSERT INTO solar_readings 
        (pv_voltage, pv_current, batt_voltage, load_current, temperature, pv_power_watts, net_energy_flux, soc_percent, pred_label) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `;
    const values = [
        raw.pv_voltage, raw.pv_current, raw.batt_voltage, raw.load_current, raw.temp,
        power_watts, enrichedData.net_energy_flux, soc, predLabel
    ];

    db.query(sql, values, (err, result) => {
        if (err) {
            console.error("DB Insert Error:", err);
            return res.status(500).send("Database Error");
        }

        // If Anomaly, log to Alerts table
        if (predLabel !== "Normal") {
            const alertSql = "INSERT INTO system_alerts (alert_type, details, severity) VALUES (?, ?, ?)";
            db.query(alertSql, [predLabel, `SoC: ${soc.toFixed(1)}%, V: ${raw.batt_voltage}`, 'Warning']);
        }

        res.json({ status: "Saved", ml_status: predLabel });
    });
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
