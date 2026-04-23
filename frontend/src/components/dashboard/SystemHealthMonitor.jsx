import React from 'react';
import { useSolarData } from '../../hooks/useSolarData';
import { ShieldCheck, ShieldAlert, Cpu } from 'lucide-react';

const SystemHealthMonitor = () => {
    const { latest } = useSolarData();

    if (!latest) {
        return (
            <div className="glass-panel h-full flex items-center justify-center">
                <span className="text-slate-400">Loading System State...</span>
            </div>
        );
    }

    const { pred_label, soh_percent, anomaly_score } = latest;

    // Derived State
    const isNormal = pred_label === 'Normal';
    const isWarning = pred_label === 'Unknown_Anomaly';
    const isCritical = pred_label === 'Known_Fault_Degradation' || pred_label === 'Known_Fault' || pred_label === 'Error' || pred_label?.includes('F');

    const statusText = isNormal ? 'HEALTHY STATE' : isCritical ? 'CRITICAL FAULT' : 'WARNING STATE';
    const statusColor = isNormal ? 'text-emerald-400' : isCritical ? 'text-rose-500' : 'text-amber-400';
    const bgGlow = isNormal ? 'shadow-[0_0_30px_rgba(52,211,153,0.05)]' : isCritical ? 'shadow-[0_0_30px_rgba(244,63,94,0.1)]' : 'shadow-[0_0_30px_rgba(251,191,36,0.05)]';

    const Icon = isNormal ? ShieldCheck : ShieldAlert;

    // SVG Donut calculation
    const radius = 36;
    const circumference = 2 * Math.PI * radius;
    const strokeDashoffset = circumference - ((soh_percent || 0) / 100) * circumference;

    return (
        <div className={`glass-panel h-full flex flex-col p-5 relative overflow-hidden ${bgGlow} transition-all duration-500`}>
            {/* Background accent */}
            <div className={`absolute -top-10 -right-10 w-32 h-32 rounded-full blur-3xl opacity-20 ${
                isNormal ? 'bg-emerald-500' : isCritical ? 'bg-rose-500' : 'bg-amber-500'
            }`}></div>

            <h3 className="text-slate-300 font-semibold tracking-wide text-sm flex items-center gap-2 mb-4 z-10">
                <Cpu className="w-4 h-4 text-slate-400" />
                SYSTEM HEALTH MONITOR
            </h3>

            <div className="flex items-center gap-6 mt-1 z-10">
                
                {/* PowerBI Style Donut Metric */}
                <div className="relative flex items-center justify-center shrink-0">
                    <svg className="w-24 h-24 transform -rotate-90">
                        <circle cx="48" cy="48" r={radius} stroke="currentColor" strokeWidth="6" fill="transparent" className="text-slate-700/50" />
                        <circle 
                            cx="48" cy="48" r={radius} 
                            stroke="currentColor" strokeWidth="6" fill="transparent" 
                            strokeDasharray={circumference} 
                            strokeDashoffset={strokeDashoffset}
                            className={`${statusColor} transition-all duration-1000 ease-out`} 
                            strokeLinecap="round" 
                        />
                    </svg>
                    <div className="absolute flex flex-col items-center justify-center">
                        <span className="text-xl font-bold text-white tracking-tight">{soh_percent ? soh_percent.toFixed(1) : '--'}%</span>
                        <span className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider">SoH</span>
                    </div>
                </div>

                {/* Status KPI */}
                <div className="flex flex-col w-full">
                    <span className="text-[11px] text-slate-400 uppercase tracking-widest font-semibold mb-1">Current State</span>
                    <div className="flex items-center gap-2">
                        <Icon className={`w-5 h-5 ${statusColor}`} />
                        <span className={`text-xl font-bold tracking-tight ${statusColor} truncate`}>
                            {statusText}
                        </span>
                    </div>
                    
                    <div className="mt-4 grid grid-cols-2 gap-x-2 gap-y-2">
                        <div className="flex flex-col bg-slate-800/40 rounded p-2 border border-slate-700/30">
                            <span className="text-[9px] text-slate-500 uppercase tracking-wider font-semibold">Anomaly Score</span>
                            <span className="text-sm font-medium text-slate-200 truncate">
                                {anomaly_score !== undefined && anomaly_score !== null ? anomaly_score.toFixed(3) : 'N/A'}
                            </span>
                        </div>
                        <div className="flex flex-col bg-slate-800/40 rounded p-2 border border-slate-700/30">
                            <span className="text-[9px] text-slate-500 uppercase tracking-wider font-semibold">ML Label</span>
                            <span className="text-[11px] font-medium text-slate-300 truncate" title={pred_label}>
                                {pred_label?.replace(/_/g, ' ') || 'N/A'}
                            </span>
                        </div>
                    </div>
                </div>
            </div>
            
            {/* PowerBI style footer bar */}
            <div className="mt-auto pt-4 border-t border-slate-700/50 flex justify-between items-center z-10">
                <span className="text-[10px] uppercase font-semibold tracking-wider text-slate-500 flex items-center gap-2">
                    <span className="relative flex h-2 w-2">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                    </span>
                    Live Diagnostics Active
                </span>
                <div className="flex gap-1.5">
                    <div className={`h-1.5 w-6 rounded-full ${isNormal ? 'bg-emerald-500' : 'bg-slate-700'}`}></div>
                    <div className={`h-1.5 w-6 rounded-full ${isWarning ? 'bg-amber-500' : 'bg-slate-700'}`}></div>
                    <div className={`h-1.5 w-6 rounded-full ${isCritical ? 'bg-rose-500' : 'bg-slate-700'}`}></div>
                </div>
            </div>
        </div>
    );
};

export default SystemHealthMonitor;
