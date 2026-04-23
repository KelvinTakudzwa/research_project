import React from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import KpiGrid from '../components/dashboard/KpiGrid';
import MainChart from '../components/dashboard/MainChart';
import AlertFeed from '../components/dashboard/AlertFeed';
import MlControl from '../components/dashboard/MlControl';
import SystemHealthMonitor from '../components/dashboard/SystemHealthMonitor';

const DashboardPage = () => {
    return (
        <DashboardLayout>
            <div className="flex flex-col gap-6 w-full max-w-7xl mx-auto pb-10">
                
                {/* Header Welcome */}
                <div className="mb-2">
                    <h2 className="text-3xl font-outfit font-bold text-white tracking-tight glow-text-soft">System Overview</h2>
                    <p className="text-slate-400 text-sm tracking-wide mt-1">Real-time solar telemetry and AI anomaly detection</p>
                </div>

                {/* KPI Tier */}
                <KpiGrid />

                {/* Main Middle Tier */}
                <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
                    {/* Chart takes up 3 columns */}
                    <div className="lg:col-span-3">
                        <MainChart />
                    </div>
                    {/* Alert feed takes 1 column */}
                    <div className="lg:col-span-1 h-[420px]">
                        <AlertFeed />
                    </div>
                </div>

                {/* Bottom Tier */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    <div className="lg:col-span-1 h-[250px]">
                        <MlControl />
                    </div>
                    
                    <div className="lg:col-span-2">
                        <SystemHealthMonitor />
                    </div>
                </div>
            </div>
        </DashboardLayout>
    );
};

export default DashboardPage;
