/**
 * useJetDriveLive - React hook for real-time JetDrive data
 * 
 * Provides the same interface as useLiveLink but connects to JetDrive
 * hardware via the REST API. This allows reusing the LiveLink gauge
 * and chart components with real dyno data.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { playUiSound } from '@/lib/ui-sounds';

// Shared capability flag across all hook instances on the page.
let globalDrainEndpointUnavailable = false;
let globalDrainBackoffMs = 0;
let globalDrainBackoffUntil = 0;

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

// NOTE: LC-1/LC-2 voltage-to-AFR rescaling used to live here as
// `isLc2VoltageAfrChannel` + `normalizeChannelValue`. It has been moved
// to `api/services/jetdrive/wideband_rescale.py` (server-side) and is
// applied at the ingest boundary in `_live_capture_loop`. Doing physics
// in a React hook was the root cause of the "volts as AFR" corrections
// bug and is now forbidden by `.cursor/rules/no-physics-in-frontend.mdc`.
// The frontend receives AFR values directly from the backend and must
// only render them.

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
    /** Unique key: "0xPPPP:CC:Name" format */
    key: string;
    /** Display name (clean, human-readable) */
    name: string;
    value: number;
    units: string;
    timestamp: number;
    /** Provider ID (hex) */
    providerId?: number;
    /** Channel ID within provider */
    id?: number;
    category?: ChannelCategory;
}

/**
 * Parse a channel key into its components.
 * Key format: "0xPPPP:CC:Name" where PPPP is provider ID (hex), CC is channel ID.
 * 
 * @returns { providerId, channelId, name } or null if invalid format
 */
export function parseChannelKey(key: string): { providerId: number; channelId: number; name: string } | null {
    const match = key.match(/^0x([0-9A-Fa-f]{4}):(\d+):(.+)$/);
    if (match) {
        return {
            providerId: parseInt(match[1], 16),
            channelId: parseInt(match[2], 10),
            name: match[3],
        };
    }
    return null;
}

/**
 * Create a channel key from components.
 */
export function createChannelKey(providerId: number, channelId: number, name: string): string {
    return `0x${providerId.toString(16).toUpperCase().padStart(4, '0')}:${channelId}:${name}`;
}

export interface JetDriveSnapshot {
    timestamp: number;
    channels: Record<string, number>;
    units: Record<string, string>;
}

export type JetDriveDataSource = 'simulator' | 'hardware' | 'none';

/** A raw sample entry from the /live/drain endpoint.
 *  Each entry represents one channel value at one point in time.
 *  Use consumeDrainedSamples() to get all samples since the last call. */
export interface DrainedSample {
    name: string;
    value: number;
    timestamp: number;
    category?: string;
    units?: string;
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
    /** Prefer Server-Sent Events over polling when available (default: true).
     *  SSE reduces latency and server load compared to polling.
     *  Falls back to polling if SSE connection fails. */
    useSse?: boolean;
    /** When true, page is in simulator mode - hook will poll live data and keep simulator data separate from hardware */
    isSimulatorActive?: boolean;
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
    /** Active data source: simulator, hardware, or none (no live data) */
    dataSource: JetDriveDataSource;

    // Data - compatible with LiveLink components (always the active source: simulator or hardware)
    channels: Record<string, JetDriveChannel>;
    snapshot: JetDriveSnapshot | null;
    history: Record<string, { time: number; value: number }[]>;

    // Actions
    startCapture: () => Promise<void>;
    stopCapture: () => Promise<void>;
    getChannelValue: (channel: string) => number | null;
    clearHistory: () => void;
    clearChannels: () => Promise<void>;

