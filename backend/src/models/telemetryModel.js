const { getDb } = require('../config/database');

const insertTelemetry = (data, timestampExpr) => {
    return new Promise((resolve, reject) => {
        const sql = `
            INSERT INTO telemetry_data (
                timestamp_utc,
                pv_voltage_v, pv_current_a, pv_power_w,
                battery_voltage_v, battery_current_a, battery_power_w,
                ac_voltage_v, ac_current_a, ac_power_w, ac_power_factor,
                irradiance_wm2, ambient_temp_c, battery_temp_c,
                net_energy_flux_w, temp_delta_c, soc_percent,
                is_offline_buffered, record_source
            )
            VALUES (${timestampExpr}, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `;
        const values = [
            data.pv_voltage_v,      data.pv_current_a,    data.pv_power_w,
            data.battery_voltage_v, data.battery_current_a, data.battery_power_w,
            data.ac_voltage_v,      data.ac_current_a,    data.ac_power_w,    data.ac_power_factor,
            data.irradiance_wm2,    data.ambient_temp_c,  data.battery_temp_c,
            data.net_energy_flux_w, data.temp_delta_c,    data.soc_percent,
            data.is_offline_buffered, data.record_source,
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
                t.telemetry_id          AS id,
                t.timestamp_utc         AS timestamp,
                t.pv_voltage_v,         t.pv_current_a,       t.pv_power_w,
                t.battery_voltage_v,    t.battery_current_a,  t.battery_power_w,
                t.ac_voltage_v,         t.ac_current_a,       t.ac_power_w,  t.ac_power_factor,
                t.irradiance_wm2,       t.ambient_temp_c,     t.battery_temp_c,
                t.net_energy_flux_w,    t.temp_delta_c,       t.soc_percent,
                t.is_offline_buffered,  t.record_source,
                i.pred_label,           i.anomaly_score,      i.soh_percent
            FROM telemetry_data t
            LEFT JOIN inference_results i ON t.telemetry_id = i.telemetry_id
            ORDER BY t.timestamp_utc DESC
            LIMIT ?
        `;
        getDb().query(sql, [limit], (err, results) => {
            if (err) return reject(err);
            resolve(results.reverse());
        });
    });
};

module.exports = { insertTelemetry, getRecentReadings };
