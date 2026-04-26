const jwt = require('jsonwebtoken');

const state = {
    cachedToken: null,
    expiresAt:   0,
};

/**
 * Returns a signed HS256 service JWT for Node → ML-engine calls.
 * Token is cached in memory; regenerated only when within 60 s of expiry.
 * Call once at boot (server.js) to warm the cache before MQTT data arrives.
 */
const getServiceToken = () => {
    const secret = process.env.JWT_SERVICE_SECRET;
    if (!secret) throw new Error('[ServiceAuth] JWT_SERVICE_SECRET is not set.');

    const now = Date.now();
    if (state.cachedToken && (state.expiresAt - now) > 60_000) {
        return state.cachedToken;
    }

    const token = jwt.sign(
        { sub: 'node-backend', role: 'ml-client' },
        secret,
        { expiresIn: '24h' }
    );
    const decoded = jwt.decode(token);
    state.cachedToken = token;
    state.expiresAt   = decoded.exp * 1000;

    console.log('[ServiceAuth] Service JWT (re)generated — valid for 24h.');
    return token;
};

module.exports = { getServiceToken };
