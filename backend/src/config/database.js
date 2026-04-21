const mysql = require('mysql2');

const dbPoolConfig = {
    host: process.env.DB_HOST || 'localhost',
    user: process.env.DB_USER || 'root',
    password: process.env.DB_PASSWORD || '0786682192@Tk',
    database: process.env.DB_NAME || 'solar_monitoring',
    waitForConnections: true,
    connectionLimit: 10,
    queueLimit: 0
};

let db = null;

const connectWithRetry = async (retries = 5, delay = 3000) => {
    while (retries > 0) {
        try {
            db = mysql.createPool(dbPoolConfig);
            // Test the connection
            await new Promise((resolve, reject) => {
                db.query('SELECT 1', (err) => {
                    if (err) reject(err);
                    else resolve();
                });
            });
            console.log(`[DB] Successfully connected to MySQL at ${dbPoolConfig.host}`);
            return db;
        } catch (err) {
            retries -= 1;
            console.error(`[DB] Connection failed. Retries left: ${retries}. Waiting ${delay/1000}s...`);
            if (retries === 0) {
                console.error('[DB] Fatally failed to connect to MySQL. Exiting.');
                process.exit(1);
            }
            await new Promise(r => setTimeout(r, delay));
        }
    }
};

const getDb = () => {
    if (!db) throw new Error("Database not initialized yet.");
    return db;
};

module.exports = {
    connectWithRetry,
    getDb
};
