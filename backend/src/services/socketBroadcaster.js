const { Server } = require('socket.io');

let io = null;

/**
 * Attaches socket.io to the existing Express HTTP server.
 * Called once in server.js during boot — before any MQTT messages arrive.
 */
const init = (httpServer) => {
    io = new Server(httpServer, {
        cors: { origin: '*' },
        // Allow socket.io to fall back to long-polling if the Nginx WebSocket
        // upgrade header is misconfigured, rather than failing silently.
        transports: ['websocket', 'polling'],
    });

    io.on('connection', (socket) => {
        console.log(`[Socket.IO] Client connected: ${socket.id}`);
        socket.on('disconnect', () => {
            console.log(`[Socket.IO] Client disconnected: ${socket.id}`);
        });
    });

    console.log('[Socket.IO] WebSocket server attached to HTTP server.');
    return io;
};

/** Pushes the latest telemetry + ML row to all connected dashboard clients. */
const broadcastTelemetry = (row) => {
    if (io) io.emit('telemetry', row);
};

/** Pushes a new alert event to all connected dashboard clients immediately. */
const broadcastAlert = (alert) => {
    if (io) io.emit('alert', alert);
};

module.exports = { init, broadcastTelemetry, broadcastAlert };
