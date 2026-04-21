const { checkAnomaly } = require('./mlClient');
const { insertTelemetry } = require('../models/telemetryModel');
const { insertInference } = require('../models/inferenceModel');
const { insertAlert } = require('../models/alertModel');

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
        const current_to_lux_ratio = (raw.pv_current / (lux + 1)) * 1000;

        const temp_ambient = raw.temp_ambient !== undefined ? raw.temp_ambient : 25.0;
        const temp_probe   = raw.temp_probe !== undefined ? raw.temp_probe : 25.0;
        const temp_delta   = parseFloat((temp_probe - temp_ambient).toFixed(2));

        const enrichedData = {
            pv_voltage:           raw.pv_voltage,
            pv_current:           raw.pv_current,
            batt_voltage:         raw.batt_voltage,
            load_current:         raw.load_current,
            temp_ambient:         temp_ambient,
            temp_probe:           temp_probe,
            irradiance_lux:       lux,
            pv_power_watts:       power_watts,
            net_energy_flux:      net_flux,
            temp_delta:           temp_delta,
            batt_voltage_ma_10:   raw.batt_voltage,
            soc_percent:          soc,
            current_to_lux_ratio: current_to_lux_ratio,
            record_source:        (raw.record_source === 'store_forward') ? 'store_forward' : 'realtime'
        };

        console.log(`[Pipeline] SoC: ${soc.toFixed(1)}% | Lux-Ratio: ${current_to_lux_ratio.toFixed(4)}`);

        // Get ML prediction BEFORE writing to DB
        const mlResult = await checkAnomaly(enrichedData);
        const predLabel    = mlResult.status      || 'Normal';
        const anomalyScore = mlResult.anomaly_score !== undefined ? mlResult.anomaly_score : null;

        const timeExpr = (raw.timestamp_unix && raw.timestamp_unix > 0)
            ? `FROM_UNIXTIME(${raw.timestamp_unix})`
            : 'NOW()';

        try {
            // -- Step 1: INSERT telemetry --
            const telemetryId = await insertTelemetry(enrichedData, timeExpr);

            // -- Step 2: INSERT inference --
            const inferenceId = await insertInference(telemetryId, soc, anomalyScore, predLabel);

            // -- Step 3: INSERT ML alert --
            if (predLabel !== 'Normal' && predLabel !== 'Error') {
                const faultMapping = {
                    'Unknown_Anomaly': 'F1 Partial Shading / Unknown',
                    'Known_Fault':     'F2-F5 Known Fault Pattern'
                };
                const faultCategory = faultMapping[predLabel] || predLabel;
                const severity      = predLabel === 'Known_Fault' ? 'Critical' : 'Warning';
                
                await insertAlert(inferenceId, faultCategory, severity, timeExpr);
                console.log(`[Alert] ${severity} alert logged — ${faultCategory}`);
            }

            // -- Step 4: Deterministic Sensor Fusion Failure Alarm --
            if (Math.abs(temp_delta) >= 10.0) {
                await insertAlert(inferenceId, 'Sensor Degradation (Thermal Runaway)', 'Critical', timeExpr);
                console.log(`[Alert] CRITICAL alert logged — Battery Thermal Runaway Risk detected via Sensor Fusion!`);
            }
        } catch (dbErr) {
            console.error('[Pipeline] Database insertion error:', dbErr);
        }

        processedCount++;
    }
    return processedCount;
};

module.exports = {
    processSensorData
};
