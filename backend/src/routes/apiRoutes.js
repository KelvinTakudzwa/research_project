const express = require('express');
const router  = express.Router();
const apiController  = require('../controllers/apiController');
const { authMiddleware } = require('../middleware/auth');

// POST /api/data — MQTT-to-DB ingest path (called internally by Node, not a public endpoint)
router.post('/data', apiController.postData);

// All remaining routes require a valid dashboard JWT
router.get('/readings',        authMiddleware, apiController.getReadings);
router.get('/alerts',          authMiddleware, apiController.getAlerts);
router.get('/calibration_log', authMiddleware, apiController.getCalibrationLog);
router.post('/trigger_retraining', authMiddleware, apiController.triggerRetrain);

module.exports = router;
