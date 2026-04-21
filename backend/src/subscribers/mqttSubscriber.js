const mqtt = require('mqtt');
const { processSensorData } = require('../services/dataProcessor');

const initMqttSubscriber = () => {
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

    mqttClient.on('message', (topic, messageBuffer) => {
        // Use setImmediate so a crash in one message never blocks the next
        setImmediate(async () => {
            const raw = messageBuffer.toString();
            console.log(`[MQTT] Received on '${topic}'`);
            try {
                let payload = JSON.parse(raw);
                if (!Array.isArray(payload)) payload = [payload];
                const count = await processSensorData(payload);
                console.log(`[MQTT] Pipeline complete — ${count} reading(s) processed.`);
            } catch (err) {
                // Log and continue — subscription stays alive
                console.error('[MQTT] Handler error (subscription preserved):', err.message);
            }
        });
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

    return mqttClient;
};

module.exports = {
    initMqttSubscriber
};
