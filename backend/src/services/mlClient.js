// Native Fetch is available in Node > 18
const checkAnomaly = async (dataPacket) => {
    const ML_API_URL = process.env.ML_API_URL || 'http://127.0.0.1:8000';
    const controller = new AbortController();
    const timeout    = setTimeout(() => controller.abort(), 5000); // 5 second hard timeout
    try {
        const response = await fetch(`${ML_API_URL}/predict`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(dataPacket),
            signal: controller.signal
        });
        clearTimeout(timeout);
        if (!response.ok) {
            console.warn(`[ML] API returned ${response.status} — defaulting to Normal.`);
            return { status: 'Normal', anomaly_score: null };
        }
        return await response.json();
    } catch (error) {
        clearTimeout(timeout);
        if (error.name === 'AbortError') {
            console.warn('[ML] Request timed out after 5s — defaulting to Normal.');
        } else {
            console.warn('[ML] Service unreachable:', error.message, '— defaulting to Normal.');
        }
        // Fail open: save the raw data as Normal so the DB keeps populating
        return { status: 'Normal', anomaly_score: null };
    }
};

module.exports = {
    checkAnomaly
};
