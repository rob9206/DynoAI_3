/**
 * useJetDriveLive - React hook for real-time JetDrive data
 * 
 * Provides the same interface as useLiveLink but connects to JetDrive
 * hardware via the REST API. This allows reusing the LiveLink gauge
 * and chart components with real dyno data.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { playUiSound } from '@/lib/ui-sounds';

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function getString(value: unknown): string | null {
    return typeof value === 'string' ? value : null;
}

function getNumber(value: unknown): number | null {
    return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function getBoolean(value: unknown): boolean | null {
    return typeof value === 'boolean' ? value : null;
}

// Channel category types
export type ChannelCategory = 'atmospheric' | 'dyno' | 'afr' | 'engine' | 'misc';

export const CHANNEL_CATEGORIES: Record<ChannelCategory, { label: string; icon: string; order: number }> = {
    atmospheric: { label: 'Atmospheric', icon: 'Cloud', order: 1 },
    dyno: { label: 'Dyno', icon: 'Gauge', order: 2 },
    afr: { label: 'Air/Fuel', icon: 'Flame', order: 3 },
    engine: { label: 'Engine', icon: 'Zap', order: 4 },
    misc: { label: 'System', icon: 'Activity', order: 5 },
} as const;

// Same types as useLiveLink for compatibility
export interface JetDriveChannel {
    name: string;
    value: number;
    units: string;
    timestamp: number;
    id?: number;
    category?: ChannelCategory;
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
    /** How often to publish chart history state (ms). History points are still collected every poll. */
    historyPublishIntervalMs?: number;
    /** Max history points for charts (default: 300) */
    maxHistoryPoints?: number;
    /** Enables verbose debug logging (default: false) */
    debug?: boolean;
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
    clearChannels: () => Promise<void>;
}

// Channel configuration type with category
export interface ChannelConfig {
    label: string;
    units: string;
    min: number;
    max: number;
    decimals: number;
    color: string;
    category: ChannelCategory;
    warning?: number;
    critical?: number;
}

