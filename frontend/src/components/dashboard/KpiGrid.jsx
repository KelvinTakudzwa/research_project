import React from 'react';
import { useSolarData } from '../../hooks/useSolarData';
import StatusCard from './StatusCard';
import { Zap, Battery, Sun, Activity, ThermometerSun, PlugZap } from 'lucide-react';

const KpiGrid = () => {
    const { latest } = useSolarData();

    return (
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-6">
            <StatusCard
                title="PV Power"
                value={latest?.pv_power_w != null ? latest.pv_power_w.toFixed(1) : null}
                unit="W"
                icon={Zap}
                colorClass="indigo-400"
            />
            <StatusCard
                title="Battery SoC"
                value={latest?.soc_percent != null ? latest.soc_percent.toFixed(1) : null}
                unit="%"
                icon={Battery}
                colorClass="emerald-400"
            />
            <StatusCard
                title="AC Load"
                value={latest?.ac_power_w != null ? latest.ac_power_w.toFixed(1) : null}
                unit="W"
                icon={PlugZap}
                colorClass="amber-400"
            />
            <StatusCard
                title="Batt Voltage"
                value={latest?.battery_voltage_v != null ? latest.battery_voltage_v.toFixed(2) : null}
                unit="V"
                icon={Activity}
                colorClass="cyan-400"
            />
            <StatusCard
                title="Irradiance"
                value={latest?.irradiance_wm2 != null ? latest.irradiance_wm2.toFixed(1) : null}
                unit="W/m²"
                icon={Sun}
                colorClass="yellow-400"
            />
            <StatusCard
                title="Thermal Stress"
                value={latest?.temp_delta_c != null ? latest.temp_delta_c.toFixed(1) : null}
                unit="°C ΔT"
                icon={ThermometerSun}
                colorClass="rose-400"
            />
        </div>
    );
};

export default KpiGrid;
