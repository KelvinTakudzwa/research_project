import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, ShieldAlert, Zap, Settings } from 'lucide-react';

const Sidebar = () => {
    return (
        <aside className="w-20 lg:w-64 flex flex-col border-r border-white/10 bg-slate-900/40 backdrop-blur-3xl transition-all duration-300 z-20 shadow-2xl">
            <div className="h-20 flex items-center justify-center lg:justify-start lg:px-6 border-b border-white/5">
                <div className="flex items-center gap-3 text-indigo-400">
                    <Zap size={28} className="drop-shadow-[0_0_8px_rgba(99,102,241,0.8)] animate-pulse-soft" />
                    <span className="hidden lg:block font-bold text-lg tracking-wide text-white uppercase font-outfit">Nexus Grid</span>
                </div>
            </div>

            <nav className="flex-1 py-8 flex flex-col gap-2 px-3">
                <NavItem to="/"       icon={<LayoutDashboard size={20} />} label="Overview"   end />
                <NavItem to="/faults" icon={<ShieldAlert size={20} />}     label="Fault Logs" />
            </nav>

            <div className="h-20 flex items-center justify-center lg:justify-start lg:px-6 border-t border-white/5 mb-4">
                <div className="flex items-center gap-3 opacity-60 hover:opacity-100 transition-opacity cursor-pointer">
                    <Settings size={20} />
                    <span className="hidden lg:block text-sm font-medium">Settings</span>
                </div>
            </div>
        </aside>
    );
};

const NavItem = ({ to, icon, label, end }) => {
    return (
        <NavLink
            to={to}
            end={end}
            className={({ isActive }) =>
                `p-3 lg:px-4 rounded-xl flex items-center justify-center lg:justify-start gap-3 transition-all duration-200 group
                ${isActive
                    ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/30 shadow-[inset_0_0_20px_rgba(99,102,241,0.1)]'
                    : 'text-slate-400 hover:bg-white/5 hover:text-slate-200 border border-transparent'
                }`
            }
        >
            {({ isActive }) => (
                <>
                    <div className={isActive ? 'drop-shadow-[0_0_8px_currentColor]' : 'group-hover:drop-shadow-[0_0_5px_currentColor]'}>
                        {icon}
                    </div>
                    <span className="hidden lg:block font-medium tracking-wide text-sm">{label}</span>
                </>
            )}
        </NavLink>
    );
};

export default Sidebar;