// Channel configuration for display
// Maps both JetDrive channel names and fallback chan_X names
export const JETDRIVE_CHANNEL_CONFIG: Record<string, ChannelConfig> = {
    // ==========================================================================
    // ATMOSPHERIC PROBE CHANNELS
    // ==========================================================================
    'Humidity': { label: 'Humidity', units: '%', min: 0, max: 100, decimals: 1, color: '#60a5fa', category: 'atmospheric' },
    'Pressure': { label: 'Baro Pressure', units: 'kPa', min: 90, max: 110, decimals: 2, color: '#a78bfa', category: 'atmospheric' },
    'Temperature 1': { label: 'Ambient Temp 1', units: '°C', min: -10, max: 50, decimals: 1, color: '#f97316', category: 'atmospheric' },
    'Temperature 2': { label: 'Ambient Temp 2', units: '°C', min: -10, max: 50, decimals: 1, color: '#fb923c', category: 'atmospheric' },

    // ==========================================================================
    // DYNO CORE CHANNELS (RPM, Power, Torque, Force, Speed)
    // ==========================================================================
    'Digital RPM 1': { label: 'RPM 1', units: 'rpm', min: 0, max: 8000, decimals: 0, color: '#4ade80', category: 'dyno', warning: 6000, critical: 7000 },
    'Digital RPM 2': { label: 'RPM 2', units: 'rpm', min: 0, max: 8000, decimals: 0, color: '#22d3ee', category: 'dyno' },
    'Engine RPM': { label: 'Engine RPM', units: 'rpm', min: 0, max: 8000, decimals: 0, color: '#4ade80', category: 'dyno', warning: 6000, critical: 7000 },
    'RPM': { label: 'RPM', units: 'rpm', min: 0, max: 8000, decimals: 0, color: '#4ade80', category: 'dyno', warning: 6000, critical: 7000 },
    
    'Horsepower': { label: 'Horsepower', units: 'HP', min: 0, max: 200, decimals: 1, color: '#10b981', category: 'dyno' },
    'HP': { label: 'HP', units: 'HP', min: 0, max: 200, decimals: 1, color: '#10b981', category: 'dyno' },
    'Power': { label: 'Power', units: 'HP', min: 0, max: 200, decimals: 1, color: '#10b981', category: 'dyno' },
    'Power Drum 1': { label: 'Power Drum 1', units: 'HP', min: 0, max: 200, decimals: 1, color: '#10b981', category: 'dyno' },
    'Power (uncorrected)': { label: 'Power (uncorr)', units: 'HP', min: 0, max: 200, decimals: 1, color: '#10b981', category: 'dyno' },
    'Power Drum 1 (uncorrected)': { label: 'Power Drum 1 (uncorr)', units: 'HP', min: 0, max: 200, decimals: 1, color: '#10b981', category: 'dyno' },
    
    'Torque': { label: 'Torque', units: 'ft-lb', min: 0, max: 200, decimals: 1, color: '#8b5cf6', category: 'dyno' },
    'TQ': { label: 'TQ', units: 'ft-lb', min: 0, max: 200, decimals: 1, color: '#8b5cf6', category: 'dyno' },
    'Torque Drum 1': { label: 'Torque Drum 1', units: 'ft-lb', min: 0, max: 200, decimals: 1, color: '#8b5cf6', category: 'dyno' },
    'Torque (uncorrected)': { label: 'Torque (uncorr)', units: 'ft-lb', min: 0, max: 200, decimals: 1, color: '#8b5cf6', category: 'dyno' },
    'Torque Drum 1 (uncorrected)': { label: 'Torque Drum 1 (uncorr)', units: 'ft-lb', min: 0, max: 200, decimals: 1, color: '#8b5cf6', category: 'dyno' },
    
    'Force': { label: 'Force', units: 'lbs', min: 0, max: 500, decimals: 1, color: '#4ade80', category: 'dyno' },
    'Force 1': { label: 'Force 1', units: 'lbs', min: 0, max: 500, decimals: 1, color: '#4ade80', category: 'dyno' },
    'Force Drum 1': { label: 'Force Drum 1', units: 'lbs', min: 0, max: 500, decimals: 1, color: '#4ade80', category: 'dyno' },
    
    'Speed': { label: 'Speed', units: 'mph', min: 0, max: 200, decimals: 1, color: '#06b6d4', category: 'dyno' },
    'Speed 1': { label: 'Speed 1', units: 'mph', min: 0, max: 200, decimals: 1, color: '#06b6d4', category: 'dyno' },
    'Distance': { label: 'Distance', units: 'ft', min: 0, max: 1000, decimals: 1, color: '#888', category: 'dyno' },
    'Distance 1': { label: 'Distance 1', units: 'ft', min: 0, max: 1000, decimals: 1, color: '#888', category: 'dyno' },
    'Acceleration': { label: 'Acceleration', units: 'g', min: -2, max: 20, decimals: 3, color: '#22d3ee', category: 'dyno' },

    // ==========================================================================
    // AIR/FUEL RATIO CHANNELS
    // ==========================================================================
    'User Analog 1': { label: 'AFR Front', units: ':1', min: 7, max: 22, decimals: 2, color: '#f472b6', category: 'afr', warning: 15.5, critical: 16.5 },
    'User Analog 2': { label: 'AFR Rear', units: ':1', min: 7, max: 22, decimals: 2, color: '#fb923c', category: 'afr', warning: 15.5, critical: 16.5 },
    'LC1 Volts Petrol AFR': { label: 'LC1 AFR', units: ':1', min: 7, max: 22, decimals: 2, color: '#f472b6', category: 'afr', warning: 15.5, critical: 16.5 },
    'LC2 Volts Petrol AFR': { label: 'LC2 AFR', units: ':1', min: 7, max: 22, decimals: 2, color: '#fb923c', category: 'afr', warning: 15.5, critical: 16.5 },
    'LC2 Volts Petrol AFR2': { label: 'LC2 AFR 2', units: ':1', min: 7, max: 22, decimals: 2, color: '#fb923c', category: 'afr', warning: 15.5, critical: 16.5 },
    'Air/Fuel Ratio 1': { label: 'AFR Front', units: ':1', min: 10, max: 18, decimals: 2, color: '#f472b6', category: 'afr', warning: 15.5, critical: 16.5 },
    'Air/Fuel Ratio 2': { label: 'AFR Rear', units: ':1', min: 10, max: 18, decimals: 2, color: '#fb923c', category: 'afr', warning: 15.5, critical: 16.5 },
    'Air/Fuel Ratio': { label: 'AFR', units: ':1', min: 10, max: 18, decimals: 2, color: '#f472b6', category: 'afr', warning: 15.5, critical: 16.5 },
    'AFR 1': { label: 'AFR 1', units: ':1', min: 10, max: 18, decimals: 2, color: '#f472b6', category: 'afr' },
    'AFR': { label: 'AFR', units: ':1', min: 10, max: 18, decimals: 2, color: '#f472b6', category: 'afr' },
    'Lambda 1': { label: 'Lambda 1', units: 'λ', min: 0.7, max: 1.3, decimals: 3, color: '#f472b6', category: 'afr' },
    'Lambda 2': { label: 'Lambda 2', units: 'λ', min: 0.7, max: 1.3, decimals: 3, color: '#fb923c', category: 'afr' },

    // ==========================================================================
    // ENGINE PARAMETER CHANNELS
    // ==========================================================================
    'MAP kPa': { label: 'MAP', units: 'kPa', min: 0, max: 105, decimals: 1, color: '#06b6d4', category: 'engine' },
    'MAP': { label: 'MAP', units: 'kPa', min: 0, max: 105, decimals: 1, color: '#06b6d4', category: 'engine' },
    'TPS': { label: 'TPS', units: '%', min: 0, max: 100, decimals: 1, color: '#14b8a6', category: 'engine' },
    'IAT': { label: 'IAT', units: '°F', min: 0, max: 200, decimals: 0, color: '#f59e0b', category: 'engine' },
    'IAT F': { label: 'IAT', units: '°F', min: 0, max: 200, decimals: 0, color: '#f59e0b', category: 'engine' },
    'VBatt': { label: 'Battery', units: 'V', min: 11, max: 15, decimals: 1, color: '#eab308', category: 'engine' },
    'Voltage 2': { label: 'Voltage 2', units: 'V', min: 0, max: 5, decimals: 3, color: '#facc15', category: 'engine' },

    // ==========================================================================
    // SYSTEM/DIAGNOSTIC CHANNELS
    // ==========================================================================
    'Correction Factor': { label: 'Correction Factor', units: '', min: 0.9, max: 1.1, decimals: 3, color: '#facc15', category: 'misc' },
    'Gear Ratio': { label: 'Gear Ratio', units: '', min: 0, max: 10, decimals: 2, color: '#888', category: 'misc' },
    'Internal Temp 1': { label: 'Internal Temp 1', units: '°C', min: 20, max: 60, decimals: 2, color: '#f97316', category: 'misc' },
    'Internal Temp 2': { label: 'Internal Temp 2', units: '°C', min: 20, max: 60, decimals: 2, color: '#fb923c', category: 'misc' },
    'Link 0 Status': { label: 'Link 0 Status', units: '', min: 0, max: 1, decimals: 0, color: '#888', category: 'misc' },
    'Link 1 Status': { label: 'Link 1 Status', units: '', min: 0, max: 1, decimals: 0, color: '#888', category: 'misc' },
    'Sampling': { label: 'Sampling', units: '', min: 0, max: 1, decimals: 0, color: '#888', category: 'misc' },
    'Sampling Duration': { label: 'Sampling Duration', units: 's', min: 0, max: 1000, decimals: 1, color: '#888', category: 'misc' },
    'TCP RX kB/s': { label: 'TCP RX', units: 'kB/s', min: 0, max: 100, decimals: 1, color: '#888', category: 'misc' },
    'TCP TX kB/s': { label: 'TCP TX', units: 'kB/s', min: 0, max: 100, decimals: 1, color: '#888', category: 'misc' },
    'UDP RX kB/s': { label: 'UDP RX', units: 'kB/s', min: 0, max: 100, decimals: 1, color: '#888', category: 'misc' },
    'User Analog 3': { label: 'Analog 3', units: 'V', min: 0, max: 5, decimals: 2, color: '#facc15', category: 'misc' },
    'User Analog 4': { label: 'Analog 4', units: 'V', min: 0, max: 5, decimals: 2, color: '#facc15', category: 'misc' },
    'Inductive 1 Signal Strength': { label: 'Inductive 1 Signal', units: '', min: 0, max: 100, decimals: 0, color: '#888', category: 'misc' },
    'Inductive 2 Signal Strength': { label: 'Inductive 2 Signal', units: '', min: 0, max: 100, decimals: 0, color: '#888', category: 'misc' },
};

