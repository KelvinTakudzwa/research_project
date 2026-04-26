const express   = require('express');
const cors      = require('cors');
const { connectWithRetry }   = require('./src/config/database');
const { initMqttSubscriber } = require('./src/subscribers/mqttSubscriber');
const { getServiceToken }    = require('./src/services/serviceAuth');
const socketBroadcaster      = require('./src/services/socketBroadcaster');
const apiRoutes  = require('./src/routes/apiRoutes');
const authRoutes = require('./src/routes/authRoutes');

const app  = express();
const PORT = 5000;

app.use(express.json());
app.use(cors());

app.use('/api',  apiRoutes);
app.use('/auth', authRoutes);

const startServer = async () => {
    try {
        // 1. Initialize DB connection
        await connectWithRetry();

        // 2. Start MQTT subscriber
        initMqttSubscriber();

        // 3. Eager-generate + cache the service JWT
        getServiceToken();

        // 4. Start HTTP server and capture the reference socket.io needs
        const httpServer = app.listen(PORT, () => {
            console.log(`[Express] Backend running on port ${PORT}`);
            console.log(`[Express] REST  → /api  |  Auth → /auth`);
        });

        // 5. Attach WebSocket server to the same HTTP server
        socketBroadcaster.init(httpServer);

    } catch (err) {
        console.error('[Boot] Critical failure:', err);
    }
};

startServer();
