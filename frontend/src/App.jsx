import React from 'react';
import Dashboard from './components/Dashboard';

function App() {
  return (
    <div className="min-h-screen p-6 font-sans text-slate-100">
      <div className="max-w-7xl mx-auto space-y-8">
        <header className="flex flex-col md:flex-row md:items-end md:justify-between border-b border-indigo-500/30 pb-6">
          <div>
            <h1 className="text-4xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-indigo-400 drop-shadow-sm">Solar Mini-Grid Monitor</h1>
            <p className="text-slate-400 mt-2 font-light tracking-wide">AI-Powered Predictive Maintenance System</p>
          </div>
          <div className="mt-4 md:mt-0 px-4 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-xs font-mono uppercase tracking-widest">
            Prototype v1.0
          </div>
        </header>
        <main>
          <Dashboard />
        </main>
      </div>
    </div>
  );
}

export default App;
