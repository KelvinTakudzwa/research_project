import React from 'react';
import { Link } from 'react-router-dom';
import { useSolarData } from '../../hooks/useSolarData';
import { ShieldAlert, AlertOctagon, AlertTriangle, ShieldCheck, ArrowRight } from 'lucide-react';

const SEVERITY_STYLES = {
    Critical: 'bg-red-500/10 border-red-500/30 text-red-400',
    Warning:  'bg-amber-500/10 border-amber-500/30 text-amber-400',
};

const FaultSummaryPanel = () => {
    const { alerts } = useSolarData();

    // Overview shows ML-driven faults only.
    // Deterministic alarms (F7, F9, F10, Thermal Runaway, Deep Discharge Protection)
    // carry no pred_label in WebSocket payloads, but REST-loaded records DO have a
    // pred_label via the inference JOIN. Use an explicit whitelist instead.
    const ML_FAULT_TYPES = new Set([
        'F1 Partial Shading', 'F2 Inverter Overload', 'F3 Deep Discharge',
        'F5 Sensor Dead', 'Uncertain Anomaly',
    ]);
    const mlAlerts = alerts.filter(a => ML_FAULT_TYPES.has(a.alert_type));

    const criticalCount = mlAlerts.filter(a => a.alert_severity === 'Critical').length;
    const warningCount  = mlAlerts.filter(a => a.alert_severity === 'Warning').length;
    const mostRecent    = mlAlerts.find(a => a.alert_severity === 'Critical') || mlAlerts[0];
    const recentThree   = mlAlerts.slice(0, 3);

    const isAllClear = mlAlerts.length === 0;

    return (
        <div className="glass-panel flex flex-col h-full overflow-hidden">
            <div className="p-5 border-b border-white/5 flex items-center justify-between bg-white/[0.02]">
                <h3 className="font-outfit font-semibold text-white tracking-wide flex items-center gap-2">
                    <ShieldAlert size={18} className="text-amber-400" />
                    Fault Summary
                </h3>
                <Link
                    to="/faults"
                    className="flex items-center gap-1 text-[11px] text-indigo-400 hover:text-indigo-300 transition-colors font-semibold uppercase tracking-wider"
                >
                    View all <ArrowRight size={12} />
                </Link>
            </div>

            <div className="flex-1 flex flex-col p-4 gap-4 overflow-hidden">
                {isAllClear ? (
                    <div className="flex-1 flex flex-col items-center justify-center opacity-50 gap-3">
                        <ShieldCheck size={32} className="text-emerald-400" />
                        <span className="text-xs uppercase tracking-widest text-emerald-300 font-semibold">System Stable</span>
                    </div>
                ) : (
                    <>
                        {/* Count badges */}
                        <div className="grid grid-cols-2 gap-3">
                            <div className="flex flex-col items-center justify-center bg-red-900/10 border border-red-500/20 rounded-xl p-3 gap-1">
                                <AlertOctagon size={16} className="text-red-400" />
                                <span className="text-2xl font-bold text-red-400">{criticalCount}</span>
                                <span className="text-[9px] uppercase tracking-widest text-red-300/70 font-semibold">Critical</span>
                            </div>
                            <div className="flex flex-col items-center justify-center bg-amber-900/10 border border-amber-500/20 rounded-xl p-3 gap-1">
                                <AlertTriangle size={16} className="text-amber-400" />
                                <span className="text-2xl font-bold text-amber-400">{warningCount}</span>
                                <span className="text-[9px] uppercase tracking-widest text-amber-300/70 font-semibold">Warning</span>
                            </div>
                        </div>

                        {/* Most recent critical */}
                        {mostRecent && (
                            <div className={`rounded-xl border p-3 ${
                                mostRecent.alert_severity === 'Critical'
                                    ? 'bg-red-900/10 border-red-500/20'
                                    : 'bg-amber-900/10 border-amber-500/20'
                            }`}>
                                <div className="text-[9px] uppercase tracking-widest text-slate-500 font-semibold mb-1">Latest Fault</div>
                                <div className={`text-sm font-bold truncate ${
                                    mostRecent.alert_severity === 'Critical' ? 'text-red-400' : 'text-amber-400'
                                }`}>
                                    {mostRecent.alert_type || mostRecent.pred_label || 'Fault Event'}
                                </div>
                                <div className="text-[10px] text-slate-500 mt-1">
                                    {mostRecent.timestamp
                                        ? new Date(mostRecent.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
                                        : '--'
                                    }
                                    {mostRecent.battery_voltage_v != null && ` · ${mostRecent.battery_voltage_v.toFixed(2)}V`}
                                    {mostRecent.soc_percent != null && ` · SoC ${mostRecent.soc_percent.toFixed(0)}%`}
                                </div>
                            </div>
                        )}

                        {/* 3 recent fault pills */}
                        <div className="flex flex-col gap-1.5">
                            {recentThree.map((alert, i) => (
                                <div
                                    key={i}
                                    className={`flex items-center justify-between px-3 py-1.5 rounded-lg border text-[11px] font-medium ${SEVERITY_STYLES[alert.alert_severity] || SEVERITY_STYLES.Warning}`}
                                >
                                    <span className="truncate">{alert.alert_type || alert.pred_label}</span>
                                    <span className="text-slate-500 shrink-0 ml-2">
                                        {alert.timestamp
                                            ? new Date(alert.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                                            : '--'
                                        }
                                    </span>
                                </div>
                            ))}
                        </div>
                    </>
                )}
            </div>
        </div>
    );
};

export default FaultSummaryPanel;
