import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { AlertTriangle, Battery, Sun, Activity } from 'lucide-react';
import RealTimeChart from './RealTimeChart';
import StatusCard from './StatusCard';

const Dashboard = () => {
    const [latest, setLatest] = useState(null);
    const [history, setHistory] = useState([]);
    const [alerts, setAlerts] = useState([]);

    const fetchData = async () => {
        try {
            // Get historical data for charts
            const historyRes = await axios.get('http://localhost:5000/api/readings');
            setHistory(historyRes.data);

            if (historyRes.data.length > 0) {
                setLatest(historyRes.data[historyRes.data.length - 1]);
            }

            // Get Alerts
            const alertsRes = await axios.get('http://localhost:5000/api/alerts');
            setAlerts(alertsRes.data);
        } catch (err) {
            console.error("API Error:", err);
        }
    };

    useEffect(() => {
        fetchData(); // Initial Load
        const interval = setInterval(fetchData, 2000); // Poll every 2 seconds
        return () => clearInterval(interval);
    }, []);

    if (!latest) return <div className="text-center mt-20">Loading System Data...</div>;

    // Determine System Health
    const healthStatus = latest.pred_label === 'Normal' ? 'Healthy' : 'Critical';
    const healthColor = latest.pred_label === 'Normal' ? 'bg-emerald-500' : 'bg-red-500';

    return (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            {/* KPI Cards */}
            <StatusCard
                title="Battery SoC"
                value={`${latest.soc_percent?.toFixed(1)}%`}
                icon={<Battery size={24} />}
                color="text-green-400"
            />
            <StatusCard
                title="PV Power"
                value={`${latest.pv_power_watts?.toFixed(1)} W`}
                icon={<Sun size={24} />}
                color="text-yellow-400"
            />
            <StatusCard
                title="System Health"
                value={healthStatus}
                subValue={latest.pred_label}
                icon={<Activity size={24} />}
                color={latest.pred_label === 'Normal' ? "text-emerald-400" : "text-red-400"}
            />
            <StatusCard
                title="Active Alerts"
                value={alerts.length}
                icon={<AlertTriangle size={24} />}
                color="text-orange-400"
            />

            {/* Main Chart Section */}
            <div className="md:col-span-3 glass-panel p-6">
                <h2 className="text-lg font-bold mb-4 text-indigo-300 uppercase tracking-widest text-xs">Real-Time Performance</h2>
                <div className="h-[26rem] w-full">
                    <RealTimeChart data={history} />
                </div>
            </div>

            {/* Alerts Feed */}
            <div className="glass-panel p-6 h-[500px] overflow-hidden flex flex-col">
                <h2 className="text-lg font-bold mb-4 text-orange-300 uppercase tracking-widest text-xs">Recent Alerts</h2>
                <div className="space-y-3 overflow-y-auto pr-2 custom-scrollbar flex-1">
                    {alerts.map((alert) => (
                        <div key={alert.id} className="p-3 bg-slate-800/50 rounded-lg border-l-4 border-red-500 hover:bg-slate-700/50 transition-colors">
                            <p className="font-bold text-red-400 text-sm">{alert.alert_type}</p>
                            <p className="text-xs text-slate-300 mt-1">{alert.details}</p>
                            <p className="text-[10px] text-slate-500 mt-2 text-right">{new Date(alert.timestamp).toLocaleTimeString()}</p>
                        </div>
                    ))}
                    {alerts.length === 0 && <p className="text-slate-500 italic text-sm text-center mt-10">No active alerts.</p>}
                </div>
            </div>
        </div>
    );
};

export default Dashboard;
