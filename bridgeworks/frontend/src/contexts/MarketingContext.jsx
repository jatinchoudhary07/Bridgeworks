import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { apiClient } from '../apiClient';
import { BACKEND_URL } from '../config/api';

const MarketingContext = createContext();

export const MarketingProvider = ({ children }) => {
    const [startDate, setStartDate] = useState(new Date().toISOString().split('T')[0]);
    const [endDate, setEndDate] = useState(new Date().toISOString().split('T')[0]);
    
    // Global Data States
    const [campaigns, setCampaigns] = useState([]);
    const [googleCampaigns, setGoogleCampaigns] = useState([]);
    const [loading, setLoading] = useState(false);
    const [syncing, setSyncing] = useState(false);
    const [syncMsg, setSyncMsg] = useState(null);
    const [syncError, setSyncError] = useState(null);

    const updateDateRange = (start, end) => {
        setStartDate(start);
        setEndDate(end);
    };

    const value = {
        startDate,
        endDate,
        updateDateRange,
        campaigns,
        setCampaigns,
        googleCampaigns,
        setGoogleCampaigns,
        loading,
        setLoading,
        syncing,
        setSyncing,
        syncMsg,
        setSyncMsg,
        syncError,
        setSyncError
    };

    return (
        <MarketingContext.Provider value={value}>
            {children}
        </MarketingContext.Provider>
    );
};

export const useMarketing = () => {
    const context = useContext(MarketingContext);
    if (!context) {
        throw new Error('useMarketing must be used within a MarketingProvider');
    }
    return context;
};
