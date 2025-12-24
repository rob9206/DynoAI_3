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
    isSimulated: boolean;
    simState: string | null;
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

// Get channel configuration with flexible matching
export function getChannelConfig(channelName: string) {
    // Try exact match first
    if (JETDRIVE_CHANNEL_CONFIG[channelName]) {
        return JETDRIVE_CHANNEL_CONFIG[channelName];
    }
    
    // Try case-insensitive match
    const lowerName = channelName.toLowerCase();
    for (const [key, config] of Object.entries(JETDRIVE_CHANNEL_CONFIG)) {
        if (key.toLowerCase() === lowerName) {
            return config;
        }
    }
    
    // Try partial match for common patterns
    if (lowerName.includes('rpm')) {
        return JETDRIVE_CHANNEL_CONFIG['RPM'] || JETDRIVE_CHANNEL_CONFIG['Digital RPM 1'];
    }
    if (lowerName.includes('afr') || lowerName.includes('air/fuel')) {
        return JETDRIVE_CHANNEL_CONFIG['AFR'] || JETDRIVE_CHANNEL_CONFIG['Air/Fuel Ratio 1'];
    }
    if (lowerName.includes('force') || lowerName.includes('load')) {
        return JETDRIVE_CHANNEL_CONFIG['Force Drum 1'];
    }
    if (lowerName.includes('map') || lowerName.includes('manifold')) {
        return JETDRIVE_CHANNEL_CONFIG['MAP'] || JETDRIVE_CHANNEL_CONFIG['MAP kPa'];
    }
    if (lowerName.includes('tps') || lowerName.includes('throttle')) {
        return JETDRIVE_CHANNEL_CONFIG['TPS'];
    }
    if (lowerName.includes('horsepower') || lowerName.includes('hp')) {
        return JETDRIVE_CHANNEL_CONFIG['HP'] || JETDRIVE_CHANNEL_CONFIG['Horsepower'];
    }
    if (lowerName.includes('torque') || lowerName.includes('tq')) {
        return JETDRIVE_CHANNEL_CONFIG['TQ'] || JETDRIVE_CHANNEL_CONFIG['Torque'];
    }
    
    // Default fallback
    return {
        label: channelName,
        units: '',
        min: 0,
        max: 100,
        decimals: 2,
        color: '#888'
    };
}

