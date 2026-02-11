import React from 'react';

const StatusCard = ({ title, value, subValue, icon, color }) => {
    return (
        <div className="glass-panel p-6 flex items-center justify-between hover:bg-slate-800/80 transition-all duration-300 transform hover:-translate-y-1">
            <div>
                <p className="text-slate-400 text-xs font-bold uppercase tracking-widest">{title}</p>
                <div className="flex items-baseline mt-2">
                    <h3 className={`text-3xl font-extrabold ${color} drop-shadow-lg`}>{value}</h3>
                    {subValue && <span className="ml-2 text-sm text-slate-500">/ {subValue}</span>}
                </div>
            </div>
            <div className={`p-4 rounded-xl bg-slate-800/50 backdrop-blur-sm shadow-inner ${color}`}>
                {icon}
            </div>
        </div >
    );
};

export default StatusCard;
