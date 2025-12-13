/**
 * useJetDriveLive - React hook for real-time JetDrive data
 * 
 * Provides the same interface as useLiveLink but connects to JetDrive
 * hardware via the REST API. This allows reusing the LiveLink gauge
 * and chart components with real dyno data.
 */

import { useState, useEffect, useCallback, useRef } from 'react';

// Same types as useLiveLink for compatibility
export interface JetDriveChannel {
    name: string;
    value: number;
    units: string;
    timestamp: number;
    id?: number;
}

export interface JetDriveSnapshot {
    timestamp: number;
    channels: Record<string, number>;
    units: Record<string, string>;
}

export interface UseJetDriveLiveOptions {
    /** API base URL (default: http://127.0.0.1:5001/api/jetdrive) */
    apiUrl?: string;
    /** Auto-connect on mount (default: false) */
    autoConnect?: boolean;
    /** Poll interval in ms (default: 1000) */
    pollInterval?: number;
    /** Max history points for charts (default: 300) */
    maxHistoryPoints?: number;
}

export interface UseJetDriveLiveReturn {
    // Connection state
    isConnected: boolean;
    isCapturing: boolean;
    connectionError: string | null;
    providerName: string | null;
    channelCount: number;

    // Data - compatible with LiveLink components
    channels: Record<string, JetDriveChannel>;
    snapshot: JetDriveSnapshot | null;
    history: Record<string, { time: number; value: number }[]>;

    // Actions
    startCapture: () => Promise<void>;
    stopCapture: () => Promise<void>;
    getChannelValue: (channel: string) => number | null;
    clearHistory: () => void;
}

// Channel configuration for display
export const JETDRIVE_CHANNEL_CONFIG: Record<string, {
    label: string;
    units: string;
    min: number;
    max: number;
    decimals: number;
    color: string;
    warning?: number;
    critical?: number;
}> = {
    // Atmospheric
    'Humidity': { label: 'Humidity', units: '%', min: 0, max: 100, decimals: 1, color: '#60a5fa' },
    'Pressure': { label: 'Pressure', units: 'kPa', min: 90, max: 110, decimals: 2, color: '#a78bfa' },
    'Temperature 1': { label: 'Temperature 1', units: '°C', min: 0, max: 50, decimals: 1, color: '#f97316' },
    'Temperature 2': { label: 'Temperature 2', units: '°C', min: 0, max: 50, decimals: 1, color: '#fb923c' },
    // Dyno
    'Force Drum 1': { label: 'Force', units: 'lbs', min: 0, max: 500, decimals: 1, color: '#4ade80' },
    'Acceleration': { label: 'Acceleration', units: 'g', min: -2, max: 2, decimals: 3, color: '#22d3ee' },
    'Digital RPM 1': { label: 'RPM 1', units: 'rpm', min: 0, max: 8000, decimals: 0, color: '#4ade80', warning: 6000, critical: 7000 },
    'Digital RPM 2': { label: 'RPM 2', units: 'rpm', min: 0, max: 8000, decimals: 0, color: '#22d3ee' },
    // AFR / Lambda
    'Air/Fuel Ratio 1': { label: 'AFR Front', units: ':1', min: 10, max: 18, decimals: 2, color: '#f472b6', warning: 15.5, critical: 16.5 },
    'Air/Fuel Ratio 2': { label: 'AFR Rear', units: ':1', min: 10, max: 18, decimals: 2, color: '#fb923c', warning: 15.5, critical: 16.5 },
    'Lambda 1': { label: 'Lambda 1', units: 'λ', min: 0.7, max: 1.3, decimals: 3, color: '#f472b6' },
    'Lambda 2': { label: 'Lambda 2', units: 'λ', min: 0.7, max: 1.3, decimals: 3, color: '#fb923c' },
    'AFR 1': { label: 'AFR 1', units: ':1', min: 10, max: 18, decimals: 2, color: '#f472b6' },
    'AFR': { label: 'AFR', units: ':1', min: 10, max: 18, decimals: 2, color: '#f472b6' },
};

const DEFAULT_OPTIONS: Required<UseJetDriveLiveOptions> = {
    apiUrl: 'http://127.0.0.1:5001/api/jetdrive',
    autoConnect: false,
    pollInterval: 1000,
    maxHistoryPoints: 300,
};