    /** Consume all drained samples since last call. Returns array of raw sample
     *  entries (each has name, value, timestamp). Clears the internal buffer.
     *  Use this for VE cell hit accumulation to get every sample, not just the
     *  latest snapshot value. Backed by the /hardware/live/drain endpoint. */
    consumeDrainedSamples: () => DrainedSample[];
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
    'ECT': { label: 'ECT', units: '°F', min: 100, max: 280, decimals: 0, color: '#ef4444', category: 'engine', warning: 230, critical: 250 },
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
 * 
 * Channel keys use the format "0xPPPP:CC:Name" where:
 * - PPPP = Provider ID (hex)
 * - CC = Channel ID within provider
 * - Name = Human-readable channel name
 * 
 * This ensures channels from different providers don't collide.
 */
export function getChannelsByCategory(
    channels: Record<string, JetDriveChannel>
): Record<ChannelCategory, Array<{ key: string; name: string; data: JetDriveChannel; config?: ChannelConfig }>> {
    const grouped: Record<ChannelCategory, Array<{ key: string; name: string; data: JetDriveChannel; config?: ChannelConfig }>> = {
        atmospheric: [],
        dyno: [],
        afr: [],
        engine: [],
        misc: [],
    };

    for (const [key, data] of Object.entries(channels)) {
        const displayName = data.name;
        const config = getChannelConfig(displayName);
        const category = data.category ?? config?.category ?? 'misc';
        grouped[category].push({ key, name: displayName, data, config });
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

const DEFAULT_OPTIONS: Required<Omit<UseJetDriveLiveOptions, 'isSimulatorActive'>> & { isSimulatorActive?: boolean } = {
    apiUrl: 'http://127.0.0.1:5001/api/jetdrive',
    autoConnect: false,
    pollInterval: 250,  // 250ms = 4Hz polling fallback; SSE is preferred (event-driven ~20Hz)
    historyPublishIntervalMs: 100, // publish chart history at ~10Hz for responsive gauges
    maxHistoryPoints: 300,
    debug: false,
    useSse: true,
    isSimulatorActive: false,
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

    // Data state - separate simulator vs hardware to prevent cross-contamination
    const [channels, setChannels] = useState<Record<string, JetDriveChannel>>({});
    const [simulatorChannels, setSimulatorChannels] = useState<Record<string, JetDriveChannel>>({});
    const [dataSource, setDataSource] = useState<JetDriveDataSource>('none');
    const [snapshot, setSnapshot] = useState<JetDriveSnapshot | null>(null);
    const [history, setHistory] = useState<Record<string, { time: number; value: number }[]>>({});

    // Refs
    const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const historyRef = useRef<Record<string, { time: number; value: number }[]>>({});
    const lastHistoryPublishAtRef = useRef<number>(0);
    const prevSimulatedRef = useRef<boolean | null>(null);
    const lastUpdateTsRef = useRef<number | null>(null);
    
    // Rate limit backoff state
    const backoffRef = useRef<number>(0); // Current backoff delay in ms
    const backoffUntilRef = useRef<number>(0); // Timestamp when backoff expires

    // Drain buffer: accumulates raw samples from /live/drain for VE hit accumulation.
    // consumeDrainedSamples() returns the buffer contents and clears it.
    const drainBufferRef = useRef<DrainedSample[]>([]);
    const drainIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const drainEndpointUnavailableRef = useRef(false);
    const drainBackoffMsRef = useRef(0);
    const drainBackoffUntilRef = useRef(0);

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

    // Shared payload processor for polling and SSE
    const processLivePayload = useCallback((raw: unknown) => {
        const data = isRecord(raw) ? raw : {};

        const capturing = getBoolean(data.capturing) ?? false;
        const simulated = getBoolean(data.simulated) ?? false;
        const simStateValue = getString(data.sim_state);
        const lastUpdateTs = getNumber(data.last_update_ts);

        setIsCapturing(capturing);
        setIsSimulated(simulated);
        setSimState(simStateValue);

        // If simulated, we're always "connected"
        if (simulated) {
            setLiveConnected(true);
        }

        // Detect mode transition to clear the other source and prevent cross-contamination
        const prevSimulated = prevSimulatedRef.current;
        if (prevSimulated === false && simulated) {
            setChannels({});
            historyRef.current = {};
            lastHistoryPublishAtRef.current = 0;
            lastUpdateTsRef.current = null;
        } else if (prevSimulated === true && !simulated) {
            setSimulatorChannels({});
            historyRef.current = {};
            lastHistoryPublishAtRef.current = 0;
            lastUpdateTsRef.current = null;
        }
        prevSimulatedRef.current = simulated;

        // Skip heavy allocations if backend indicates nothing changed since last poll.
        // (This matters when the UI is polling but capture is idle/stale.)
        if (!simulated && lastUpdateTs !== null) {
            const prev = lastUpdateTsRef.current;
            if (prev !== null && prev === lastUpdateTs) {
                return;
            }
            lastUpdateTsRef.current = lastUpdateTs;
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

            for (const [key, chRaw] of Object.entries(channelsRaw)) {
                if (!isRecord(chRaw)) continue;
                const rawValue = getNumber(chRaw.value);
                const timestamp = getNumber(chRaw.timestamp);
                if (rawValue === null || timestamp === null) continue;
                
                // Parse the channel key (format: "0xPPPP:CC:Name")
                // or fall back to legacy format for backwards compatibility
                const parsed = parseChannelKey(key);
                const channelKey = getString(chRaw.key) ?? key;
                const providerId = getNumber(chRaw.provider_id) ?? parsed?.providerId;
                const channelId = getNumber(chRaw.id) ?? parsed?.channelId;
                const displayName = getString(chRaw.name) ?? parsed?.name ?? key;
                const value = rawValue;
                
                const config = getChannelConfig(displayName);
                const apiCategory = getString(chRaw.category);
                const category = getChannelCategory(displayName, apiCategory ?? undefined);
                
                // Store by DISPLAY NAME (not composite key) so dashboard lookups work.
                // The composite key is retained inside the object for debugging.
                newChannels[displayName] = {
                    key: channelKey,
                    name: displayName,
                    value,
                    units: config?.units ?? getString(chRaw.units) ?? '',
                    timestamp,
                    providerId,
                    id: channelId,
                    category,
                };

                newSnapshot.channels[displayName] = value;
                newSnapshot.units[displayName] = config?.units ?? '';
            }
            if (opts.debug) {
                // Keep any verbose logging behind a flag: logging inside a 20Hz polling loop
                // can severely degrade UI performance.
                console.debug('[useJetDriveLive] channels:', Object.keys(newChannels));
            }

            if (simulated) {
                setSimulatorChannels(newChannels);
                setDataSource('simulator');
            } else {
                setChannels(newChannels);
                setDataSource('hardware');
            }
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
            setDataSource('none');
            // If capturing but no channels, surface backend diagnostics (if provided).
            const statusObj = isRecord(data.status) ? data.status : null;
            const message = statusObj ? getString(statusObj.message) : null;
            if (capturing && message) {
                setConnectionError(message);
            }
        }
    }, [opts.debug, opts.historyPublishIntervalMs, opts.maxHistoryPoints, opts.pollInterval]);

    // Poll live data
    const pollLiveData = useCallback(async () => {
        // Skip polling if in backoff period
        if (Date.now() < backoffUntilRef.current) {
            return;
        }
        
        try {
            const res = await fetch(`${opts.apiUrl}/hardware/live/data`);
            
            // Handle rate limiting with exponential backoff
            if (res.status === 429) {
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
            processLivePayload(raw);
        } catch {
            // Silent fail for polling
        }
    }, [opts.apiUrl, opts.debug, processLivePayload]);

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

    // Active channels: simulator when dataSource is simulator, otherwise hardware
    const activeChannels = dataSource === 'simulator' ? simulatorChannels : channels;

    // Get single channel value (from active source)
    const getChannelValue = useCallback((channel: string): number | null => {
        return activeChannels[channel]?.value ?? null;
    }, [activeChannels]);

    // Clear history
    const clearHistory = useCallback(() => {
        setHistory({});
        historyRef.current = {};
        lastHistoryPublishAtRef.current = 0;
    }, []);

    // Clear all channels (both simulator and hardware) - use when switching modes
    const clearChannels = useCallback(async () => {
        setChannels({});
        setSimulatorChannels({});
        setDataSource('none');
        setHistory({});
        historyRef.current = {};
        lastHistoryPublishAtRef.current = 0;
        lastUpdateTsRef.current = null;
        setSnapshot(null);
        setChannelCount(0);
        prevSimulatedRef.current = null;
        
        try {
            await fetch(`${opts.apiUrl}/queue/reset`, { method: 'POST' });
        } catch {
            // Ignore errors - local clear is the important part
        }
    }, [opts.apiUrl]);

    // Initial connection check - only if autoConnect is enabled
    useEffect(() => {
        if (opts.autoConnect) {
            void checkConnection();
        }
    }, [checkConnection, opts.autoConnect]);

    // Polling effect - poll when real capture OR simulator is active (separate modes)
    const shouldPollLive = isCapturing || opts.isSimulatorActive;
    useEffect(() => {
        // Only poll for status when autoConnect is enabled or we're actively using the feature
        const shouldPollStatus = opts.autoConnect || shouldPollLive;
        let statusInterval: NodeJS.Timeout | null = null;
        
        if (shouldPollStatus) {
            statusInterval = setInterval(checkConnection, 5000);
        }

        if (shouldPollLive && !opts.useSse) {
            void pollLiveData(); // Immediate poll
            pollIntervalRef.current = setInterval(pollLiveData, opts.pollInterval);
        }

        return () => {
            if (statusInterval) {
                clearInterval(statusInterval);
            }
            if (pollIntervalRef.current) {
                clearInterval(pollIntervalRef.current);
            }
        };
    }, [shouldPollLive, checkConnection, pollLiveData, opts.pollInterval, opts.autoConnect, opts.useSse]);

    // SSE effect (optional): prefer server push over polling
    useEffect(() => {
        if (!shouldPollLive || !opts.useSse) return;

        const es = new EventSource(`${opts.apiUrl}/hardware/live/stream`);
        es.onmessage = (evt) => {
            try {
                const parsed = JSON.parse(evt.data) as unknown;
                processLivePayload(parsed);
            } catch {
                // ignore malformed events
            }
        };
        es.onerror = () => {
            // EventSource auto-reconnects; keep this non-fatal
        };

        return () => {
            es.close();
        };
    }, [shouldPollLive, opts.useSse, opts.apiUrl, processLivePayload]);

    // Drain polling: fetch /live/drain every 100ms to accumulate ALL samples
    // for VE cell hit counting. Runs independently of SSE (which serves gauges).
    useEffect(() => {
        if (!shouldPollLive) {
            // Clear buffer when not capturing
            drainBufferRef.current = [];
            drainEndpointUnavailableRef.current = false;
            drainBackoffMsRef.current = 0;
            drainBackoffUntilRef.current = 0;
            return;
        }

        const pollDrain = async () => {
            if (drainEndpointUnavailableRef.current || globalDrainEndpointUnavailable) return;
            if (Date.now() < drainBackoffUntilRef.current || Date.now() < globalDrainBackoffUntil) return;
            try {
                const res = await fetch(`${opts.apiUrl}/hardware/live/drain`);
                if (!res.ok) {
                    // Some backends don't expose /live/drain. Disable polling to avoid console spam.
                    if (res.status === 404) {
                        drainEndpointUnavailableRef.current = true;
                        globalDrainEndpointUnavailable = true;
                        if (opts.debug) {
                            console.warn('[useJetDriveLive] /hardware/live/drain not available (404); disabling drain polling.');
                        }
                    }
                    // Apply endpoint-level rate-limit backoff to prevent hammering.
                    if (res.status === 429) {
                        const nextBackoff = Math.min(
                            drainBackoffMsRef.current === 0 ? 500 : drainBackoffMsRef.current * 2,
                            15000
                        );
                        const backoffUntil = Date.now() + nextBackoff;
                        drainBackoffMsRef.current = nextBackoff;
                        drainBackoffUntilRef.current = backoffUntil;
                        globalDrainBackoffMs = Math.max(globalDrainBackoffMs, nextBackoff);
                        globalDrainBackoffUntil = Math.max(globalDrainBackoffUntil, backoffUntil);
                        if (opts.debug) {
                            console.warn(
                                `[useJetDriveLive] /hardware/live/drain rate-limited; backing off ${nextBackoff}ms.`
                            );
                        }
                    }
                    return;
                }

                // Success: clear drain backoff state.
                drainBackoffMsRef.current = 0;
                drainBackoffUntilRef.current = 0;
                globalDrainBackoffMs = 0;
                globalDrainBackoffUntil = 0;
                const raw: unknown = await res.json();
                if (!isRecord(raw)) return;

                const samples = raw.samples;
                if (!Array.isArray(samples) || samples.length === 0) return;

                // Append parsed samples to buffer
                for (const s of samples) {
                    if (!isRecord(s)) continue;
                    const name = getString(s.name);
                    const rawValue = getNumber(s.value);
                    const timestamp = getNumber(s.timestamp);
                    if (name === null || rawValue === null || timestamp === null) continue;
                    const value = rawValue;
                    drainBufferRef.current.push({
                        name,
                        value,
                        timestamp,
                        category: getString(s.category) ?? undefined,
                        units: getString(s.units) ?? undefined,
                    });
                }
            } catch {
                // Silent fail -- drain is best-effort
            }
        };

        // Start polling drain immediately, then every 100ms (aligned with 50ms
        // aggregation window; 10Hz drain ≈ 2 polls per window = minimal loss)
        void pollDrain();
        drainIntervalRef.current = setInterval(pollDrain, 100);

        return () => {
            if (drainIntervalRef.current) {
                clearInterval(drainIntervalRef.current);
                drainIntervalRef.current = null;
            }
        };
    }, [shouldPollLive, opts.apiUrl]);

    // consumeDrainedSamples: returns all accumulated samples and clears the buffer.
    // Called by VE accumulation consumers (e.g., VEHeatmapPanel) at their own pace.
    const consumeDrainedSamples = useCallback((): DrainedSample[] => {
        const samples = drainBufferRef.current;
        if (samples.length === 0) return [];
        drainBufferRef.current = [];
        return samples;
    }, []);

    // Auto-connect: when autoConnect is enabled, aggressively keep capture
    // running so live data (and the VE heatmap that consumes it) stays
    // populated whenever the user is on the Command Center — not only while
    // a pull is actively recording. The backend handles "no providers" by
    // exiting the capture thread and clearing `capturing`, so this effect
    // will retry on the next tick once `isCapturing` flips back to false.
    useEffect(() => {
        if (!opts.autoConnect || isCapturing) return;

        // Fire immediately on mount / whenever capture stops, then retry
        // periodically so transient discovery failures self-heal.
        let cancelled = false;
        const attemptStart = () => {
            if (cancelled || isCapturing) return;
            void startCapture().catch(() => undefined);
        };
        attemptStart();
        const retry = setInterval(attemptStart, 5000);

        return () => {
            cancelled = true;
            clearInterval(retry);
        };
    }, [opts.autoConnect, isCapturing, startCapture]);

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
        dataSource,
        channels: activeChannels,
        snapshot,
        history,
        startCapture,
        stopCapture,
        getChannelValue,
        clearHistory,
        clearChannels,
        consumeDrainedSamples,
    };
}

export default useJetDriveLive;

