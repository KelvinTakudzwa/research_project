import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import DashboardLayout from '../layouts/DashboardLayout';
import { useSolarData } from '../hooks/useSolarData';
import { ShieldAlert, AlertOctagon, AlertTriangle, ShieldCheck, RefreshCw, Download, ChevronDown } from 'lucide-react';
import { exportCSV, exportPDF, exportDOCX } from '../utils/reportGenerator';

const SEVERITY_FILTER_OPTIONS = ['All', 'Critical', 'Warning'];

const severityBadge = (severity) => {
    if (severity === 'Critical') return 'bg-red-500/10 border-red-500/30 text-red-400';
    return 'bg-amber-500/10 border-amber-500/30 text-amber-400';
};

const FaultLogsPage = () => {
    const [logs,           setLogs]           = useState([]);
    const [loading,        setLoading]        = useState(true);
    const [refreshing,     setRefreshing]     = useState(false);
    const [severityFilter, setSeverityFilter] = useState('All');
    const [liveCount,      setLiveCount]      = useState(0);
    const [showExportMenu, setShowExportMenu] = useState(false);
    const [exporting,      setExporting]      = useState(false);
    const exportMenuRef = useRef(null);

    const { alerts: wsAlerts } = useSolarData();
    const seenIdsRef = useRef(new Set());

    const loadLogs = useCallback(async (isRefresh = false) => {
        if (isRefresh) setRefreshing(true); else setLoading(true);
        try {
            const res  = await axios.get('/api/alerts/log?limit=500');
            const data = res.data || [];
            setLogs(data);
            seenIdsRef.current = new Set(data.map(r => r.id));
            if (isRefresh) setLiveCount(0);
        } catch (err) {
            console.error('FaultLogsPage load error:', err.message);
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    }, []);

    useEffect(() => { loadLogs(); }, [loadLogs]);

    // Real-time: unshift new WebSocket alerts to top of table
    useEffect(() => {
        if (!wsAlerts || wsAlerts.length === 0) return;
        const newest = wsAlerts[0];
        if (!newest || seenIdsRef.current.has(newest.id)) return;
        seenIdsRef.current.add(newest.id);
        setLogs(prev => [newest, ...prev]);
        setLiveCount(c => c + 1);
    }, [wsAlerts]);

    // Close export menu when clicking outside
    useEffect(() => {
        const handler = (e) => {
            if (exportMenuRef.current && !exportMenuRef.current.contains(e.target)) {
                setShowExportMenu(false);
            }
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, []);

    const filtered     = severityFilter === 'All' ? logs : logs.filter(r => r.alert_severity === severityFilter);
    const filterLabel  = severityFilter;

    const handleExport = async (format) => {
        setShowExportMenu(false);
        setExporting(true);
        try {
            if (format === 'csv')  exportCSV(filtered, filterLabel);
            if (format === 'pdf')  exportPDF(filtered, filterLabel);
            if (format === 'docx') await exportDOCX(filtered, filterLabel);
        } catch (err) {
            console.error('Export error:', err);
        } finally {
            setExporting(false);
        }
    };

    return (
        <DashboardLayout>
            <div className="flex flex-col gap-6 w-full max-w-7xl mx-auto pb-10">

                {/* Header */}
                <div className="flex items-start justify-between mb-2">
                    <div>
                        <h2 className="text-3xl font-outfit font-bold text-white tracking-tight glow-text-soft">Fault Logs</h2>
                        <p className="text-slate-400 text-sm tracking-wide mt-1">
                            Full fault history — historical records and live events
                        </p>
                    </div>

                    {/* Action buttons */}
                    <div className="flex items-center gap-3">
                        {liveCount > 0 && (
                            <div className="flex items-center gap-2 bg-indigo-500/10 border border-indigo-500/30 rounded-xl px-4 py-2">
                                <span className="relative flex h-2 w-2">
                                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                                    <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500"></span>
                                </span>
                                <span className="text-xs text-indigo-300 font-semibold">+{liveCount} live</span>
                            </div>
                        )}

                        {/* Refresh */}
                        <button
                            onClick={() => loadLogs(true)}
                            disabled={refreshing}
                            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-800/60 border border-slate-700/50 text-slate-300 hover:text-white hover:border-slate-600 transition-all text-xs font-semibold disabled:opacity-50"
                        >
                            <RefreshCw size={13} className={refreshing ? 'animate-spin' : ''} />
                            Refresh
                        </button>

                        {/* Download Report dropdown */}
                        <div className="relative" ref={exportMenuRef}>
                            <button
                                onClick={() => setShowExportMenu(v => !v)}
                                disabled={exporting || filtered.length === 0}
                                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600/20 border border-indigo-500/40 text-indigo-300 hover:bg-indigo-600/30 hover:text-indigo-200 transition-all text-xs font-semibold disabled:opacity-50"
                            >
                                <Download size={13} className={exporting ? 'animate-bounce' : ''} />
                                {exporting ? 'Exporting…' : 'Download Report'}
                                <ChevronDown size={11} className={`transition-transform ${showExportMenu ? 'rotate-180' : ''}`} />
                            </button>

                            {showExportMenu && (
                                <div className="absolute right-0 top-full mt-2 w-52 rounded-xl border border-slate-700/60 bg-slate-900/95 backdrop-blur-xl shadow-2xl z-50 overflow-hidden">
                                    <div className="px-3 py-2 border-b border-slate-700/40">
                                        <span className="text-[10px] text-slate-500 uppercase tracking-widest font-semibold">
                                            Export {filtered.length} records ({filterLabel})
                                        </span>
                                    </div>
                                    {[
                                        { fmt: 'csv',  label: 'CSV Spreadsheet',  sub: 'Raw data, Excel-compatible',   color: 'text-emerald-400' },
                                        { fmt: 'pdf',  label: 'PDF Report',        sub: 'Full report with summary',     color: 'text-red-400'     },
                                        { fmt: 'docx', label: 'Word Document',     sub: 'Editable DOCX report',         color: 'text-blue-400'    },
                                    ].map(({ fmt, label, sub, color }) => (
                                        <button
                                            key={fmt}
                                            onClick={() => handleExport(fmt)}
                                            className="w-full flex items-start gap-3 px-4 py-3 hover:bg-white/5 transition-colors text-left"
                                        >
                                            <span className={`text-xs font-bold uppercase tracking-wider mt-0.5 w-10 shrink-0 ${color}`}>{fmt.toUpperCase()}</span>
                                            <span className="flex flex-col">
                                                <span className="text-xs font-semibold text-slate-200">{label}</span>
                                                <span className="text-[10px] text-slate-500">{sub}</span>
                                            </span>
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {/* Filters + count bar */}
                <div className="flex items-center justify-between">
                    <div className="flex gap-2">
                        {SEVERITY_FILTER_OPTIONS.map(opt => (
                            <button
                                key={opt}
                                onClick={() => setSeverityFilter(opt)}
                                className={`px-4 py-1.5 rounded-lg text-xs font-semibold uppercase tracking-wider border transition-all ${
                                    severityFilter === opt
                                        ? 'bg-indigo-600/20 text-indigo-300 border-indigo-500/40'
                                        : 'text-slate-400 border-slate-700/50 hover:border-slate-600 hover:text-slate-200'
                                }`}
                            >
                                {opt}
                            </button>
                        ))}
                    </div>
                    <span className="text-xs text-slate-500 font-medium">
                        {loading ? 'Loading…' : `${filtered.length} records`}
                    </span>
                </div>

                {/* Table */}
                <div className="glass-panel overflow-hidden">
                    {loading ? (
                        <div className="flex items-center justify-center py-16 gap-3 text-slate-400">
                            <RefreshCw size={18} className="animate-spin" />
                            <span className="text-sm">Loading fault log…</span>
                        </div>
                    ) : filtered.length === 0 ? (
                        <div className="flex flex-col items-center justify-center py-16 gap-3 opacity-50">
                            <ShieldCheck size={36} className="text-emerald-400" />
                            <span className="text-sm uppercase tracking-widest text-emerald-300 font-semibold">No faults recorded</span>
                        </div>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b border-white/5 bg-white/[0.02]">
                                        {['Timestamp', 'Fault', 'Severity', 'ML Label', 'Confidence', 'SoC', 'Batt V', 'Batt °C', 'PV W', 'AC W', 'Irr W/m²'].map(col => (
                                            <th key={col} className="px-4 py-3 text-left text-[10px] uppercase tracking-widest text-slate-500 font-semibold whitespace-nowrap">
                                                {col}
                                            </th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {filtered.map((row, i) => {
                                        const isCritical = row.alert_severity === 'Critical';
                                        return (
                                            <tr
                                                key={row.id ?? i}
                                                className={`border-b border-white/[0.03] transition-colors ${
                                                    isCritical ? 'hover:bg-red-900/10' : 'hover:bg-amber-900/10'
                                                }`}
                                            >
                                                <td className="px-4 py-3 text-slate-400 tabular-nums whitespace-nowrap text-xs">
                                                    {row.timestamp ? new Date(row.timestamp).toLocaleString([], {
                                                        month: 'short', day: '2-digit',
                                                        hour: '2-digit', minute: '2-digit', second: '2-digit',
                                                    }) : '--'}
                                                </td>
                                                <td className="px-4 py-3 font-semibold whitespace-nowrap">
                                                    <div className={`flex items-center gap-1.5 ${isCritical ? 'text-red-400' : 'text-amber-400'}`}>
                                                        {isCritical ? <AlertOctagon size={13} className="shrink-0" /> : <AlertTriangle size={13} className="shrink-0" />}
                                                        {row.alert_type || row.pred_label || 'Fault Event'}
                                                    </div>
                                                </td>
                                                <td className="px-4 py-3">
                                                    <span className={`inline-block px-2.5 py-0.5 rounded-full border text-[9px] uppercase tracking-widest font-bold ${severityBadge(row.alert_severity)}`}>
                                                        {row.alert_severity}
                                                    </span>
                                                </td>
                                                <td className="px-4 py-3 text-slate-400 text-xs whitespace-nowrap">
                                                    {row.pred_label?.replace(/_/g, ' ') || '—'}
                                                </td>
                                                <td className="px-4 py-3 text-slate-300 tabular-nums text-xs">
                                                    {row.confidence != null ? `${(row.confidence * 100).toFixed(0)}%` : '—'}
                                                </td>
                                                <td className="px-4 py-3 text-slate-300 tabular-nums text-xs">
                                                    {row.soc_percent != null ? `${parseFloat(row.soc_percent).toFixed(1)}%` : '—'}
                                                </td>
                                                <td className="px-4 py-3 text-slate-300 tabular-nums text-xs">
                                                    {row.battery_voltage_v != null ? `${parseFloat(row.battery_voltage_v).toFixed(2)}V` : '—'}
                                                </td>
                                                <td className="px-4 py-3 text-slate-300 tabular-nums text-xs">
                                                    {row.battery_temp_c != null ? `${parseFloat(row.battery_temp_c).toFixed(1)}°C` : '—'}
                                                </td>
                                                <td className="px-4 py-3 text-slate-300 tabular-nums text-xs">
                                                    {row.pv_power_w != null ? `${parseFloat(row.pv_power_w).toFixed(1)}W` : '—'}
                                                </td>
                                                <td className="px-4 py-3 text-slate-300 tabular-nums text-xs">
                                                    {row.ac_power_w != null ? `${parseFloat(row.ac_power_w).toFixed(1)}W` : '—'}
                                                </td>
                                                <td className="px-4 py-3 text-slate-300 tabular-nums text-xs">
                                                    {row.irradiance_wm2 != null ? `${parseFloat(row.irradiance_wm2).toFixed(1)}` : '—'}
                                                </td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>

            </div>
        </DashboardLayout>
    );
};

export default FaultLogsPage;
