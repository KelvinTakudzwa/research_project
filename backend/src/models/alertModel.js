const { getDb } = require('../config/database');

const insertAlert = (inferenceId, faultCategory, severity, timestampExpr) => {
    return new Promise((resolve, reject) => {
        const sql = `
            INSERT INTO system_alerts (inference_id, alert_timestamp, fault_category, severity)
            VALUES (?, ${timestampExpr}, ?, ?)
        `;
        getDb().query(sql, [inferenceId, faultCategory, severity], (err, result) => {
            if (err) return reject(err);
            resolve(result.insertId);
        });
    });
};

const getRecentAlerts = (limit = 10) => {
    return new Promise((resolve, reject) => {
        const sql = `
            SELECT
                a.alert_id            AS id,
                a.alert_timestamp     AS timestamp,
                a.fault_category      AS alert_type,
                a.severity            AS alert_severity,
                t.soc_percent,
                t.battery_voltage_v,
                i.anomaly_score,
                i.pred_label
            FROM system_alerts a
            JOIN inference_results i ON a.inference_id = i.inference_id
            JOIN telemetry_data t    ON i.telemetry_id = t.telemetry_id
            ORDER BY a.alert_timestamp DESC
            LIMIT ?
        `;
        getDb().query(sql, [limit], (err, results) => {
            if (err) return reject(err);
            resolve(results);
        });
    });
};

module.exports = { insertAlert, getRecentAlerts };
