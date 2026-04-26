const { checkAnomaly }                    = require('./mlClient');
const { insertTelemetry, getLastTimestamp } = require('../models/telemetryModel');
const { insertInference }                 = require('../models/inferenceModel');
const { insertAlert }                     = require('../models/alertModel');
const { BOUNDS }                          = require('../config/systemBounds');
const socketBroadcaster                   = require('./socketBroadcaster');

const clamp = (val, min, max) => Math.min(Math.max(val, min), max);

// ── Monotonicity tracker ──────────────────────────────────────────────────────
// Initialised lazily on the first MQTT message by querying the DB for the most
// recent stored timestamp. Persists in memory for the server's lifetime so that
// subsequent messages skip the DB query entirely.
let lastInsertedMs = null;

const initLastTimestamp = async () => {
    if (lastInsertedMs !== null) return;
    try {
        const lastTs = await getLastTimestamp();
        lastInsertedMs = lastTs ? new Date(lastTs).getTime() : 0;
        console.log(
            `[Monotonicity] Initialised — last DB timestamp: ` +
            `${lastTs ? lastTs : 'none (empty table)'}`
        );
    } catch (err) {
        console.warn('[Monotonicity] Could not read last timestamp from DB:', err.message);
        lastInsertedMs = 0;   // fail-open: allow all records through
    }
};

