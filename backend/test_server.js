// test_server.js
// A minimal Echo Server to verify IoT Node connectivity and demonstrate Distributed Computing.

const express = require('express');
const app = express();
const PORT = 5000;

// Middleware to parse JSON bodies
app.use(express.json());

// API Endpoint to receive data
app.post('/api/data', (req, res) => {
    console.log("\n[IoT Node] Data Packet Received:");
    const rawData = req.body;
    console.log("RAW:", rawData);

    // DISTRIBUTED COMPUTING LAYER
    // The ESP32 sends raw sensor data. We calculate high-level features here.
    
    // 1. Calculate SoC (State of Charge)
    // Formula: SoC% = (V_current - V_min) / (V_max - V_min) * 100
    const v_min = 10.5;
    const v_max = 14.4;
    let soc = ((rawData.batt_voltage - v_min) / (v_max - v_min)) * 100;
    
    // Clamp between 0 and 100
    soc = Math.min(Math.max(soc, 0), 100);
    
    // 2. Calculate Power
    const power = rawData.pv_voltage * rawData.pv_current;

    console.log("--- PROCESSED FEATURES ---");
    console.log(`SoC:       ${soc.toFixed(2)}%`);
    console.log(`PV Power:  ${power.toFixed(2)} W`);
    console.log("--------------------------");

    // Send success response back to ESP32
    res.status(200).send({ 
        status: "Success", 
        timestamp: new Date(),
        server_message: "Data processed locally."
    });
});

// Start Server
app.listen(PORT, '0.0.0.0', () => {
    console.log(`\n>>> Echo Server running on port ${PORT}`);
    console.log(`>>> Connect your ESP32 to: http://<YOUR_PC_IP>:${PORT}/api/data`);
});
