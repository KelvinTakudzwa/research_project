import { useContext } from 'react';
import { SolarDataContext } from '../context/SolarDataContext';

export const useSolarData = () => {
    const context = useContext(SolarDataContext);
    if (context === undefined) {
        throw new Error('useSolarData must be used within a SolarDataProvider');
    }
    return context;
};