/**
 * Get channel configuration with flexible name matching.
 * Tries exact match first, then case-insensitive, then partial match.
 * Returns undefined if no match found.
 */
export function getChannelConfig(name: string): ChannelConfig | undefined {
    // Try exact match first
    if (JETDRIVE_CHANNEL_CONFIG[name]) {
        return JETDRIVE_CHANNEL_CONFIG[name];
    }

    // Try case-insensitive match
    const nameLower = name.toLowerCase();
    for (const [key, config] of Object.entries(JETDRIVE_CHANNEL_CONFIG)) {
        if (key.toLowerCase() === nameLower) {
            return config;
        }
    }

    // Try partial match (e.g., "RPM" matches "Digital RPM 1")
    for (const [key, config] of Object.entries(JETDRIVE_CHANNEL_CONFIG)) {
        const keyLower = key.toLowerCase();
        if (keyLower.includes(nameLower) || nameLower.includes(keyLower)) {
            return config;
        }
    }

    // No match found - return undefined to allow fallback logic
    return undefined;
}

/**
 * Get channel category from config or API data.
 * Returns 'misc' as default if not found.
 */
export function getChannelCategory(name: string, apiCategory?: string): ChannelCategory {
    // If API provides category, use it
    if (apiCategory && apiCategory in CHANNEL_CATEGORIES) {
        return apiCategory as ChannelCategory;
    }
    // Fall back to config
    const config = getChannelConfig(name);
    return config?.category ?? 'misc';
}

