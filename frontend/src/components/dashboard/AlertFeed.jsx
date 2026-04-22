import React from 'react';
import { useSolarData } from '../../hooks/useSolarData';
import { AlertTriangle, ShieldCheck } from 'lucide-react';

const AlertFeed = () => {
    const { alerts } = useSolarData();

    return (
        <div className="glass-panel flex flex-col h-full overflow-hidden">
            <div className="p-5 border-b border-white/5 flex items-center justify-between bg-white/[0.02]">
                <h3 className="font-outfit font-semibold text-white tracking-wide flex items-center gap-2">
                    <AlertTriangle size={18} className="text-amber-400" />
                    Diagnostics Log
                </h3>
                <span className="px-2.5 py-0.5 rounded-full bg-slate-800 border border-slate-700 text-xs font-medium text-slate-300">
                    {alerts?.length || 0} Events
                </span>
            </div>

            <div className="flex-1 overflow-y-auto custom-scrollbar p-3">
                {!alerts || alerts.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center opacity-50 gap-3">
                        <ShieldCheck size={32} className="text-emerald-400" />
                        <span className="text-xs uppercase tracking-widest text-emerald-300 font-semibold">System Stable</span>
                    </div>
                ) : (
                    <div className="flex flex-col gap-3">
                        {alerts.map((alert, index) => (
                            <div 
                                key={index} 
                                className="p-3.5 rounded-xl bg-red-900/10 border border-red-500/20 flex flex-col gap-2 hover:bg-red-900/20 transition-colors animate-slide-in shadow-[inset_0_0_20px_rgba(239,68,68,0.05)]"
                                style={{ animationDelay: `${index * 50}ms` }}
                            >
                                <div className="flex justify-between items-start">
                                    <span className="text-sm font-bold text-red-400 tracking-wide glow-text-soft">
                                        {alert.alert_type || alert.pred_label || "Fault Event"}
                                    </span>
                                    <span className="text-[10px] text-slate-400 tabular-nums">
                                        {new Date(alert.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                                    </span>
                                </div>
                                <div className="flex justify-between items-end border-t border-red-500/10 pt-2 mt-1">
                                    <div className="flex flex-col gap-0.5">
                                        <span className="text-[10px] text-slate-500 uppercase tracking-widest">Confidence</span>
                                        <span className="text-xs text-red-300 font-medium">{Math.abs(alert.anomaly_score).toFixed(4)}</span>
                                    </div>
                                    <div className="flex flex-col gap-0.5 text-right">
                                        <span className="text-[10px] text-slate-500 uppercase tracking-widest">Battery</span>
                                        <span className="text-xs text-red-300 font-medium">{alert.batt_voltage}V</span>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

export default AlertFeed;
