import React, { createContext, useState, useEffect } from 'react';
import axios from 'axios';

// Create Context
export const SolarDataContext = createContext();

export const SolarDataProvider = ({ children }) => {
    const [latest, setLatest] = useState(null);
    const [history, setHistory] = useState([]);
    const [alerts, setAlerts] = useState([]);
    const [calibrationLog, setCalibrationLog] = useState([]);
    const [isPolling, setIsPolling] = useState(true);

    const fetchData = async () => {
        if (!isPolling) return;
        try {
            const [readingsRes, alertsRes] = await Promise.all([
                axios.get('/api/readings'),
                axios.get('/api/alerts')
            ]);
            
            const data = readingsRes.data;
            if (data.length > 0) {
                setLatest(data[0]); // most recent is at index 0
                setHistory(data.reverse()); // chart wants chronological (oldest to newest)
            }
            
            setAlerts(alertsRes.data);
            localStorage.setItem('solar_alerts', JSON.stringify(alertsRes.data));

            // Occasionally poll calibration log (could be optimized)
            try {
                const calRes = await axios.get('/api/calibration_log');
                if (Array.isArray(calRes.data)) setCalibrationLog(calRes.data);
            } catch (calErr) {
                // Silently omit if fails
            }

        } catch (err) {
            console.error("Solar API Error:", err.message);
        }
    };

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 2000);
        return () => clearInterval(interval);
    }, [isPolling]);

    return (
        <SolarDataContext.Provider value={{ 
            latest, 
            history, 
            alerts, 
            calibrationLog,
            setCalibrationLog,
            setIsPolling 
        }}>
            {children}
        </SolarDataContext.Provider>
    );
};