/**
 * Group channels by category for organized display.
 * Returns channels sorted by category order.
 */
export function getChannelsByCategory(
    channels: Record<string, JetDriveChannel>
): Record<ChannelCategory, Array<{ name: string; data: JetDriveChannel; config?: ChannelConfig }>> {
    const grouped: Record<ChannelCategory, Array<{ name: string; data: JetDriveChannel; config?: ChannelConfig }>> = {
        atmospheric: [],
        dyno: [],
        afr: [],
        engine: [],
        misc: [],
    };

    for (const [name, data] of Object.entries(channels)) {
        const config = getChannelConfig(name);
        const category = data.category ?? config?.category ?? 'misc';
        grouped[category].push({ name, data, config });
    }

    // Sort each category by label
    for (const cat of Object.keys(grouped) as ChannelCategory[]) {
        grouped[cat].sort((a, b) => {
            const labelA = a.config?.label ?? a.name;
            const labelB = b.config?.label ?? b.name;
            return labelA.localeCompare(labelB);
        });
    }

    return grouped;
}

const DEFAULT_OPTIONS: Required<UseJetDriveLiveOptions> = {
    apiUrl: 'http://127.0.0.1:5001/api/jetdrive',
    autoConnect: false,
    pollInterval: 1000,  // 1000ms = 1 update/sec - balances responsiveness with connection pool limits
    historyPublishIntervalMs: 300, // publish chart history at ~3Hz to reduce render/memory pressure
    maxHistoryPoints: 300,
    debug: false,
};

