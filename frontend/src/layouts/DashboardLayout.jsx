import React, { useState } from 'react';
import Sidebar from '../components/common/Sidebar';
import Topbar from '../components/common/Topbar';
import { Maximize, Minimize } from 'lucide-react';

const DashboardLayout = ({ children }) => {
    const [isZenMode, setIsZenMode] = useState(false);

    return (
        <div className="flex h-screen overflow-hidden bg-slate-950 font-sans text-slate-200 relative">
            {/* Ambient Background Glows */}
            <div className="absolute top-0 left-1/4 w-96 h-96 bg-indigo-600/20 rounded-full blur-[128px] -z-10 pointer-events-none"></div>
            <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-emerald-600/10 rounded-full blur-[128px] -z-10 pointer-events-none"></div>

            {/* Zen Mode Toggle Button */}
            <button 
                onClick={() => setIsZenMode(!isZenMode)}
                className="absolute bottom-6 right-6 z-50 p-3 rounded-full bg-indigo-600/20 border border-indigo-500/30 text-indigo-400 hover:bg-indigo-600/40 hover:text-white transition-all backdrop-blur-md shadow-lg hover:scale-110 active:scale-95"
                title={isZenMode ? "Exit Zen Mode" : "Enter Zen Mode"}
            >
                {isZenMode ? <Minimize size={20} /> : <Maximize size={20} />}
            </button>

            {!isZenMode && <Sidebar />}
            
            <div className="flex-1 flex flex-col min-w-0 z-10 transition-all duration-500">
                {!isZenMode && <Topbar />}
                <main className={`flex-1 overflow-y-auto overflow-x-hidden custom-scrollbar scroll-smooth ${isZenMode ? 'p-8 pb-20' : 'p-6'}`}>
                    {children}
                </main>
            </div>
        </div>
    );
};

export default DashboardLayout;
