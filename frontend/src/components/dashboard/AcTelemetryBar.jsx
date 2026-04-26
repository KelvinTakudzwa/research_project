import React from 'react';
import { useSolarData } from '../../hooks/useSolarData';
import { Zap, WifiOff } from 'lucide-react';

const Stat = ({ label, value, unit, highlight }) => (
    <div className="flex flex-col items-center gap-0.5 px-5 py-2.5 rounded-lg"
         style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
        <span className="text-[9px] uppercase tracking-[0.18em] font-semibold text-slate-500">{label}</span>
        <div className="flex items-baseline gap-1">
            <span className={`text-lg font-bold tabular-nums ${highlight ? 'text-amber-300' : 'text-white'}`}>
                {value ?? '--'}
            </span>
            <span className="text-[10px] font-medium text-slate-400">{unit}</span>
        </div>
    </div>
);

const Divider = () => (
    <div className="w-px h-8 bg-white/5 self-center" />
);

const AcTelemetryBar = () => {
    const { latest } = useSolarData();

    const fmt = (val, decimals = 1) =>
        val != null ? Number(val).toFixed(decimals) : null;

    const isBuffered = latest?.is_offline_buffered === 1 || latest?.is_offline_buffered === true;

    return (
        <div className="glass-panel px-6 py-3 flex items-center justify-between gap-4 flex-wrap">
            {/* Section label */}
            <div className="flex items-center gap-2 shrink-0">
                <div className="p-1.5 rounded-lg bg-amber-500/10 border border-amber-500/20">
                    <Zap size={13} className="text-amber-400" />
                </div>
                <div>
                    <p className="text-[10px] uppercase tracking-widest font-semibold text-slate-400 leading-tight">AC Subsystem</p>
                    <p className="text-[9px] text-slate-600 leading-tight">PZEM-004T</p>
                </div>
            </div>

            <Divider />

            {/* Four PZEM readings */}
            <div className="flex items-center gap-3 flex-wrap">
                <Stat label="Voltage"      value={fmt(latest?.ac_voltage_v, 1)}   unit="V"  />
                <Stat label="Current"      value={fmt(latest?.ac_current_a, 2)}   unit="A"  />
                <Stat label="Active Power" value={fmt(latest?.ac_power_w, 1)}     unit="W"  highlight />
                <Stat label="Power Factor" value={fmt(latest?.ac_power_factor, 3)} unit="pf" />
            </div>

            {/* Store-and-forward badge — only shown when packet came from LittleFS buffer */}
            {isBuffered && (
                <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full ml-auto"
                     style={{ background: 'rgba(251,191,36,0.08)', border: '1px solid rgba(251,191,36,0.25)' }}>
                    <WifiOff size={11} className="text-amber-400" />
                    <span className="text-[9px] uppercase tracking-widest font-bold text-amber-400">Buffered</span>
                </div>
            )}
        </div>
    );
};

export default AcTelemetryBar;
