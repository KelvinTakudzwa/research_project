import React from 'react';
import { useSolarData } from '../../hooks/useSolarData';
import { Wifi, Signal, ServerCrash, Clock } from 'lucide-react';

const Topbar = () => {
    const { latest } = useSolarData();
    const isOnline = latest !== null;

    return (
        <header className="h-20 px-8 flex items-center justify-between border-b border-white/5 glass-panel rounded-none">
            
            {/* Left aligned branding / contextual info */}
            <div className="flex flex-col">
                <h1 className="text-xl font-bold font-outfit text-white tracking-wide">Command Center</h1>
                <p className="text-xs text-slate-400 tracking-widest uppercase">ML-Driven IoT Infrastructure</p>
            </div>

            {/* Right side global status */}
            <div className="flex items-center gap-6">
                
                {/* Node Sync Status */}
                <div className="flex items-center gap-3 glass-card px-4 py-2 opacity-80 backdrop-blur-lg">
                    {isOnline ? (
                        <>
                            <Wifi size={16} className="text-emerald-400 animate-pulse-soft text-glow" />
                            <div className="flex flex-col">
                                <span className="text-[10px] text-slate-400 uppercase tracking-widest font-semibold leading-tight">Link</span>
                                <span className="text-xs text-emerald-300 font-bold leading-tight">ONLINE</span>
                            </div>
                        </>
                    ) : (
                        <>
                            <ServerCrash size={16} className="text-red-500 animate-pulse" />
                            <div className="flex flex-col">
                                <span className="text-[10px] text-slate-400 uppercase tracking-widest font-semibold leading-tight">Link</span>
                                <span className="text-xs text-red-400 font-bold leading-tight">OFFLINE</span>
                            </div>
                        </>
                    )}
                </div>

                {/* Last Update */}
                <div className="flex items-center gap-3">
                    <Clock size={16} className="text-indigo-400" />
                    <div className="text-xs tabular-nums text-slate-300">
                        {latest ? new Date(latest.timestamp).toLocaleTimeString() : '--:--:--'}
                    </div>
                </div>

                {/* Minimal User Profile placeholder */}
                <div className="h-10 w-10 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-500 border-2 border-white/20 shadow-lg cursor-pointer"></div>
            </div>
            
        </header>
    );
};

export default Topbar;