export function useJetDriveLive(options: UseJetDriveLiveOptions = {}): UseJetDriveLiveReturn {
    const opts = { ...DEFAULT_OPTIONS, ...options };

    // Connection state
    const [monitorConnected, setMonitorConnected] = useState(false);
    const [liveConnected, setLiveConnected] = useState(false);
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
    const historyRef = useRef<Record<string, { time: number; value: number }[]>>({});
    const lastHistoryPublishAtRef = useRef<number>(0);
    
    // Rate limit backoff state
    const backoffRef = useRef<number>(0); // Current backoff delay in ms
    const backoffUntilRef = useRef<number>(0); // Timestamp when backoff expires

    // UI sound state (debounced to avoid flapping/poll noise)
    const prevConnectedRef = useRef<boolean | null>(null);
    const lastStatusSoundAtRef = useRef<number>(0);
    const STATUS_SOUND_DEBOUNCE_MS = 3000;

    // Check monitor status
    const checkConnection = useCallback(async () => {
        // Skip if in backoff period
        if (Date.now() < backoffUntilRef.current) {
            return;
        }
        
        try {
            const res = await fetch(`${opts.apiUrl}/hardware/monitor/status`);
            
            // Handle rate limiting
            if (res.status === 429) {
                backoffRef.current = Math.min(backoffRef.current === 0 ? 500 : backoffRef.current * 2, 8000);
                backoffUntilRef.current = Date.now() + backoffRef.current;
                return;
            }
            
            // Success - reset backoff  
            backoffRef.current = 0;
            
            if (!res.ok) throw new Error('Monitor endpoint unavailable');

            const raw: unknown = await res.json();
            const data = isRecord(raw) ? raw : {};

            const connected = getBoolean(data.connected) ?? false;
            setMonitorConnected(connected);

            const providersRaw = data.providers;
            if (Array.isArray(providersRaw) && providersRaw.length > 0 && isRecord(providersRaw[0])) {
                const p0 = providersRaw[0];
                setProviderName(getString(p0.name));
                setChannelCount(getNumber(p0.channel_count) ?? 0);
            }

            setConnectionError(null);
        } catch (err) {
            setMonitorConnected(false);
            // More user-friendly error messages
            const errMsg = err instanceof Error ? err.message : 'Connection failed';
            if (errMsg.includes('Failed to fetch') || errMsg.includes('NetworkError')) {
                setConnectionError('Cannot reach JetDrive API. Check if the backend is running.');
            } else {
                setConnectionError(errMsg);
            }
        }
    }, [opts.apiUrl]);

    // Poll live data
    const pollLiveData = useCallback(async () => {
        // Skip polling if in backoff period
        if (Date.now() < backoffUntilRef.current) {
            return;
        }
        
        // #region agent log
        fetch('http://127.0.0.1:7243/ingest/78113279-9244-4ae6-8f9e-203bcc2c7404',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'useJetDriveLive.ts:286',message:'poll_initiated',data:{apiUrl:opts.apiUrl,backoff:backoffRef.current},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'H3'})}).catch(()=>{});
        // #endregion
        
        try {
            const res = await fetch(`${opts.apiUrl}/hardware/live/data`);
            
            // #region agent log
            fetch('http://127.0.0.1:7243/ingest/78113279-9244-4ae6-8f9e-203bcc2c7404',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'useJetDriveLive.ts:293',message:'fetch_response',data:{status:res.status,ok:res.ok,type:res.type,url:res.url},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'H5'})}).catch(()=>{});
            // #endregion
            
            // Handle rate limiting with exponential backoff
            if (res.status === 429) {
                // #region agent log
                fetch('http://127.0.0.1:7243/ingest/78113279-9244-4ae6-8f9e-203bcc2c7404',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'useJetDriveLive.ts:296',message:'429_received_frontend',data:{status:res.status,statusText:res.statusText,backoffCurrent:backoffRef.current,retryAfter:res.headers.get('Retry-After'),headers:Object.fromEntries(res.headers.entries())},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'H1,H4'})}).catch(()=>{});
                // #endregion
                // Exponential backoff: 500ms, 1s, 2s, 4s, max 8s
                backoffRef.current = Math.min(backoffRef.current === 0 ? 500 : backoffRef.current * 2, 8000);
                backoffUntilRef.current = Date.now() + backoffRef.current;
                if (opts.debug) {
                    console.warn(`[useJetDriveLive] Rate limited, backing off for ${backoffRef.current}ms`);
                }
                return;
            }
            
            // Success - reset backoff
            backoffRef.current = 0;
            
            if (!res.ok) throw new Error('Live data unavailable');

            const raw: unknown = await res.json();
            const data = isRecord(raw) ? raw : {};

            const capturing = getBoolean(data.capturing) ?? false;
            const simulated = getBoolean(data.simulated) ?? false;
            const simStateValue = getString(data.sim_state);

            setIsCapturing(capturing);
            setIsSimulated(simulated);
            setSimState(simStateValue);

            // If simulated, we're always "connected"
            if (simulated) {
                setLiveConnected(true);
            }

            const channelsRaw = isRecord(data.channels) ? data.channels : null;
            if (channelsRaw && Object.keys(channelsRaw).length > 0) {
                setLiveConnected(true);
                setConnectionError(null);
                // Convert to LiveLink-compatible format
                const newChannels: Record<string, JetDriveChannel> = {};
                const newSnapshot: JetDriveSnapshot = {
                    timestamp: Date.now(),
                    channels: {},
                    units: {},
                };

                for (const [name, chRaw] of Object.entries(channelsRaw)) {
                    if (!isRecord(chRaw)) continue;
                    const id = getNumber(chRaw.id) ?? undefined;
                    const value = getNumber(chRaw.value);
                    const timestamp = getNumber(chRaw.timestamp);
                    if (value === null || timestamp === null) continue;
                    
                    const config = getChannelConfig(name);
                    const apiCategory = getString(chRaw.category);
                    const category = getChannelCategory(name, apiCategory ?? undefined);

                    newChannels[name] = {
                        name,
                        value,
                        units: config?.units ?? getString(chRaw.units) ?? '',
                        timestamp,
                        id,
                        category,
                    };

                    newSnapshot.channels[name] = value;
                    newSnapshot.units[name] = config?.units ?? '';
                }
                if (opts.debug) {
                    // Keep any verbose logging behind a flag: logging inside a 20Hz polling loop
                    // can severely degrade UI performance.
                    console.debug('[useJetDriveLive] channels:', Object.keys(newChannels));
                }

                setChannels(newChannels);
                setSnapshot(newSnapshot);

                // Collect chart history every poll into a ref (cheap), but publish to React state
                // less frequently to reduce allocations and full-dashboard rerenders.
                const now = Date.now();
                const nextHistory = historyRef.current;

                for (const [name, ch] of Object.entries(newChannels)) {
                    const arr = nextHistory[name] ?? (nextHistory[name] = []);
                    arr.push({ time: now, value: ch.value });
                    if (arr.length > opts.maxHistoryPoints) {
                        // Drop the oldest points without allocating a new array
                        arr.splice(0, arr.length - opts.maxHistoryPoints);
                    }
                }
                const shouldPublish =
                    opts.historyPublishIntervalMs <= opts.pollInterval ||
                    now - lastHistoryPublishAtRef.current >= opts.historyPublishIntervalMs;
                if (shouldPublish) {
                    lastHistoryPublishAtRef.current = now;
                    // Clone shallowly to keep React state immutable and avoid downstream mutation surprises.
                    const published: Record<string, { time: number; value: number }[]> = {};
                    for (const [k, v] of Object.entries(nextHistory)) {
                        published[k] = v.slice();
                    }
                    setHistory(published);
                }
            } else {
                // If capturing but no channels, surface backend diagnostics (if provided).
                const statusObj = isRecord(data.status) ? data.status : null;
                const message = statusObj ? getString(statusObj.message) : null;
                if (capturing && message) {
                    setConnectionError(message);
                }
            }
        } catch {
            // Silent fail for polling
        }
    }, [opts.apiUrl, opts.debug, opts.historyPublishIntervalMs, opts.maxHistoryPoints, opts.pollInterval]);

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
            setLiveConnected(false);
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
        historyRef.current = {};
        lastHistoryPublishAtRef.current = 0;
    }, []);

    // Clear all channels (removes stale/old channel data)
    const clearChannels = useCallback(async () => {
        // Clear local state
        setChannels({});
        setHistory({});
        historyRef.current = {};
        lastHistoryPublishAtRef.current = 0;
        setSnapshot(null);
        setChannelCount(0);
        
        // Also reset backend queue to clear any cached channel data
        try {
            await fetch(`${opts.apiUrl}/queue/reset`, { method: 'POST' });
        } catch {
            // Ignore errors - local clear is the important part
        }
    }, [opts.apiUrl]);

    // Initial connection check
    useEffect(() => {
        void checkConnection();
    }, [checkConnection]);

    // Polling effect
    useEffect(() => {
        // Always poll for status
        const statusInterval = setInterval(checkConnection, 5000);

        // Poll live data when capturing
        if (isCapturing) {
            void pollLiveData(); // Immediate poll
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
        if (opts.autoConnect && monitorConnected && !isCapturing) {
            void startCapture().catch(() => undefined);
        }
    }, [opts.autoConnect, monitorConnected, isCapturing, startCapture]);

    // Status sounds on connect/disconnect transitions
    useEffect(() => {
        const isConnectedNow = monitorConnected || liveConnected;
        const prev = prevConnectedRef.current;

        // Ignore first render (no initial chirp)
        if (prev === null) {
            prevConnectedRef.current = isConnectedNow;
            return;
        }

        if (prev !== isConnectedNow) {
            const now = Date.now();
            if (now - lastStatusSoundAtRef.current > STATUS_SOUND_DEBOUNCE_MS) {
                playUiSound(isConnectedNow ? 'connect' : 'disconnect');
                lastStatusSoundAtRef.current = now;
            }
            prevConnectedRef.current = isConnectedNow;
        }
    }, [monitorConnected, liveConnected]);

    return {
        isConnected: monitorConnected || liveConnected,
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
        clearChannels,
    };
}

export default useJetDriveLive;