const processSensorData = async (rawArray) => {
    // ── Lazy initialisation from DB on first call ─────────────────────────────
    await initLastTimestamp();

    // ── Sort the incoming batch by timestamp (ascending) ─────────────────────
    // Critical for store-and-forward bursts: LittleFS records arrive as separate
    // MQTT messages in order, but within a single multi-record message the order
    // cannot be guaranteed. Sorting ensures time-series integrity regardless.
    const parseMs = (raw) => {
        if (!raw.timestamp) return 0;
        const ms = new Date(raw.timestamp).getTime();
        return isNaN(ms) ? 0 : ms;
    };

    const sorted = [...rawArray].sort((a, b) => parseMs(a) - parseMs(b));

    let processedCount = 0;

    for (const raw of sorted) {
        // ── Monotonicity check ────────────────────────────────────────────────
        // Skip any record whose timestamp is not strictly greater than the last
        // inserted one. Catches: out-of-order backlog bursts, clock regressions
        // (RTC reset to epoch), and exact duplicates (<=, not just <).
        const recordMs = parseMs(raw);
        if (recordMs > 0 && recordMs <= lastInsertedMs) {
            console.warn(
                `[Monotonicity] VIOLATION — skipping record: ` +
                `${raw.timestamp} (${recordMs}ms) <= last inserted (${lastInsertedMs}ms). ` +
                `Source: ${raw.record_source || raw.is_offline_buffered ? 'store_and_forward' : 'realtime'}`
            );
            continue;
        }

        // ── 4a. Field rename + parse ──────────────────────────────────────────
        const pv_voltage_v      = parseFloat(raw.pv_voltage_v)      || 0;
        const pv_current_a      = parseFloat(raw.pv_current_a)      || 0;
        const battery_voltage_v = parseFloat(raw.battery_voltage_v) || 0;
        const battery_current_a = parseFloat(raw.battery_current_a) || 0;
        const ac_voltage_v      = parseFloat(raw.ac_voltage_v)      || 0;
        const ac_current_a      = parseFloat(raw.ac_current_a)      || 0;
        const ac_power_w        = parseFloat(raw.ac_power_w)        || 0;
        const ac_power_factor   = parseFloat(raw.ac_power_factor)   || 0;
        const irradiance_wm2    = parseFloat(raw.irradiance_wm2)    || 0;
        const ambient_temp_c    = raw.ambient_temp_c  !== undefined ? parseFloat(raw.ambient_temp_c)  : 25.0;
        const battery_temp_c    = raw.battery_temp_c  !== undefined ? parseFloat(raw.battery_temp_c)  : 25.0;
        const is_offline_buffered = raw.is_offline_buffered ? 1 : 0;

        // Timestamp: convert ISO 8601 to MySQL DATETIME (strips T and Z)
        const toMySQLDatetime = (iso) => {
            const d = new Date(iso);
            return isNaN(d.getTime()) ? null : d.toISOString().slice(0, 19).replace('T', ' ');
        };
        const mysqlTs       = raw.timestamp ? toMySQLDatetime(raw.timestamp) : null;
        const timestamp_utc = mysqlTs ? `'${mysqlTs}'` : 'NOW()';

        // ── 4b. Derive contextual fields ──────────────────────────────────────
        const pv_power_w        = parseFloat((pv_voltage_v * pv_current_a).toFixed(4));
        const battery_power_w   = parseFloat((battery_voltage_v * battery_current_a).toFixed(4));
        const net_energy_flux_w = parseFloat((pv_power_w - ac_power_w).toFixed(4));
        const temp_delta_c      = parseFloat((battery_temp_c - ambient_temp_c).toFixed(2));

        // SoC: chemistry-correct voltage-based formula
        const V_min = BOUNDS.socBounds.vMin;
        const V_max = BOUNDS.socBounds.vMax;
        const soc_percent = clamp(
            ((battery_voltage_v - V_min) / (V_max - V_min)) * 100,
            0, 100
        );

        // ── 4c. Min-Max normalization ─────────────────────────────────────────
        const norm = {
            pv_voltage_norm:      pv_voltage_v      / BOUNDS.pvVoltage.max,
            pv_current_norm:      pv_current_a      / BOUNDS.pvCurrent.max,
            pv_power_norm:        pv_power_w        / BOUNDS.pvPower.max,
            battery_voltage_norm: battery_voltage_v / BOUNDS.battVoltage.max,
            battery_current_norm: battery_current_a / BOUNDS.battCurrent.max,
            battery_power_norm:   battery_power_w   / BOUNDS.battPower.max,
            ac_power_norm:        ac_power_w        / BOUNDS.acPower.max,
            ac_current_norm:      ac_current_a      / BOUNDS.acCurrent.max,
            net_flux_norm:        net_energy_flux_w / BOUNDS.pvPower.max,
            irradiance_norm:      irradiance_wm2    / BOUNDS.irradiance.max,
            soc_percent,
            ac_power_factor,
            ambient_temp_c,
            battery_temp_c,
            temp_delta_c,
        };

        // ── 4d. Split: DB record vs ML vector ─────────────────────────────────
        const dbRecord = {
            pv_voltage_v, pv_current_a, pv_power_w,
            battery_voltage_v, battery_current_a, battery_power_w,
            ac_voltage_v, ac_current_a, ac_power_w, ac_power_factor,
            irradiance_wm2, ambient_temp_c, battery_temp_c, temp_delta_c,
            net_energy_flux_w, soc_percent,
            is_offline_buffered,
            // Prefer the explicit field from firmware; fall back to derivation
            // for the simulator which does not send record_source.
            record_source: raw.record_source || (is_offline_buffered ? 'store_forward' : 'realtime'),
        };

        console.log(
            `[Pipeline] SoC: ${soc_percent.toFixed(1)}% | ` +
            `PV: ${pv_power_w.toFixed(1)}W | AC: ${ac_power_w.toFixed(1)}W | ` +
            `Flux: ${net_energy_flux_w.toFixed(1)}W | src: ${dbRecord.record_source}`
        );

        const mlResult     = await checkAnomaly(norm);
        const predLabel    = mlResult.status        || 'Normal';
        const anomalyScore = mlResult.anomaly_score !== undefined ? mlResult.anomaly_score : null;
        const sohPercent   = mlResult.soh_percent   !== undefined ? mlResult.soh_percent   : soc_percent;

        try {
            // Step 1: INSERT telemetry
            const telemetryId = await insertTelemetry(dbRecord, timestamp_utc);

            // Step 2: INSERT inference
            const inferenceId = await insertInference(telemetryId, sohPercent, anomalyScore, predLabel);

            // Step 3: Update monotonicity tracker AFTER confirmed DB insert
            if (recordMs > 0) lastInsertedMs = recordMs;

            // Step 4: WebSocket push
            socketBroadcaster.broadcastTelemetry({
                id: telemetryId,
                timestamp: mysqlTs || new Date().toISOString(),
                ...dbRecord,
                pred_label:    predLabel,
                anomaly_score: anomalyScore,
                soh_percent:   sohPercent,
            });

            // Step 5: ML-driven alert
            if (predLabel !== 'Normal' && predLabel !== 'Error') {
                const faultMapping = {
                    'Unknown_Anomaly':         'F1 Partial Shading / Unknown',
                    'Known_Fault_Degradation': 'F2-F5 Known Fault Pattern',
                };
                const faultCategory = faultMapping[predLabel] || predLabel;
                const severity      = predLabel === 'Known_Fault_Degradation' ? 'Critical' : 'Warning';
                await insertAlert(inferenceId, faultCategory, severity, timestamp_utc);
                const alertPayload = {
                    alert_type: faultCategory, alert_severity: severity,
                    soc_percent, battery_voltage_v, anomaly_score: anomalyScore,
                    pred_label: predLabel, timestamp: mysqlTs || new Date().toISOString(),
                };
                socketBroadcaster.broadcastAlert(alertPayload);
                console.log(`[Alert] ${severity} — ${faultCategory}`);
            }

            // Step 6a: Deterministic thermal runaway discriminator
            if (Math.abs(temp_delta_c) >= 10.0) {
                await insertAlert(inferenceId, 'Sensor Degradation (Thermal Runaway)', 'Critical', timestamp_utc);
                socketBroadcaster.broadcastAlert({
                    alert_type: 'Sensor Degradation (Thermal Runaway)', alert_severity: 'Critical',
                    soc_percent, battery_voltage_v, anomaly_score: null,
                    timestamp: mysqlTs || new Date().toISOString(),
                });
                console.log(`[Alert] CRITICAL — Thermal Runaway Risk (ΔT=${temp_delta_c}°C)`);
            }

            // Step 6b: Chemistry-aware deep discharge guard
            if (battery_voltage_v < BOUNDS.socBounds.deepDischargeV) {
                await insertAlert(inferenceId, 'Deep Discharge (Battery Protection)', 'Critical', timestamp_utc);
                socketBroadcaster.broadcastAlert({
                    alert_type: 'Deep Discharge (Battery Protection)', alert_severity: 'Critical',
                    soc_percent, battery_voltage_v, anomaly_score: null,
                    timestamp: mysqlTs || new Date().toISOString(),
                });
                console.log(
                    `[Alert] CRITICAL — Deep Discharge: ` +
                    `${battery_voltage_v.toFixed(2)}V < ${BOUNDS.socBounds.deepDischargeV}V ` +
                    `(${BOUNDS.socBounds.chemistry} threshold)`
                );
            }
        } catch (dbErr) {
            console.error('[Pipeline] Database insertion error:', dbErr);
        }

        processedCount++;
    }
    return processedCount;
};

module.exports = { processSensorData };
