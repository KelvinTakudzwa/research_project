import React from 'react';
import { useSolarData } from '../../hooks/useSolarData';
import { AlertTriangle, ShieldCheck, AlertOctagon } from 'lucide-react';

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
                        {alerts.map((alert, index) => {
                            const isCritical = alert.alert_severity === 'Critical';
                            const Icon = isCritical ? AlertOctagon : AlertTriangle;

                            // Colour scheme driven by severity
                            const borderColor  = isCritical ? 'border-red-500/20'    : 'border-amber-500/20';
                            const bgColor      = isCritical ? 'bg-red-900/10'        : 'bg-amber-900/10';
                            const bgHover      = isCritical ? 'hover:bg-red-900/20'  : 'hover:bg-amber-900/20';
                            const textColor    = isCritical ? 'text-red-400'         : 'text-amber-400';
                            const subTextColor = isCritical ? 'text-red-300'         : 'text-amber-300';
                            const divider      = isCritical ? 'border-red-500/10'    : 'border-amber-500/10';
                            const innerGlow    = isCritical
                                ? 'shadow-[inset_0_0_20px_rgba(239,68,68,0.05)]'
                                : 'shadow-[inset_0_0_20px_rgba(251,191,36,0.05)]';

                            // Deterministic alarms (thermal runaway, deep discharge) have no ML score
                            const confidenceDisplay = alert.anomaly_score != null
                                ? Math.abs(alert.anomaly_score).toFixed(4)
                                : 'Rule-based';

                            return (
                                <div
                                    key={index}
                                    className={`p-3.5 rounded-xl ${bgColor} border ${borderColor} flex flex-col gap-2 ${bgHover} transition-colors animate-slide-in ${innerGlow}`}
                                    style={{ animationDelay: `${index * 50}ms` }}
                                >
                                    {/* Header row */}
                                    <div className="flex justify-between items-start gap-2">
                                        <div className="flex items-center gap-1.5 min-w-0">
                                            <Icon size={13} className={`${textColor} shrink-0`} />
                                            <span className={`text-sm font-bold ${textColor} tracking-wide truncate`}>
                                                {alert.alert_type || alert.pred_label || 'Fault Event'}
                                            </span>
                                        </div>
                                        <span className="text-[10px] text-slate-400 tabular-nums shrink-0">
                                            {new Date(alert.timestamp).toLocaleTimeString([], {
                                                hour: '2-digit', minute: '2-digit', second: '2-digit'
                                            })}
                                        </span>
                                    </div>

                                    {/* Severity badge */}
                                    <span className={`self-start text-[9px] uppercase tracking-widest font-bold px-2 py-0.5 rounded-full border ${
                                        isCritical
                                            ? 'bg-red-500/10 border-red-500/30 text-red-300'
                                            : 'bg-amber-500/10 border-amber-500/30 text-amber-300'
                                    }`}>
                                        {alert.alert_severity || 'Warning'}
                                    </span>

                                    {/* Stats footer */}
                                    <div className={`flex justify-between items-end border-t ${divider} pt-2 mt-1`}>
                                        <div className="flex flex-col gap-0.5">
                                            <span className="text-[10px] text-slate-500 uppercase tracking-widest">Confidence</span>
                                            <span className={`text-xs ${subTextColor} font-medium`}>{confidenceDisplay}</span>
                                        </div>
                                        <div className="flex flex-col gap-0.5 text-right">
                                            <span className="text-[10px] text-slate-500 uppercase tracking-widest">Batt / SoC</span>
                                            <span className={`text-xs ${subTextColor} font-medium`}>
                                                {alert.battery_voltage_v != null ? `${alert.battery_voltage_v.toFixed(2)}V` : '--'}
                                                {alert.soc_percent != null ? ` / ${alert.soc_percent.toFixed(0)}%` : ''}
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
};

export default AlertFeed;
