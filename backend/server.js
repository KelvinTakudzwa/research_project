const express = require('express');
const cors = require('cors');
const { connectWithRetry } = require('./src/config/database');
const { initMqttSubscriber } = require('./src/subscribers/mqttSubscriber');
const apiRoutes = require('./src/routes/apiRoutes');

const app = express();
const PORT = 5000;

// Middleware
app.use(express.json());
app.use(cors());

// Mount the robust MVC API routes
app.use('/api', apiRoutes);

// Boot sequence
const startServer = async () => {
    try {
        // 1. Initialize DB connection
        await connectWithRetry();

        // 2. Start MQTT Subscriber explicitly
        initMqttSubscriber();

        // 3. Mount explicit HTTP API
        app.listen(PORT, () => {
            console.log(`[Express] Modular backend server running on port ${PORT}`);
            console.log(`[Express] REST endpoints mapped at HTTP /api`);
        });
    } catch (err) {
        console.error('[Boot] Critical Failure starting backend services:', err);
    }
};

startServer();