// Channel configuration for display
// Maps both JetDrive channel names and fallback chan_X names
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
    // === Atmospheric Probe (from JetDrive names) ===
    'Humidity': { label: 'Humidity', units: '%', min: 0, max: 100, decimals: 1, color: '#60a5fa' },
    'Pressure': { label: 'Pressure', units: 'kPa', min: 90, max: 110, decimals: 2, color: '#a78bfa' },
    'Temperature 1': { label: 'Temperature 1', units: '°C', min: 0, max: 50, decimals: 1, color: '#f97316' },
    'Temperature 2': { label: 'Temperature 2', units: '°C', min: 0, max: 50, decimals: 1, color: '#fb923c' },
    'Temperature': { label: 'Temperature', units: '°C', min: 0, max: 50, decimals: 1, color: '#f97316' },

    // Fallback chan_X names (based on observed values from your dyno)
    'chan_6': { label: 'Temperature 1', units: '°C', min: 0, max: 50, decimals: 1, color: '#f97316' },
    'chan_7': { label: 'Temperature 2', units: '°C', min: 0, max: 50, decimals: 1, color: '#fb923c' },
    'chan_8': { label: 'Humidity', units: '%', min: 0, max: 100, decimals: 1, color: '#60a5fa' },
    'chan_9': { label: 'Pressure', units: 'kPa', min: 90, max: 110, decimals: 2, color: '#a78bfa' },

    // === Dyno Channels ===
    'Force Drum 1': { label: 'Force', units: 'lbs', min: 0, max: 500, decimals: 1, color: '#4ade80' },
    'Acceleration': { label: 'Acceleration', units: 'g', min: -2, max: 2, decimals: 3, color: '#22d3ee' },
    'Digital RPM 1': { label: 'RPM 1', units: 'rpm', min: 0, max: 8000, decimals: 0, color: '#4ade80', warning: 6000, critical: 7000 },
    'Digital RPM 2': { label: 'RPM 2', units: 'rpm', min: 0, max: 8000, decimals: 0, color: '#22d3ee' },
    'RPM': { label: 'RPM', units: 'rpm', min: 0, max: 8000, decimals: 0, color: '#4ade80', warning: 6000, critical: 7000 },

    // Fallback dyno chan_X names
    'chan_39': { label: 'Force', units: 'lbs', min: 0, max: 500, decimals: 1, color: '#4ade80' },
    'chan_40': { label: 'Acceleration', units: 'g', min: -2, max: 2, decimals: 3, color: '#22d3ee' },
    'chan_42': { label: 'RPM 1', units: 'rpm', min: 0, max: 8000, decimals: 0, color: '#4ade80' },
    'chan_43': { label: 'RPM 2', units: 'rpm', min: 0, max: 8000, decimals: 0, color: '#22d3ee' },

    // === AFR / Lambda Channels ===
    'Air/Fuel Ratio 1': { label: 'AFR Front', units: ':1', min: 10, max: 18, decimals: 2, color: '#f472b6', warning: 15.5, critical: 16.5 },
    'Air/Fuel Ratio 2': { label: 'AFR Rear', units: ':1', min: 10, max: 18, decimals: 2, color: '#fb923c', warning: 15.5, critical: 16.5 },
    'Air/Fuel Ratio': { label: 'AFR', units: ':1', min: 10, max: 18, decimals: 2, color: '#f472b6', warning: 15.5, critical: 16.5 },
    'Lambda 1': { label: 'Lambda 1', units: 'λ', min: 0.7, max: 1.3, decimals: 3, color: '#f472b6' },
    'Lambda 2': { label: 'Lambda 2', units: 'λ', min: 0.7, max: 1.3, decimals: 3, color: '#fb923c' },
    'AFR 1': { label: 'AFR 1', units: ':1', min: 10, max: 18, decimals: 2, color: '#f472b6' },
    'AFR': { label: 'AFR', units: ':1', min: 10, max: 18, decimals: 2, color: '#f472b6' },

    // Fallback AFR chan_X names (based on observed data)
    'chan_23': { label: 'AFR 1', units: ':1', min: 10, max: 18, decimals: 2, color: '#f472b6' },
    'chan_28': { label: 'AFR 2', units: ':1', min: 10, max: 18, decimals: 2, color: '#fb923c' },
    'chan_15': { label: 'Lambda', units: 'λ', min: 0.7, max: 1.3, decimals: 3, color: '#a78bfa' },
    'chan_30': { label: 'Correction', units: '', min: 0, max: 2, decimals: 3, color: '#22d3ee' },

    // === Dyno Performance Channels ===
    'Horsepower': { label: 'Horsepower', units: 'HP', min: 0, max: 200, decimals: 1, color: '#10b981' },
    'HP': { label: 'Horsepower', units: 'HP', min: 0, max: 200, decimals: 1, color: '#10b981' },
    'Torque': { label: 'Torque', units: 'ft-lb', min: 0, max: 150, decimals: 1, color: '#8b5cf6' },
    'TQ': { label: 'Torque', units: 'ft-lb', min: 0, max: 150, decimals: 1, color: '#8b5cf6' },

    // === Engine Sensors ===
    'MAP kPa': { label: 'MAP', units: 'kPa', min: 0, max: 105, decimals: 1, color: '#06b6d4' },
    'MAP': { label: 'MAP', units: 'kPa', min: 0, max: 105, decimals: 1, color: '#06b6d4' },
    'TPS': { label: 'TPS', units: '%', min: 0, max: 100, decimals: 1, color: '#14b8a6' },
    'IAT': { label: 'IAT', units: '°F', min: 0, max: 200, decimals: 0, color: '#f59e0b' },
    'IAT F': { label: 'IAT', units: '°F', min: 0, max: 200, decimals: 0, color: '#f59e0b' },
    'VBatt': { label: 'Battery', units: 'V', min: 11, max: 15, decimals: 1, color: '#eab308' },

    // Fallback chan_X names for performance channels
    'chan_100': { label: 'Torque', units: 'ft-lb', min: 0, max: 150, decimals: 1, color: '#8b5cf6' },
    'chan_101': { label: 'Horsepower', units: 'HP', min: 0, max: 200, decimals: 1, color: '#10b981' },
    'chan_102': { label: 'MAP', units: 'kPa', min: 0, max: 105, decimals: 1, color: '#06b6d4' },
    'chan_103': { label: 'TPS', units: '%', min: 0, max: 100, decimals: 1, color: '#14b8a6' },
    'chan_104': { label: 'IAT', units: '°F', min: 0, max: 200, decimals: 0, color: '#f59e0b' },
    'chan_105': { label: 'Battery', units: 'V', min: 11, max: 15, decimals: 1, color: '#eab308' },

    // Other observed channels
    'chan_0': { label: 'Channel 0', units: '', min: 0, max: 100, decimals: 2, color: '#888' },
    'chan_1': { label: 'Channel 1', units: '', min: 0, max: 100, decimals: 2, color: '#888' },
    'chan_2': { label: 'Channel 2', units: '', min: 0, max: 100, decimals: 2, color: '#888' },
    'chan_3': { label: 'Channel 3', units: '', min: 0, max: 200, decimals: 2, color: '#888' },
    'chan_14': { label: 'Channel 14', units: '', min: 0, max: 1, decimals: 0, color: '#888' },
    'chan_16': { label: 'Channel 16', units: '', min: 0, max: 1, decimals: 0, color: '#888' },
    'chan_17': { label: 'Voltage 1', units: 'V', min: 0, max: 5, decimals: 2, color: '#facc15' },
    'chan_18': { label: 'Voltage 2', units: 'V', min: 0, max: 1, decimals: 3, color: '#facc15' },
    'chan_20': { label: 'Flag 1', units: '', min: 0, max: 1, decimals: 0, color: '#888' },
    'chan_22': { label: 'Voltage 3', units: 'V', min: 0, max: 5, decimals: 2, color: '#facc15' },
    'chan_24': { label: 'Lambda Raw', units: 'λ', min: 0.7, max: 1.6, decimals: 3, color: '#a78bfa' },
    'chan_26': { label: 'Flag 2', units: '', min: 0, max: 1, decimals: 0, color: '#888' },
    'chan_29': { label: 'Sensor', units: '', min: 0, max: 1, decimals: 3, color: '#888' },
};

