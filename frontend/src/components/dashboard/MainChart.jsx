import React from 'react';
import { useSolarData } from '../../hooks/useSolarData';
import { 
    ResponsiveContainer, ComposedChart, Line, Area, XAxis, YAxis, 
    CartesianGrid, Tooltip, Legend, ReferenceLine
} from 'recharts';

const MainChart = () => {
    const { history } = useSolarData();

    if (!history || history.length === 0) {
        return (
            <div className="glass-panel w-full h-[400px] flex items-center justify-center">
                <span className="text-slate-500 tracking-widest uppercase animate-pulse">Awaiting Telemetry...</span>
            </div>
        );
    }

    // Format time for X-Axis
    const formattedData = history.map(d => ({
        ...d,
        timeLabel: new Date(d.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    }));

    return (
        <div className="glass-panel w-full p-6 flex flex-col gap-4">
            <div className="flex items-center justify-between">
                <h2 className="text-lg font-outfit font-semibold text-white tracking-wide">Real-Time Power Curve</h2>
                <div className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse-soft"></span>
                    <span className="text-xs text-slate-400 uppercase tracking-widest font-semibold">Live Sync</span>
                </div>
            </div>

            <div className="h-[320px] w-full mt-2">
                <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={formattedData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                        <defs>
                            <linearGradient id="colorPower" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#818cf8" stopOpacity={0.3}/>
                                <stop offset="95%" stopColor="#818cf8" stopOpacity={0}/>
                            </linearGradient>
                            <linearGradient id="colorVoltage" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#22d3ee" stopOpacity={0.1}/>
                                <stop offset="95%" stopColor="#22d3ee" stopOpacity={0}/>
                            </linearGradient>
                        </defs>
                        
                        <CartesianGrid strokeDasharray="3 3" stroke="#ffffff15" vertical={false} />
                        
                        <XAxis 
                            dataKey="timeLabel" 
                            stroke="#94a3b8" 
                            fontSize={11} 
                            tickMargin={10}
                            axisLine={false}
                            tickLine={false}
                        />
                        
                        <YAxis 
                            yAxisId="left" 
                            stroke="#94a3b8" 
                            fontSize={11}
                            axisLine={false}
                            tickLine={false}
                        />
                        <YAxis 
                            yAxisId="right" 
                            orientation="right" 
                            stroke="#94a3b8" 
                            fontSize={11}
                            axisLine={false}
                            tickLine={false}
                        />
                        
                        <Tooltip 
                            contentStyle={{ 
                                backgroundColor: 'rgba(15, 23, 42, 0.9)', 
                                backdropFilter: 'blur(10px)',
                                borderColor: 'rgba(255,255,255,0.1)',
                                borderRadius: '12px',
                                color: '#f8fafc',
                                boxShadow: '0 10px 40px -10px rgba(0,0,0,0.5)'
                            }}
                            itemStyle={{ fontSize: '13px', padding: '2px 0' }}
                            labelStyle={{ color: '#94a3b8', marginBottom: '8px', fontSize: '12px' }}
                        />
                        
                        <Legend wrapperStyle={{ paddingTop: '20px', fontSize: '12px' }} iconType="circle" />

                        {/* Power Area */}
                        <Area 
                            yAxisId="left"
                            type="monotone" 
                            dataKey="pv_power_watts" 
                            name="PV Power (W)" 
                            stroke="#818cf8" 
                            strokeWidth={3}
                            fillOpacity={1} 
                            fill="url(#colorPower)" 
                            activeDot={{ r: 6, fill: '#818cf8', stroke: '#fff', strokeWidth: 2 }}
                            isAnimationActive={false}
                        />
                        
                        {/* Voltage Line */}
                        <Line 
                            yAxisId="right"
                            type="monotone" 
                            dataKey="pv_voltage" 
                            name="PV Voltage (V)" 
                            stroke="#22d3ee" 
                            strokeWidth={2}
                            dot={false}
                            isAnimationActive={false}
                        />
                        
                        {/* Load Current Line */}
                        <Line 
                            yAxisId="left"
                            type="monotone" 
                            dataKey="load_current" 
                            name="Load Current (A)" 
                            stroke="#fbbf24" 
                            strokeWidth={2}
                            strokeDasharray="4 4"
                            dot={false}
                            isAnimationActive={false}
                        />
                    </ComposedChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
};

export default MainChart;
