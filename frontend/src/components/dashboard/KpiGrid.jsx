import React from 'react';
import { useSolarData } from '../../hooks/useSolarData';
import StatusCard from './StatusCard';
import { Zap, Battery, Sun, Activity, ThermometerSun } from 'lucide-react';

const KpiGrid = () => {
    const { latest } = useSolarData();

    return (
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-6">
            <StatusCard 
                title="PV Power" 
                value={latest?.pv_power_watts} 
                unit="W" 
                icon={Zap} 
                colorClass="indigo-400" 
            />
            <StatusCard 
                title="PV Voltage" 
                value={latest?.pv_voltage} 
                unit="V" 
                icon={Activity} 
                colorClass="cyan-400" 
            />
            <StatusCard 
                title="Batt SoC" 
                value={latest?.soc_percent} 
                unit="%" 
                icon={Battery} 
                colorClass="emerald-400" 
            />
            <StatusCard 
                title="Irradiance" 
                value={latest?.irradiance_lux} 
                unit="Lux" 
                icon={Sun} 
                colorClass="amber-400" 
            />
            <StatusCard 
                title="Thermal Stress" 
                value={latest?.temp_delta} 
                unit="°C" 
                icon={ThermometerSun} 
                colorClass="rose-400" 
            />
        </div>
    );
};

export default KpiGrid;