/**
 * Get channel configuration with flexible name matching.
 * Tries exact match, case-insensitive match, and partial match patterns.
 */
// Cache for channel config lookups to avoid repeated string operations
const channelConfigCache = new Map<string, {
    label: string;
    units: string;
    min: number;
    max: number;
    decimals: number;
    color: string;
    warning?: number;
    critical?: number;
}>();

// Debug logging throttle - log every N polls to avoid console spam
const DEBUG_LOG_THROTTLE = 100;

function getChannelConfig(channelName: string) {
    // Check cache first
    if (channelConfigCache.has(channelName)) {
        return channelConfigCache.get(channelName);
    }
    
    let config;
    
    // Try exact match first
    if (JETDRIVE_CHANNEL_CONFIG[channelName]) {
        config = JETDRIVE_CHANNEL_CONFIG[channelName];
        channelConfigCache.set(channelName, config);
        return config;
    }
    
    // Try case-insensitive match
    const lowerName = channelName.toLowerCase();
    for (const [key, cfg] of Object.entries(JETDRIVE_CHANNEL_CONFIG)) {
        if (key.toLowerCase() === lowerName) {
            config = cfg;
            channelConfigCache.set(channelName, config);
            return config;
        }
    }
    
    // Try partial match for common patterns
    if (lowerName.includes('rpm')) {
        config = JETDRIVE_CHANNEL_CONFIG['RPM'] || {
            label: channelName,
            units: 'rpm',
            min: 0,
            max: 8000,
            decimals: 0,
            color: '#4ade80'
        };
        channelConfigCache.set(channelName, config);
        return config;
    }
    if (lowerName.includes('afr') || lowerName.includes('air/fuel') || lowerName.includes('air-fuel')) {
        config = JETDRIVE_CHANNEL_CONFIG['AFR'] || {
            label: channelName,
            units: ':1',
            min: 10,
            max: 18,
            decimals: 2,
            color: '#f472b6'
        };
        channelConfigCache.set(channelName, config);
        return config;
    }
    if (lowerName.includes('lambda')) {
        config = {
            label: channelName,
            units: 'λ',
            min: 0.7,
            max: 1.3,
            decimals: 3,
            color: '#a78bfa'
        };
        channelConfigCache.set(channelName, config);
        return config;
    }
    if (lowerName.includes('force') || lowerName.includes('load') || lowerName.includes('drum')) {
        config = JETDRIVE_CHANNEL_CONFIG['Force Drum 1'] || {
            label: channelName,
            units: 'lbs',
            min: 0,
            max: 500,
            decimals: 1,
            color: '#4ade80'
        };
        channelConfigCache.set(channelName, config);
        return config;
    }
    if (lowerName.includes('hp') || lowerName.includes('horsepower') || lowerName.includes('power')) {
        config = {
            label: channelName,
            units: 'HP',
            min: 0,
            max: 200,
            decimals: 1,
            color: '#10b981'
        };
        channelConfigCache.set(channelName, config);
        return config;
    }
    if (lowerName.includes('tq') || lowerName.includes('torque')) {
        config = {
            label: channelName,
            units: 'ft-lb',
            min: 0,
            max: 150,
            decimals: 1,
            color: '#8b5cf6'
        };
        channelConfigCache.set(channelName, config);
        return config;
    }
    if (lowerName.includes('map')) {
        config = {
            label: channelName,
            units: 'kPa',
            min: 0,
            max: 105,
            decimals: 1,
            color: '#06b6d4'
        };
        channelConfigCache.set(channelName, config);
        return config;
    }
    if (lowerName.includes('tps') || lowerName.includes('throttle')) {
        config = {
            label: channelName,
            units: '%',
            min: 0,
            max: 100,
            decimals: 1,
            color: '#14b8a6'
        };
        channelConfigCache.set(channelName, config);
        return config;
    }
    
    // Default fallback
    config = {
        label: channelName,
        units: '',
        min: 0,
        max: 100,
        decimals: 2,
        color: '#888888'
    };
    channelConfigCache.set(channelName, config);
    return config;
}

