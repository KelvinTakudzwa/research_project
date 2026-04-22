import React, { useState } from 'react';
import { useSolarData } from '../../hooks/useSolarData';
import { BrainCircuit, RefreshCw, CheckCircle2 } from 'lucide-react';
import axios from 'axios';

const MlControl = () => {
    const { calibrationLog, setCalibrationLog } = useSolarData();
    const [retraining, setRetraining] = useState(false);
    const [statusMsg, setStatusMsg] = useState('');

    const handleRetrain = async () => {
        setRetraining(true);
        setStatusMsg('Calibrating Neural Weights...');
        try {
            const res = await axios.post('/api/trigger_retraining');
            setStatusMsg(res.data.status || 'Retraining Triggered Space-Time.');
            // Optimistically update log
            setCalibrationLog(prev => [{
                calibration_id: Date.now(),
                timestamp: new Date().toISOString(),
                event_type: 'Manual Retrain',
                status: 'Triggered'
            }, ...prev]);
        } catch (error) {
            console.error("Retrain error:", error);
            setStatusMsg('Calibration Failed.');
        } finally {
            setTimeout(() => {
                setRetraining(false);
                setStatusMsg('');
            }, 3000);
        }
    };

    return (
        <div className="glass-panel p-5 flex flex-col h-full bg-indigo-900/10 border-indigo-500/20">
            <div className="flex items-center gap-3 mb-4 border-b border-indigo-500/10 pb-4">
                <div className="p-2.5 rounded-xl bg-indigo-600/20 border border-indigo-500/30 text-indigo-400">
                    <BrainCircuit size={20} className="drop-shadow-[0_0_8px_currentColor]" />
                </div>
                <div>
                    <h3 className="font-outfit font-semibold text-white tracking-wide">AI Core Engine</h3>
                    <p className="text-[10px] text-indigo-300/70 tracking-widest uppercase">Isolation Forest V2.0</p>
                </div>
            </div>

            <div className="flex-1 flex flex-col justify-between">
                
                {/* Calibration Logs */}
                <div className="flex-1 space-y-2 mb-4 overflow-y-auto custom-scrollbar pr-2">
                    {calibrationLog && calibrationLog.length > 0 ? (
                        calibrationLog.slice(0, 3).map((log, i) => {
                            const rawTime = log.timestamp || log.retrain_timestamp;
                            const timeStr = rawTime 
                                ? new Date(rawTime).toLocaleTimeString() 
                                : 'Unknown Time';
                            
                            const isFail = log.status?.includes('Fail');
                            const displayStatus = log.status || `RMSE: ${log.rmse_score ? log.rmse_score.toFixed(4) : 'N/A'}`;

                            return (
                                <div key={i} className="flex justify-between items-center px-3 py-2 rounded-lg bg-black/20 border border-white/5 text-xs">
                                    <span className="text-slate-400">{timeStr}</span>
                                    <span className={isFail ? 'text-rose-400' : 'text-emerald-400'}>
                                        {displayStatus}
                                    </span>
                                </div>
                            );
                        })
                    ) : (
                        <div className="text-xs text-slate-500 italic text-center pt-2">No recent calibrations.</div>
                    )}
                </div>

                {/* Retrain Action */}
                <div className="relative">
                    <button 
                        onClick={handleRetrain} 
                        disabled={retraining}
                        className={`w-full py-3 rounded-xl font-bold tracking-widest uppercase text-xs transition-all duration-300 flex justify-center items-center gap-2 overflow-hidden
                            ${retraining 
                                ? 'bg-indigo-600/50 text-indigo-200 cursor-not-allowed border border-indigo-500/50' 
                                : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-[0_0_20px_-5px_rgba(99,102,241,0.5)] hover:shadow-[0_0_30px_-5px_rgba(99,102,241,0.7)]'
                            }
                        `}
                    >
                        {retraining ? (
                            <>
                                <RefreshCw size={16} className="animate-spin" />
                                {statusMsg}
                            </>
                        ) : (
                            <>
                                <CheckCircle2 size={16} />
                                Trigger Calibration
                            </>
                        )}
                        
                        {/* Shine effect */}
                        {!retraining && (
                            <div className="absolute inset-0 -translate-x-[150%] bg-gradient-to-r from-transparent via-white/20 to-transparent hover:animate-[shimmer_1.5s_infinite]"></div>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default MlControl;
