import React from 'react';

// Neon color mapping for sparkline
const colorMap = {
    'indigo-400': '#818cf8',
    'emerald-400': '#34d399',
    'rose-400': '#fb7185',
    'amber-400': '#fbbf24',
    'cyan-400': '#22d3ee',
};

const StatusCard = ({ title, value, unit, icon: Icon, colorClass, dataKey }) => {
    // Determine gradient map
    const accentColor = colorMap[colorClass] || colorMap['indigo-400'];
    
    return (
        <div className="glass-card p-5 group flex flex-col justify-between hover:scale-[1.02] transition-transform duration-300">
            {/* Top Row: Icon + Title */}
            <div className="flex justify-between items-start mb-4">
                <div className={`p-2.5 rounded-lg bg-white/5 border border-white/10 ${`text-${colorClass}`} group-hover:bg-white/10 transition-colors`}>
                    <Icon size={22} className="drop-shadow-[0_0_8px_currentColor]" />
                </div>
                <div className="text-[10px] uppercase tracking-[0.2em] font-semibold text-slate-400 pt-1">
                    {title}
                </div>
            </div>

            {/* Bottom Row: Value */}
            <div className="flex items-baseline gap-1.5 mt-auto">
                <span className="text-3xl font-bold text-white font-outfit tracking-tight">
                    {value !== undefined && value !== null ? value : '--'}
                </span>
                <span className={`text-sm font-semibold tracking-wide text-${colorClass} opacity-80`}>
                    {unit}
                </span>
            </div>

            {/* Micro decorative sparkline at the bottom */}
            <div className="absolute bottom-0 left-0 w-full h-[3px] bg-white/5">
                <div 
                    className={`h-full bg-${colorClass} shadow-[0_0_10px_currentColor]`} 
                    style={{ width: `${Math.random() * 40 + 60}%`, opacity: 0.8 }}
                ></div>
            </div>
        </div>
    );
};

export default StatusCard;
