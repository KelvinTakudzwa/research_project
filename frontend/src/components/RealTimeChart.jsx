import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const RealTimeChart = ({ data }) => {
    // Format timestamp for X-Axis
    const formattedData = data.map(d => ({
        ...d,
        time: new Date(d.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    }));

    return (
        <ResponsiveContainer width="100%" height="100%">
            <LineChart data={formattedData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="time" stroke="#9CA3AF" />
                <YAxis yAxisId="left" stroke="#9CA3AF" />
                <YAxis yAxisId="right" orientation="right" stroke="#9CA3AF" />
                <Tooltip
                    contentStyle={{ backgroundColor: '#1F2937', borderColor: '#374151', color: '#F3F4F6' }}
                    itemStyle={{ color: '#F3F4F6' }}
                />
                <Legend />
                <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey="batt_voltage"
                    stroke="#34D399"
                    name="Battery Voltage (V)"
                    dot={false}
                    strokeWidth={2}
                />
                <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="pv_current"
                    stroke="#FBBF24"
                    name="PV Current (A)"
                    dot={false}
                    strokeWidth={2}
                />
            </LineChart>
        </ResponsiveContainer>
    );
};

export default RealTimeChart;