const DEFAULT_OPTIONS: Required<UseJetDriveLiveOptions> = {
    apiUrl: 'http://127.0.0.1:5001/api/jetdrive',
    autoConnect: false,
    pollInterval: 50,  // 50ms = 20 updates/sec for ultra-responsive gauges and VE table
    maxHistoryPoints: 300,
};

export function useJetDriveLive(options: UseJetDriveLiveOptions = {}): UseJetDriveLiveReturn {
    const opts = { ...DEFAULT_OPTIONS, ...options };

    // Connection state
    const [isConnected, setIsConnected] = useState(false);
    const [isCapturing, setIsCapturing] = useState(false);
    const [isSimulated, setIsSimulated] = useState(false);
    const [simState, setSimState] = useState<string | null>(null);
    const [connectionError, setConnectionError] = useState<string | null>(null);
    const [providerName, setProviderName] = useState<string | null>(null);
    const [channelCount, setChannelCount] = useState(0);

    // Data state
    const [channels, setChannels] = useState<Record<string, JetDriveChannel>>({});
    const [snapshot, setSnapshot] = useState<JetDriveSnapshot | null>(null);
    const [history, setHistory] = useState<Record<string, { time: number; value: number }[]>>({});

    // Refs
    const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const pollCountRef = useRef(0);  // Track polls for throttled history updates

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

            // Increment poll counter
            pollCountRef.current++;

            setIsCapturing(data.capturing);
            setIsSimulated(data.simulated || false);
            setSimState(data.sim_state || null);

            // If simulated, we're always "connected"
            if (data.simulated) {
                setIsConnected(true);
            }

            if (data.channels && Object.keys(data.channels).length > 0) {
                // Convert to LiveLink-compatible format
                const newChannels: Record<string, JetDriveChannel> = {};
                const newSnapshot: JetDriveSnapshot = {
                    timestamp: Date.now(),
                    channels: {},
                    units: {},
                };

                // Debug: Log raw channel names (on first poll or periodically)
                const rawChannelNames = Object.keys(data.channels);
                if (pollCountRef.current === 1 || pollCountRef.current % DEBUG_LOG_THROTTLE === 0) {
                    console.log('[useJetDriveLive] Raw channels:', rawChannelNames);
                }

                const unmappedChannels: string[] = [];

                for (const [name, ch] of Object.entries(data.channels)) {
                    const channel = ch as { id: number; name: string; value: number; timestamp: number };
                    const config = getChannelConfig(name);

                    // Track unmapped channels (those not in JETDRIVE_CHANNEL_CONFIG)
                    if (!JETDRIVE_CHANNEL_CONFIG[name]) {
                        unmappedChannels.push(name);
                    }

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

                // Log unmapped channels (only on first poll or periodically)
                if (unmappedChannels.length > 0 && (pollCountRef.current === 1 || pollCountRef.current % DEBUG_LOG_THROTTLE === 0)) {
                    console.warn('[useJetDriveLive] Unmapped channels:', unmappedChannels);
                    console.warn('[useJetDriveLive] Available mapped channels:', Object.keys(JETDRIVE_CHANNEL_CONFIG));
                }

                // Debug: Log mapped channels summary
                if (pollCountRef.current === 1 || pollCountRef.current % DEBUG_LOG_THROTTLE === 0) {
                    console.log('[useJetDriveLive] Mapped channels:', Object.keys(newChannels));
                    console.log('[useJetDriveLive] Channel count:', Object.keys(newChannels).length);
                }

                setChannels(newChannels);
                setSnapshot(newSnapshot);

                // Update history for charts (every poll for now)
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
        } catch {
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
            startCapture().catch(() => { });
        }
    }, [opts.autoConnect, isConnected, isCapturing, startCapture]);

    return {
        isConnected,
        isCapturing,
        isSimulated,
        simState,
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

