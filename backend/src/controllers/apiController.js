const { getRecentReadings } = require('../models/telemetryModel');
const { getRecentAlerts } = require('../models/alertModel');
const { processSensorData } = require('../services/dataProcessor');
const { getServiceToken } = require('../services/serviceAuth');

// GET /api/readings — Dashboard data (last 100), joined with ML results
const getReadings = async (req, res) => {
    try {
        const results = await getRecentReadings(100);
        res.json(results);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
};

// GET /api/alerts — Dashboard alerts (last 10)
const getAlerts = async (req, res) => {
    try {
        const results = await getRecentAlerts(10);
        res.json(results);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
};

// POST /api/data — Manual test fallback (replaces ESP32 in dev/testing)
const postData = async (req, res) => {
    let payload = req.body;
    if (!Array.isArray(payload)) payload = [payload];
    try {
        const count = await processSensorData(payload);
        res.json({ status: 'Saved', transport: 'HTTP', processed_count: count });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
};

// GET /api/calibration_log
const getCalibrationLog = async (req, res) => {
    const { getDb } = require('../config/database');
    const sql = `SELECT * FROM calibration_log ORDER BY retrain_timestamp DESC LIMIT 10`;
    getDb().query(sql, (err, results) => {
        if (err) return res.status(500).json({ error: err.message });
        res.json(results);
    });
};

// POST /api/trigger_retraining
const triggerRetrain = async (req, res) => {
    const ML_API_URL = process.env.ML_API_URL || 'http://127.0.0.1:8000';
    try {
        const response = await fetch(`${ML_API_URL}/trigger_retraining`, {
            method:  'POST',
            headers: { 'Authorization': `Bearer ${getServiceToken()}` },
        });
        const data = await response.json();
        res.json(data);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
};

module.exports = {
    getReadings,
    getAlerts,
    postData,
    getCalibrationLog,
    triggerRetrain
};
