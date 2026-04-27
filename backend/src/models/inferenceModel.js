const { getDb } = require('../config/database');

const insertInference = (telemetryId, soc, anomalyScore, predLabel, confidence = null) => {
    return new Promise((resolve, reject) => {
        const sql = `
            INSERT INTO inference_results (telemetry_id, soh_percent, anomaly_score, pred_label, confidence)
            VALUES (?, ?, ?, ?, ?)
        `;
        getDb().query(sql, [telemetryId, soc, anomalyScore, predLabel, confidence], (err, result) => {
            if (err) return reject(err);
            resolve(result.insertId);
        });
    });
};

module.exports = {
    insertInference
};
