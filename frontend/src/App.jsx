import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { SolarDataProvider } from './context/SolarDataContext';
import ProtectedRoute from './components/common/ProtectedRoute';
import DashboardPage  from './pages/DashboardPage';
import FaultLogsPage  from './pages/FaultLogsPage';
import LoginPage      from './pages/LoginPage';

function App() {
    return (
        <BrowserRouter>
            <Routes>
                <Route path="/login" element={<LoginPage />} />
                <Route
                    path="/"
                    element={
                        <ProtectedRoute>
                            <SolarDataProvider>
                                <DashboardPage />
                            </SolarDataProvider>
                        </ProtectedRoute>
                    }
                />
                <Route
                    path="/faults"
                    element={
                        <ProtectedRoute>
                            <SolarDataProvider>
                                <FaultLogsPage />
                            </SolarDataProvider>
                        </ProtectedRoute>
                    }
                />
                <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
        </BrowserRouter>
    );
}

export default App;
