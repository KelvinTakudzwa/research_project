const { getDb } = require('../config/database');

const insertTelemetry = (data, timeExpr) => {
    return new Promise((resolve, reject) => {
        const sql = `
            INSERT INTO telemetry_data
            (timestamp_unix, pv_voltage, pv_current, batt_voltage, load_current,
             temp_ambient, temp_probe, irradiance_lux, pv_power_watts, net_energy_flux, temp_delta, soc_percent, record_source)
            VALUES (${timeExpr}, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `;
        const values = [
            data.pv_voltage, data.pv_current, data.batt_voltage, data.load_current,
            data.temp_ambient, data.temp_probe, data.irradiance_lux, data.pv_power_watts, 
            data.net_energy_flux, data.temp_delta, data.soc_percent, data.record_source
        ];

        getDb().query(sql, values, (err, result) => {
            if (err) return reject(err);
            resolve(result.insertId);
        });
    });
};

const getRecentReadings = (limit = 100) => {
    return new Promise((resolve, reject) => {
        const sql = `
            SELECT
                t.telemetry_id  AS id,
                t.timestamp_unix AS timestamp,
                t.pv_voltage, t.pv_current, t.batt_voltage,
                t.load_current, t.temp_ambient, t.temp_probe, t.temp_delta, t.irradiance_lux,
                t.pv_power_watts, t.net_energy_flux, t.soc_percent, t.record_source,
                i.pred_label, i.anomaly_score, i.soh_percent
            FROM telemetry_data t
            LEFT JOIN inference_results i ON t.telemetry_id = i.telemetry_id
            ORDER BY t.timestamp_unix DESC
            LIMIT ?
        `;
        getDb().query(sql, [limit], (err, results) => {
            if (err) return reject(err);
            resolve(results.reverse());
        });
    });
};

module.exports = {
    insertTelemetry,
    getRecentReadings
};
