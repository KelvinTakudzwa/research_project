import React, { createContext, useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { io } from 'socket.io-client';

export const SolarDataContext = createContext();

// Attach the stored JWT to every outgoing API request.
axios.interceptors.request.use((config) => {
    const token = localStorage.getItem('solar_token');
    if (token) config.headers['Authorization'] = `Bearer ${token}`;
    return config;
});

// On 401, clear token and redirect to login.
axios.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            localStorage.removeItem('solar_token');
            window.location.href = '/login';
        }
        return Promise.reject(error);
    }
);

const MAX_HISTORY = 100;

export const SolarDataProvider = ({ children }) => {
    const [latest,         setLatest]         = useState(null);
    const [history,        setHistory]        = useState([]);
    const [alerts,         setAlerts]         = useState([]);
    const [calibrationLog, setCalibrationLog] = useState([]);
    const [isPolling,      setIsPolling]      = useState(true);
    const socketRef = useRef(null);

    // ── WebSocket connection ─────────────────────────────────────────────────
    useEffect(() => {
        const socket = io('/', {
            transports: ['websocket', 'polling'],
            auth: { token: localStorage.getItem('solar_token') },
        });
        socketRef.current = socket;

        socket.on('connect', () => {
            console.log('[Socket.IO] Connected:', socket.id);
        });

        // Real-time telemetry push — one event per MQTT reading
        socket.on('telemetry', (row) => {
            setLatest(row);
            setHistory((prev) => {
                const next = [...prev, row];
                // Keep a rolling window matching the REST endpoint limit
                return next.length > MAX_HISTORY ? next.slice(next.length - MAX_HISTORY) : next;
            });
        });

        // Real-time alert push — fires immediately when dataProcessor raises one
        socket.on('alert', (alert) => {
            setAlerts((prev) => [alert, ...prev].slice(0, 50));
        });

        socket.on('disconnect', (reason) => {
            console.log('[Socket.IO] Disconnected:', reason);
        });

        return () => socket.disconnect();
    }, []);

    // ── Initial data load (REST) ─────────────────────────────────────────────
    // Populate history and alerts from DB on first mount, then let WebSocket
    // keep them live. This ensures the chart has data before the next MQTT tick.
    useEffect(() => {
        const loadInitial = async () => {
            try {
                const [readingsRes, alertsRes] = await Promise.all([
                    axios.get('/api/readings'),
                    axios.get('/api/alerts'),
                ]);
                const data = readingsRes.data;
                if (data.length > 0) {
                    setLatest(data[data.length - 1]);
                    setHistory(data);
                }
                setAlerts(alertsRes.data);
                localStorage.setItem('solar_alerts', JSON.stringify(alertsRes.data));
            } catch (err) {
                if (err.response?.status !== 401) {
                    console.error('Initial load error:', err.message);
                }
            }
        };
        loadInitial();
    }, []);

    // ── Calibration log (low-frequency poll — doesn't need real-time push) ───
    useEffect(() => {
        if (!isPolling) return;
        const fetchCal = async () => {
            try {
                const res = await axios.get('/api/calibration_log');
                if (Array.isArray(res.data)) setCalibrationLog(res.data);
            } catch {
                // Silently omit
            }
        };
        fetchCal();
        const interval = setInterval(fetchCal, 30_000);
        return () => clearInterval(interval);
    }, [isPolling]);

    return (
        <SolarDataContext.Provider value={{
            latest,
            history,
            alerts,
            calibrationLog,
            setCalibrationLog,
            setIsPolling,
        }}>
            {children}
        </SolarDataContext.Provider>
    );
};
