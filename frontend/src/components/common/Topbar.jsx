import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useSolarData } from '../../hooks/useSolarData';
import { Wifi, ServerCrash, Clock, LogOut } from 'lucide-react';

const Topbar = () => {
    const { latest } = useSolarData();
    const navigate   = useNavigate();
    const isOnline   = latest !== null;

    const logout = () => {
        localStorage.removeItem('solar_token');
        // Full page reload tears down the polling interval cleanly
        window.location.href = '/login';
    };

    return (
        <header className="h-20 px-8 flex items-center justify-between border-b border-white/5 glass-panel rounded-none">

            {/* Left — branding */}
            <div className="flex flex-col">
                <h1 className="text-xl font-bold font-outfit text-white tracking-wide">Command Center</h1>
                <p className="text-xs text-slate-400 tracking-widest uppercase">ML-Driven IoT Infrastructure</p>
            </div>

            {/* Right — status + logout */}
            <div className="flex items-center gap-6">

                {/* Node sync status */}
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

                {/* Last update timestamp */}
                <div className="flex items-center gap-3">
                    <Clock size={16} className="text-indigo-400" />
                    <div className="text-xs tabular-nums text-slate-300">
                        {latest ? new Date(latest.timestamp).toLocaleTimeString() : '--:--:--'}
                    </div>
                </div>

                {/* Logout */}
                <button
                    onClick={logout}
                    title="Sign out"
                    className="flex items-center gap-2 px-3 py-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-colors border border-transparent hover:border-white/10"
                >
                    <LogOut size={16} />
                    <span className="text-xs font-semibold uppercase tracking-widest hidden sm:inline">Sign Out</span>
                </button>
            </div>
        </header>
    );
};

export default Topbar;
