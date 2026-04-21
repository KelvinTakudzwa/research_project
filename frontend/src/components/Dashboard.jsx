import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { AlertTriangle, Battery, Sun, Activity, Zap, BrainCircuit, RefreshCw, CheckCircle, XCircle, Thermometer, ThermometerSun, Flame } from 'lucide-react';
import RealTimeChart from './RealTimeChart';
import StatusCard from './StatusCard';

const Dashboard = () => {
    const [latest, setLatest] = useState(() => {
        const saved = localStorage.getItem('solar_latest');
        return saved ? JSON.parse(saved) : null;
    });
    const [history, setHistory] = useState(() => {
        const saved = localStorage.getItem('solar_history');
        return saved ? JSON.parse(saved) : [];
    });
    const [alerts, setAlerts] = useState(() => {
        const saved = localStorage.getItem('solar_alerts');
        return saved ? JSON.parse(saved) : [];
    });
    const [calibrationLog, setCalibrationLog] = useState([]);
    const [retrainStatus, setRetrainStatus] = useState('idle'); // 'idle' | 'loading' | 'success' | 'error'
    const [retrainMsg, setRetrainMsg]   = useState('');

    const fetchData = async () => {
        try {
            const historyRes = await axios.get('/api/readings');
            const newHistory = historyRes.data;
            if (!Array.isArray(newHistory)) throw new Error("Expected array for history.");
            setHistory(newHistory);
            localStorage.setItem('solar_history', JSON.stringify(newHistory));
            if (newHistory.length > 0) {
                const newLatest = newHistory[newHistory.length - 1];
                setLatest(newLatest);
                localStorage.setItem('solar_latest', JSON.stringify(newLatest));
            }

            const alertsRes = await axios.get('/api/alerts');
            const newAlerts = alertsRes.data;
            if (!Array.isArray(newAlerts)) throw new Error("Expected array for alerts.");
            setAlerts(newAlerts);
            localStorage.setItem('solar_alerts', JSON.stringify(newAlerts));

            const calRes = await axios.get('/api/calibration_log');
            if (Array.isArray(calRes.data)) setCalibrationLog(calRes.data);

        } catch (err) {
            console.error("API Error (falling back to cache):", err.message);
        }
    };

    const triggerRetraining = async () => {
        setRetrainStatus('loading');
        setRetrainMsg('Dispatching retraining job...');
        try {
            const currentLogLength = calibrationLog.length;
            await axios.post('/api/trigger_retraining');
            setRetrainMsg('Retraining in progress (background)...');
            
            let attempts = 0;
            const pollLogs = async () => {
                try {
                    const calRes = await axios.get('/api/calibration_log');
                    if (calRes.data.length > currentLogLength) {
                        setCalibrationLog(calRes.data);
                        setRetrainStatus('success');
                        setRetrainMsg('Retraining completed successfully!');
                        setTimeout(() => setRetrainStatus('idle'), 5000);
                        return;
                    }
                } catch (e) {}
                
                attempts++;
                if (attempts < 20) { // Max 60 seconds
                    setTimeout(pollLogs, 3000);
                } else {
                    setRetrainStatus('error');
                    setRetrainMsg('Timed out waiting for completion.');
                    setTimeout(() => setRetrainStatus('idle'), 5000);
                }
            };
            
            // Start polling after 3 seconds
            setTimeout(pollLogs, 3000);
            
        } catch (err) {
            setRetrainStatus('error');
            setRetrainMsg(err.response?.data?.message || 'ML API unreachable.');
            setTimeout(() => setRetrainStatus('idle'), 6000);
        }
    };

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 2000);
        return () => clearInterval(interval);
    }, []);

    if (!latest) return (
        <div className="flex items-center justify-center mt-20 text-slate-400 gap-3">
            <RefreshCw size={18} className="animate-spin" />
            <span>Loading System Data... (Waiting for first reading)</span>
        </div>
    );

    const healthStatus = latest.pred_label === 'Normal' ? 'Healthy' : 'Critical';

    // Button style based on status
    const btnStyles = {
        idle:    'bg-indigo-600 hover:bg-indigo-500 text-white',
        loading: 'bg-slate-600 text-slate-300 cursor-not-allowed',
        success: 'bg-emerald-600 text-white',
        error:   'bg-red-600 text-white',
    };
    const BtnIcon = {
        idle:    <BrainCircuit size={16} />,
        loading: <RefreshCw size={16} className="animate-spin" />,
        success: <CheckCircle size={16} />,
        error:   <XCircle size={16} />,
    };

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {/* KPI Cards */}
            <StatusCard
                title="Irradiance"
                value={`${latest.irradiance_lux?.toFixed(0)} Lux`}
                icon={<Sun size={24} />}
                color="text-yellow-200"
            />
            <StatusCard
                title="Battery SoC"
                value={`${latest.soc_percent?.toFixed(1)}%`}
                icon={<Battery size={24} />}
                color="text-green-400"
            />
            <StatusCard
                title="PV Power"
                value={`${latest.pv_power_watts?.toFixed(1)} W`}
                icon={<Zap size={24} />}
                color="text-yellow-400"
            />
            <StatusCard
                title="System Health"
                value={healthStatus}
                subValue={latest.pred_label}
                icon={<Activity size={24} />}
                color={latest.pred_label === 'Normal' ? "text-emerald-400" : "text-red-400"}
            />
            
            {/* Dual Sensor Fusion Row */}
            <StatusCard
                title="Ambient Temp"
                value={latest.temp_ambient !== undefined ? `${latest.temp_ambient?.toFixed(1)}°C` : 'N/A'}
                subValue="DS3231 Sensor"
                icon={<ThermometerSun size={24} />}
                color="text-blue-300"
            />
            <StatusCard
                title="Battery Probe"
                value={latest.temp_probe !== undefined ? `${latest.temp_probe?.toFixed(1)}°C` : 'N/A'}
                subValue="DS18B20 Surface"
                icon={<Thermometer size={24} />}
                color="text-orange-300"
            />
            <StatusCard
                title="Thermal Stress"
                value={latest.temp_delta !== undefined ? `${latest.temp_delta?.toFixed(1)}°C` : 'N/A'}
                subValue="Sensor Fusion Δ"
                icon={<Flame size={24} />}
                color={latest.temp_delta !== undefined && Math.abs(latest.temp_delta) >= 10.0 ? "text-red-500 font-bold" : "text-rose-400"}
            />
            <StatusCard
                title="Active Alerts"
                value={alerts.length}
                icon={<AlertTriangle size={24} />}
                color="text-orange-400"
            />

            {/* Main Chart Section */}
            <div className="md:col-span-2 lg:col-span-3 glass-panel p-6">
                <h2 className="text-lg font-bold mb-4 text-indigo-300 uppercase tracking-widest text-xs">Real-Time Performance</h2>
                <div className="h-[26rem] w-full">
                    <RealTimeChart data={history} />
                </div>
            </div>

            {/* Alerts Feed */}
            <div className="md:col-span-2 lg:col-span-1 glass-panel p-6 h-[500px] overflow-hidden flex flex-col">
                <h2 className="text-lg font-bold mb-4 text-orange-300 uppercase tracking-widest text-xs">Recent Alerts</h2>
                <div className="space-y-3 overflow-y-auto pr-2 custom-scrollbar flex-1">
                    {alerts.map((alert) => (
                        <div key={alert.id} className="p-3 bg-slate-800/50 rounded-lg border-l-4 border-red-500 hover:bg-slate-700/50 transition-colors">
                            <p className="font-bold text-red-400 text-sm">{alert.alert_type || alert.fault_category}</p>
                            <p className="text-xs text-slate-300 mt-1">{alert.details || `SoC: ${alert.soc_percent?.toFixed(1)}%  |  ${alert.batt_voltage?.toFixed(2)}V`}</p>
                            <p className="text-[10px] text-slate-500 mt-2 text-right">{new Date(alert.timestamp).toLocaleTimeString()}</p>
                        </div>
                    ))}
                    {alerts.length === 0 && <p className="text-slate-500 italic text-sm text-center mt-10">No active alerts.</p>}
                </div>
            </div>

            {/* ── ML CONTROL PANEL ── */}
            <div className="lg:col-span-4 glass-panel p-6">
                <div className="flex items-center justify-between mb-4">
                    <h2 className="text-indigo-300 uppercase tracking-widest text-xs font-bold flex items-center gap-2">
                        <BrainCircuit size={15} /> ML Retraining Control
                    </h2>
                    <span className="text-[10px] text-slate-500">Auto-scheduled every 7 days &bull; APScheduler</span>
                </div>

                <div className="flex flex-col md:flex-row items-start md:items-center gap-6">
                    {/* Trigger Button */}
                    <div className="flex flex-col gap-2 min-w-[220px]">
                        <button
                            id="btn-trigger-retraining"
                            onClick={triggerRetraining}
                            disabled={retrainStatus === 'loading'}
                            className={`flex items-center gap-2 px-5 py-3 rounded-lg text-sm font-semibold transition-all duration-300 ${btnStyles[retrainStatus]}`}
                        >
                            {BtnIcon[retrainStatus]}
                            {retrainStatus === 'idle'    && 'Trigger Model Retraining'}
                            {retrainStatus === 'loading' && 'Dispatching...'}
                            {retrainStatus === 'success' && 'Job Accepted!'}
                            {retrainStatus === 'error'   && 'Failed — Retry?'}
                        </button>
                        {retrainMsg && (
                            <p className={`text-xs ${retrainStatus === 'error' ? 'text-red-400' : 'text-slate-400'}`}>
                                {retrainMsg}
                            </p>
                        )}
                    </div>

                    {/* Calibration Log */}
                    <div className="flex-1 overflow-x-auto">
                        {calibrationLog.length > 0 ? (
                            <table className="w-full text-xs text-left text-slate-300">
                                <thead>
                                    <tr className="text-slate-500 uppercase border-b border-slate-700">
                                        <th className="pb-2 pr-4">Timestamp</th>
                                        <th className="pb-2 pr-4">RMSE</th>
                                        <th className="pb-2 pr-4">MAE</th>
                                        <th className="pb-2">Days Since Last</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {calibrationLog.map((log) => (
                                        <tr key={log.calibration_id} className="border-b border-slate-800 hover:bg-slate-800/30">
                                            <td className="py-2 pr-4">{new Date(log.retrain_timestamp).toLocaleString()}</td>
                                            <td className="py-2 pr-4 text-indigo-300">{log.rmse_score?.toFixed(4)}</td>
                                            <td className="py-2 pr-4 text-indigo-300">{log.mae_score?.toFixed(4)}</td>
                                            <td className="py-2 text-slate-400">{log.days_elapsed ?? '—'}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        ) : (
                            <p className="text-slate-500 italic text-sm">No retraining cycles logged yet. Click the button to run the first cycle.</p>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Dashboard;
