const express = require('express');
const mysql = require('mysql2');
const cors = require('cors');
const mqtt = require('mqtt');
const path = require('path');

const app = express();
const PORT = 5000;

// Middleware
app.use(express.json());
app.use(cors());

// ============================================================
// DATABASE CONNECTION WITH STARTUP RETRY LOOP (Docker fix)
// ============================================================
const dbPoolConfig = {
    host: process.env.DB_HOST || 'localhost',
    user: process.env.DB_USER || 'root',
    password: process.env.DB_PASSWORD || '0786682192@Tk',
    database: process.env.DB_NAME || 'solar_monitoring',
    waitForConnections: true,
    connectionLimit: 10,
    queueLimit: 0
};

let db;

const connectWithRetry = async (retries = 5, delay = 3000) => {
    while (retries > 0) {
        try {
            db = mysql.createPool(dbPoolConfig);
            // Test the connection
            await new Promise((resolve, reject) => {
                db.query('SELECT 1', (err) => {
                    if (err) reject(err);
                    else resolve();
                });
            });
            console.log(`[DB] Successfully connected to MySQL at ${dbPoolConfig.host}`);
            return;
        } catch (err) {
            retries -= 1;
            console.error(`[DB] Connection failed. Retries left: ${retries}. Waiting ${delay/1000}s...`);
            if (retries === 0) {
                console.error('[DB] Fatally failed to connect to MySQL. Exiting.');
                process.exit(1);
            }
            await new Promise(r => setTimeout(r, delay));
        }
    }
};

// ============================================================
// CORE DATA PROCESSING PIPELINE
// (Shared by both MQTT subscriber AND HTTP fallback endpoint)
// ============================================================
const processSensorData = async (rawArray) => {
    let processedCount = 0;

    for (const raw of rawArray) {
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

        console.log(`[Pipeline] Processing reading. SoC: ${soc.toFixed(1)}%`);

        const mlResult = await checkAnomaly(enrichedData);
        console.log('[Pipeline] ML Prediction:', mlResult);

        const predLabel = mlResult.status || 'Normal';

        let timeVal = 'NOW()';
        if (raw.timestamp_unix && raw.timestamp_unix > 0) {
            timeVal = `FROM_UNIXTIME(${raw.timestamp_unix})`;
        }

        const sql = `
            INSERT INTO solar_readings 
            (timestamp, pv_voltage, pv_current, batt_voltage, load_current, temperature, irradiance_lux, pv_power_watts, net_energy_flux, soc_percent, pred_label) 
            VALUES (${timeVal}, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `;
        const values = [
            raw.pv_voltage, raw.pv_current, raw.batt_voltage, raw.load_current, raw.temp,
            raw.irradiance_lux || 0, power_watts, enrichedData.net_energy_flux, soc, predLabel
        ];

        db.query(sql, values, (err) => {
            if (err) {
                console.error('[DB] Insert Error:', err);
            } else {
                if (predLabel !== 'Normal') {
                    const alertSql = `INSERT INTO system_alerts (timestamp, alert_type, details, severity) VALUES (${timeVal}, ?, ?, ?)`;
                    db.query(alertSql, [predLabel, `SoC: ${soc.toFixed(1)}%, V: ${raw.batt_voltage}, Irr: ${raw.irradiance_lux || 0} Lux`, 'Warning']);
                }
            }
        });

        processedCount++;
    }
    return processedCount;
};

// ============================================================
// ML API HELPER
// ============================================================
const checkAnomaly = async (dataPacket) => {
    try {
        const ML_API_URL = process.env.ML_API_URL || 'http://127.0.0.1:8000';
        const response = await fetch(`${ML_API_URL}/predict`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(dataPacket)
        });
        if (!response.ok) {
            console.error(`[ML] API Error: ${response.status}`);
            return { status: 'Error' };
        }
        return await response.json();
    } catch (error) {
        console.error('[ML] Service offline:', error.message);
        return { status: 'Error' };
    }
};

// ============================================================
// MQTT SUBSCRIBER — PRIMARY DATA TRANSPORT (Phase 8)
// ============================================================
const MQTT_BROKER = process.env.MQTT_BROKER || 'mqtt://localhost:1883';
const MQTT_TOPIC  = 'solar/data';

const mqttClient = mqtt.connect(MQTT_BROKER, {
    clientId: 'NodeJS_SolarBackend',  // Hardcoded — consistent across restarts
    clean: true,                       // Clear stale session on connect
    reconnectPeriod: 3000,
    connectTimeout: 10000
});

mqttClient.on('connect', () => {
    console.log('[MQTT] Connected to Mosquitto broker at', MQTT_BROKER);
    // Subscribe at QoS 1 to guarantee delivery acknowledgment
    mqttClient.subscribe(MQTT_TOPIC, { qos: 1 }, (err) => {
        if (err) {
            console.error('[MQTT] Subscription error:', err);
        } else {
            console.log(`[MQTT] Subscribed to topic: ${MQTT_TOPIC} (QoS 1)`);
        }
    });
});

mqttClient.on('message', async (topic, messageBuffer) => {
    const raw = messageBuffer.toString();
    console.log(`[MQTT] Message received on topic '${topic}': ${raw.substring(0, 80)}...`);

    try {
        let payload = JSON.parse(raw);
        // Normalize to array — handles both single object and burst JSON arrays
        if (!Array.isArray(payload)) payload = [payload];
        const count = await processSensorData(payload);
        console.log(`[MQTT] Pipeline complete. Processed ${count} reading(s).`);
    } catch (err) {
        console.error('[MQTT] Failed to parse or process message:', err.message);
    }
});

mqttClient.on('error', (err) => {
    console.error('[MQTT] Client error:', err.message);
});

mqttClient.on('offline', () => {
    console.warn('[MQTT] Client offline — broker may be unavailable. Retrying...');
});

mqttClient.on('reconnect', () => {
    console.log('[MQTT] Reconnecting to broker...');
});

// ============================================================
// HTTP REST API — FALLBACK & MANUAL TESTING (Kept intentionally)
// ============================================================

// POST /api/data — Manual test fallback (replaces ESP32 in dev/testing)
app.post('/api/data', async (req, res) => {
    let payload = req.body;
    if (!Array.isArray(payload)) payload = [payload];
    const count = await processSensorData(payload);
    res.json({ status: 'Saved', transport: 'HTTP', processed_count: count });
});

// GET /api/readings — Dashboard data (last 100)
app.get('/api/readings', (req, res) => {
    db.query('SELECT * FROM solar_readings ORDER BY timestamp DESC LIMIT 100', (err, results) => {
        if (err) return res.status(500).send(err);
        res.json(results.reverse());
    });
});

// GET /api/alerts — Dashboard alerts
app.get('/api/alerts', (req, res) => {
    db.query('SELECT * FROM system_alerts ORDER BY timestamp DESC LIMIT 10', (err, results) => {
        if (err) return res.status(500).send(err);
        res.json(results);
    });
});

// ============================================================
// START HTTP SERVER (After DB starts)
// ============================================================
connectWithRetry().then(() => {
    app.listen(PORT, () => {
        console.log(`[HTTP] Server running on port ${PORT}`);
        console.log('[HTTP] Fallback /api/data endpoint active for manual testing.');
        console.log(`[MQTT] Waiting for broker connection at ${MQTT_BROKER}...`);
    });
});
