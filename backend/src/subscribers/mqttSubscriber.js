const fs   = require('fs');
const path = require('path');
const mqtt = require('mqtt');
const { processSensorData } = require('../services/dataProcessor');

const initMqttSubscriber = () => {
    const MQTT_BROKER = process.env.MQTT_BROKER || 'mqtts://localhost:8883';
    const MQTT_TOPIC  = 'solar/data';

    // TLS: load the CA certificate so the broker's self-signed cert is trusted.
    // The file is mounted into the container at /app/certs/ca.crt via docker-compose.
    const CA_PATH = path.join('/app', 'certs', 'ca.crt');
    const tlsOptions = fs.existsSync(CA_PATH)
        ? { ca: fs.readFileSync(CA_PATH), rejectUnauthorized: true }
        : {};

    if (Object.keys(tlsOptions).length) {
        console.log('[MQTT] TLS enabled — CA cert loaded from', CA_PATH);
    } else {
        console.warn('[MQTT] CA cert not found at', CA_PATH, '— connecting without TLS verification.');
    }

    const mqttClient = mqtt.connect(MQTT_BROKER, {
        ...tlsOptions,
        clientId:        'NodeJS_SolarBackend',
        clean:           true,
        reconnectPeriod: 3000,
        connectTimeout:  10000,
    });

    mqttClient.on('connect', () => {
        console.log('[MQTT] Connected to Mosquitto broker at', MQTT_BROKER);
        mqttClient.subscribe(MQTT_TOPIC, { qos: 1 }, (err) => {
            if (err) {
                console.error('[MQTT] Subscription error:', err);
            } else {
                console.log(`[MQTT] Subscribed to topic: ${MQTT_TOPIC} (QoS 1)`);
            }
        });
    });

    mqttClient.on('message', (topic, messageBuffer) => {
        setImmediate(async () => {
            const raw = messageBuffer.toString();
            console.log(`[MQTT] Received on '${topic}'`);
            try {
                let payload = JSON.parse(raw);
                if (!Array.isArray(payload)) payload = [payload];
                const count = await processSensorData(payload);
                console.log(`[MQTT] Pipeline complete — ${count} reading(s) processed.`);
            } catch (err) {
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

module.exports = { initMqttSubscriber };
