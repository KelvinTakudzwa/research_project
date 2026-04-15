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
        const net_flux    = raw.pv_current - raw.load_current;
        const lux         = raw.irradiance_lux || 0;
        // Contextual discriminator feature — must match ML model training
        const current_to_lux_ratio = (raw.pv_current / (lux + 1)) * 1000;

        const enrichedData = {
            pv_voltage:           raw.pv_voltage,
            pv_current:           raw.pv_current,
            batt_voltage:         raw.batt_voltage,
            load_current:         raw.load_current,
            temperature:          raw.temp || raw.temperature || 0,
            irradiance_lux:       lux,
            pv_power_watts:       power_watts,
            net_energy_flux:      net_flux,
            batt_voltage_ma_10:   raw.batt_voltage, // Approximation; rolling avg done in Python
            soc_percent:          soc,
            current_to_lux_ratio: current_to_lux_ratio
        };

        console.log(`[Pipeline] SoC: ${soc.toFixed(1)}% | Lux-Ratio: ${current_to_lux_ratio.toFixed(4)}`);

        // -- Step 1: Get ML prediction BEFORE writing to DB --
        const mlResult = await checkAnomaly(enrichedData);
        const predLabel    = mlResult.status      || 'Normal';
        const anomalyScore = mlResult.anomaly_score !== undefined ? mlResult.anomaly_score : null;

        const timeExpr = (raw.timestamp_unix && raw.timestamp_unix > 0)
            ? `FROM_UNIXTIME(${raw.timestamp_unix})`
            : 'NOW()';

        const recordSource = (raw.record_source === 'store_forward') ? 'store_forward' : 'realtime';

        // -- Step 2: INSERT into telemetry_data (raw sensor record) --
        const telemetrySql = `
            INSERT INTO telemetry_data
            (timestamp_unix, pv_voltage, pv_current, batt_voltage, load_current,
             temperature, irradiance_lux, pv_power_watts, net_energy_flux, soc_percent, record_source)
            VALUES (${timeExpr}, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `;
        const telemetryValues = [
            raw.pv_voltage, raw.pv_current, raw.batt_voltage, raw.load_current,
            enrichedData.temperature, lux, power_watts, net_flux, soc, recordSource
        ];

        db.query(telemetrySql, telemetryValues, (err, telemetryResult) => {
            if (err) {
                console.error('[DB] telemetry_data insert error:', err);
                return;
            }

            const telemetryId = telemetryResult.insertId;

            // -- Step 3: INSERT into inference_results (ML analysis) --
            const inferenceSql = `
                INSERT INTO inference_results (telemetry_id, soh_percent, anomaly_score, pred_label)
                VALUES (?, ?, ?, ?)
            `;
            db.query(inferenceSql, [telemetryId, soc, anomalyScore, predLabel], (err2, inferenceResult) => {
                if (err2) {
                    console.error('[DB] inference_results insert error:', err2);
                    return;
                }

                // -- Step 4: INSERT alert if fault detected (1:N from inference_results) --
                if (predLabel !== 'Normal' && predLabel !== 'Error') {
                    const inferenceId  = inferenceResult.insertId;
                    const faultMapping = {
                        'Unknown_Anomaly': 'F1 Partial Shading / Unknown',
                        'Known_Fault':     'F2-F5 Known Fault Pattern'
                    };
                    const faultCategory = faultMapping[predLabel] || predLabel;
                    const severity      = predLabel === 'Known_Fault' ? 'Critical' : 'Warning';

                    const alertSql = `
                        INSERT INTO system_alerts (inference_id, alert_timestamp, fault_category, severity)
                        VALUES (?, ${timeExpr}, ?, ?)
                    `;
                    db.query(alertSql, [inferenceId, faultCategory, severity], (err3) => {
                        if (err3) console.error('[DB] system_alerts insert error:', err3);
                        else console.log(`[Alert] ${severity} alert logged — ${faultCategory}`);
                    });
                }
            });
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

// GET /api/readings — Dashboard data (last 100), joined with ML results
app.get('/api/readings', (req, res) => {
    const sql = `
        SELECT
            t.telemetry_id  AS id,
            t.timestamp_unix AS timestamp,
            t.pv_voltage, t.pv_current, t.batt_voltage,
            t.load_current, t.temperature, t.irradiance_lux,
            t.pv_power_watts, t.net_energy_flux, t.soc_percent, t.record_source,
            i.pred_label, i.anomaly_score, i.soh_percent
        FROM telemetry_data t
        LEFT JOIN inference_results i ON t.telemetry_id = i.telemetry_id
        ORDER BY t.timestamp_unix DESC
        LIMIT 100
    `;
    db.query(sql, (err, results) => {
        if (err) return res.status(500).send(err);
        res.json(results.reverse());
    });
});

// GET /api/alerts — Dashboard alerts (last 10)
app.get('/api/alerts', (req, res) => {
    const sql = `
        SELECT
            a.alert_id   AS id,
            a.alert_timestamp AS timestamp,
            a.fault_category  AS alert_type,
            a.severity,
            i.pred_label,
            t.soc_percent,
            t.batt_voltage
        FROM system_alerts a
        JOIN inference_results i ON a.inference_id = i.inference_id
        JOIN telemetry_data    t ON i.telemetry_id  = t.telemetry_id
        ORDER BY a.alert_timestamp DESC
        LIMIT 10
    `;
    db.query(sql, (err, results) => {
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
