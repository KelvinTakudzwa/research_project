import React from 'react';
import { SolarDataProvider } from './context/SolarDataContext';
import DashboardPage from './pages/DashboardPage';

function App() {
  return (
    <SolarDataProvider>
      <DashboardPage />
    </SolarDataProvider>
  );
}

export default App;
