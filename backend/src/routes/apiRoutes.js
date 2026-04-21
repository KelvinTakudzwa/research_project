const express = require('express');
const router = express.Router();
const apiController = require('../controllers/apiController');

router.get('/readings', apiController.getReadings);
router.get('/alerts', apiController.getAlerts);
router.post('/data', apiController.postData);
router.get('/calibration_log', apiController.getCalibrationLog);
router.post('/trigger_retraining', apiController.triggerRetrain);

module.exports = router;
