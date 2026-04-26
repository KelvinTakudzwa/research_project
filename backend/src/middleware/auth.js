const jwt = require('jsonwebtoken');

/**
 * Express middleware — validates dashboard user JWTs.
 * Reads Authorization: Bearer <token>, verifies against JWT_SECRET.
 * On success attaches req.user = decoded payload.
 */
const authMiddleware = (req, res, next) => {
    const header = req.headers['authorization'];
    if (!header || !header.startsWith('Bearer ')) {
        return res.status(401).json({ error: 'Unauthorized' });
    }

    const token  = header.slice(7);
    const secret = process.env.JWT_SECRET;
    if (!secret) return res.status(500).json({ error: 'JWT_SECRET not configured.' });

    try {
        req.user = jwt.verify(token, secret);
        next();
    } catch {
        return res.status(401).json({ error: 'Unauthorized' });
    }
};

module.exports = { authMiddleware };