export function useJetDriveLive(options: UseJetDriveLiveOptions = {}): UseJetDriveLiveReturn {
    const opts = { ...DEFAULT_OPTIONS, ...options };

    // Connection state
    const [isConnected, setIsConnected] = useState(false);
    const [isCapturing, setIsCapturing] = useState(false);
    const [connectionError, setConnectionError] = useState<string | null>(null);
    const [providerName, setProviderName] = useState<string | null>(null);
    const [channelCount, setChannelCount] = useState(0);

    // Data state
    const [channels, setChannels] = useState<Record<string, JetDriveChannel>>({});
    const [snapshot, setSnapshot] = useState<JetDriveSnapshot | null>(null);
    const [history, setHistory] = useState<Record<string, { time: number; value: number }[]>>({});

    // Refs
    const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

    // Check monitor status
    const checkConnection = useCallback(async () => {
        try {
            const res = await fetch(`${opts.apiUrl}/hardware/monitor/status`);
            if (!res.ok) throw new Error('Monitor endpoint unavailable');
            
            const data = await res.json();
            setIsConnected(data.connected);
            
            if (data.providers && data.providers.length > 0) {
                setProviderName(data.providers[0].name);
                setChannelCount(data.providers[0].channel_count || 0);
            }
            
            setConnectionError(null);
        } catch (err) {
            setIsConnected(false);
            setConnectionError(err instanceof Error ? err.message : 'Connection failed');
        }
    }, [opts.apiUrl]);

    // Poll live data
    const pollLiveData = useCallback(async () => {
        try {
            const res = await fetch(`${opts.apiUrl}/hardware/live/data`);
            if (!res.ok) throw new Error('Live data unavailable');
            
            const data = await res.json();
            setIsCapturing(data.capturing);
            
            if (data.channels && Object.keys(data.channels).length > 0) {
                // Convert to LiveLink-compatible format
                const newChannels: Record<string, JetDriveChannel> = {};
                const newSnapshot: JetDriveSnapshot = {
                    timestamp: Date.now(),
                    channels: {},
                    units: {},
                };

                for (const [name, ch] of Object.entries(data.channels)) {
                    const channel = ch as { id: number; name: string; value: number; timestamp: number };
                    const config = JETDRIVE_CHANNEL_CONFIG[name];
                    
                    newChannels[name] = {
                        name,
                        value: channel.value,
                        units: config?.units || '',
                        timestamp: channel.timestamp,
                        id: channel.id,
                    };
                    
                    newSnapshot.channels[name] = channel.value;
                    newSnapshot.units[name] = config?.units || '';
                }

                setChannels(newChannels);
                setSnapshot(newSnapshot);

                // Update history for charts
                setHistory(prev => {
                    const newHistory = { ...prev };
                    const now = Date.now();

                    for (const [name, ch] of Object.entries(newChannels)) {
                        if (!newHistory[name]) {
                            newHistory[name] = [];
                        }
                        newHistory[name] = [
                            ...newHistory[name].slice(-(opts.maxHistoryPoints - 1)),
                            { time: now, value: ch.value }
                        ];
                    }

                    return newHistory;
                });
            }
        } catch (err) {
            // Silent fail for polling
        }
    }, [opts.apiUrl, opts.maxHistoryPoints]);

    // Start capture
    const startCapture = useCallback(async () => {
        try {
            const res = await fetch(`${opts.apiUrl}/hardware/live/start`, { method: 'POST' });
            if (!res.ok) throw new Error('Failed to start capture');
            setIsCapturing(true);
        } catch (err) {
            setConnectionError(err instanceof Error ? err.message : 'Start failed');
            throw err;
        }
    }, [opts.apiUrl]);

    // Stop capture
    const stopCapture = useCallback(async () => {
        try {
            const res = await fetch(`${opts.apiUrl}/hardware/live/stop`, { method: 'POST' });
            if (!res.ok) throw new Error('Failed to stop capture');
            setIsCapturing(false);
        } catch (err) {
            setConnectionError(err instanceof Error ? err.message : 'Stop failed');
            throw err;
        }
    }, [opts.apiUrl]);

    // Get single channel value
    const getChannelValue = useCallback((channel: string): number | null => {
        return channels[channel]?.value ?? null;
    }, [channels]);

    // Clear history
    const clearHistory = useCallback(() => {
        setHistory({});
    }, []);

    // Initial connection check
    useEffect(() => {
        checkConnection();
    }, [checkConnection]);

    // Polling effect
    useEffect(() => {
        // Always poll for status
        const statusInterval = setInterval(checkConnection, 5000);

        // Poll live data when capturing
        if (isCapturing) {
            pollLiveData(); // Immediate poll
            pollIntervalRef.current = setInterval(pollLiveData, opts.pollInterval);
        }

        return () => {
            clearInterval(statusInterval);
            if (pollIntervalRef.current) {
                clearInterval(pollIntervalRef.current);
            }
        };
    }, [isCapturing, checkConnection, pollLiveData, opts.pollInterval]);

    // Auto-connect
    useEffect(() => {
        if (opts.autoConnect && isConnected && !isCapturing) {
            startCapture().catch(() => {});
        }
    }, [opts.autoConnect, isConnected, isCapturing, startCapture]);

    return {
        isConnected,
        isCapturing,
        connectionError,
        providerName,
        channelCount,
        channels,
        snapshot,
        history,
        startCapture,
        stopCapture,
        getChannelValue,
        clearHistory,
    };
}

export default useJetDriveLive;

