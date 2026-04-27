const { checkAnomaly }    = require('./mlClient');
const { insertTelemetry } = require('../models/telemetryModel');
const { insertInference } = require('../models/inferenceModel');
const { insertAlert }     = require('../models/alertModel');
const { BOUNDS }          = require('../config/systemBounds');
const socketBroadcaster   = require('./socketBroadcaster');

const clamp = (val, min, max) => Math.min(Math.max(val, min), max);

const processSensorData = async (rawArray) => {
    let processedCount = 0;

    for (const raw of rawArray) {
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

        // The payload timestamp is kept for the WebSocket broadcast so the
        // frontend chart shows time-of-day labels. The DB always uses NOW()
        // — one source of truth, no timezone conversion chain.
        const displayTimestamp = raw.timestamp || new Date().toISOString();

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
        const confidence   = mlResult.confidence    !== undefined ? mlResult.confidence     : null;

        // ── Fault display name + confidence-driven severity ───────────────────
        // conf >= 0.75 → Critical; 0.50–0.74 → Warning; < 0.50 → soft indicator
        const FAULT_LABELS = {
            'F1_Partial_Shading':   'F1 Partial Shading',
            'F2_Inverter_Overload': 'F2 Inverter Overload',
            'F3_Deep_Discharge':    'F3 Deep Discharge',
            'F5_Sensor_Dead':       'F5 Sensor Dead',
            'Uncertain_Anomaly':    'Uncertain Anomaly',
        };
        const faultDisplay = FAULT_LABELS[predLabel] || predLabel;

        const getSeverity = (label, conf) => {
            if (label === 'Uncertain_Anomaly') return 'Warning';
            if (label === 'Normal')            return null;
            if (conf === null || conf >= 0.75) return 'Critical';
            return 'Warning';
        };
        const faultSeverity = getSeverity(predLabel, confidence);

        try {
            // Step 1: INSERT — DB timestamp is always server NOW()
            const telemetryId = await insertTelemetry(dbRecord, 'NOW()');

            // Step 2: INSERT inference
            const inferenceId = await insertInference(telemetryId, sohPercent, anomalyScore, predLabel);

            // Step 3: WebSocket push with display timestamp for frontend chart
            socketBroadcaster.broadcastTelemetry({
                id: telemetryId,
                timestamp: displayTimestamp,
                ...dbRecord,
                pred_label:    predLabel,
                fault_display: faultDisplay,
                confidence,
                anomaly_score: anomalyScore,
                soh_percent:   sohPercent,
            });

            // Step 4: ML-driven fault alert (confidence < 0.5 skips DB insert — soft indicator only)
            if (predLabel !== 'Normal' && predLabel !== 'Error' && faultSeverity) {
                await insertAlert(inferenceId, faultDisplay, faultSeverity, 'NOW()');
                socketBroadcaster.broadcastAlert({
                    alert_type: faultDisplay, alert_severity: faultSeverity,
                    confidence, soc_percent, battery_voltage_v,
                    anomaly_score: anomalyScore, pred_label: predLabel,
                    timestamp: displayTimestamp,
                });
                const confStr = confidence !== null ? ` (conf ${(confidence*100).toFixed(0)}%)` : '';
                console.log(`[Alert] ${faultSeverity} — ${faultDisplay}${confStr}`);
            }

            // Step 5a: Deterministic thermal runaway discriminator
            if (Math.abs(temp_delta_c) >= 10.0) {
                await insertAlert(inferenceId, 'Sensor Degradation (Thermal Runaway)', 'Critical', 'NOW()');
                socketBroadcaster.broadcastAlert({
                    alert_type: 'Sensor Degradation (Thermal Runaway)', alert_severity: 'Critical',
                    soc_percent, battery_voltage_v, anomaly_score: null, timestamp: displayTimestamp,
                });
                console.log(`[Alert] CRITICAL — Thermal Runaway Risk (ΔT=${temp_delta_c}°C)`);
            }

            // Step 5b: Chemistry-aware deep discharge guard
            if (battery_voltage_v < BOUNDS.socBounds.deepDischargeV) {
                await insertAlert(inferenceId, 'Deep Discharge (Battery Protection)', 'Critical', 'NOW()');
                socketBroadcaster.broadcastAlert({
                    alert_type: 'Deep Discharge (Battery Protection)', alert_severity: 'Critical',
                    soc_percent, battery_voltage_v, anomaly_score: null, timestamp: displayTimestamp,
                });
                console.log(
                    `[Alert] CRITICAL — Deep Discharge: ` +
                    `${battery_voltage_v.toFixed(2)}V < ${BOUNDS.socBounds.deepDischargeV}V`
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
