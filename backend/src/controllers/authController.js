const jwt    = require('jsonwebtoken');
const bcrypt = require('bcryptjs');

// Bcrypt hashes contain $ signs that Docker Compose expands when set as env vars.
// To avoid that, DASHBOARD_PASSWORD is stored as plain text in .env and hashed
// once at module load time. The hash lives only in process memory — never on disk.
const _plainPassword = process.env.DASHBOARD_PASSWORD;
const PASSWORD_HASH  = _plainPassword ? bcrypt.hashSync(_plainPassword, 10) : null;

/**
 * POST /auth/login
 * Body: { username, password }
 * Validates against DASHBOARD_USER + DASHBOARD_PASSWORD env vars.
 * Returns { token } signed with JWT_SECRET, expiresIn 24h.
 * No user database — single-operator monitoring system.
 */
const login = async (req, res) => {
    const { username, password } = req.body || {};

    if (!username || !password) {
        return res.status(400).json({ error: 'username and password are required.' });
    }

    const expectedUser = process.env.DASHBOARD_USER;
    const secret       = process.env.JWT_SECRET;

    if (!expectedUser || !PASSWORD_HASH || !secret) {
        return res.status(500).json({ error: 'Auth not configured on server.' });
    }

    const usernameMatch = username === expectedUser;
    const passwordMatch = await bcrypt.compare(password, PASSWORD_HASH);

    if (!usernameMatch || !passwordMatch) {
        return res.status(401).json({ error: 'Invalid credentials.' });
    }

    const token = jwt.sign(
        { sub: username, role: 'dashboard-user' },
        secret,
        { expiresIn: '24h' }
    );

    return res.json({ token });
};

module.exports = { login };
