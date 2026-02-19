/**
 * useInnovateLive - React hook for real-time Innovate DLG-1/LC-2 wideband AFR data
 * 
 * Connects to the DLG-1 via the backend API and provides real-time AFR/Lambda
 * readings for both channels. Designed to integrate with the JetDrive dashboard.
 */

import { useState, useEffect, useCallback, useRef } from 'react';

export interface InnovateSample {
    afr: number;
    lambda: number;
    timestamp: number;
}

export interface InnovateChannelData {
    channel: number;
    name: string;
    afr: number;
    lambda: number;
    timestamp: number;
    connected: boolean;
}

export interface UseInnovateLiveOptions {
    /** API base URL (default: http://127.0.0.1:5001/api/jetdrive) */
    apiUrl?: string;
    /** Poll interval in ms (default: 250 for ~4Hz update) */
    pollInterval?: number;
    /** Max history points for charts (default: 300 = 75 seconds at 4Hz) */
    maxHistoryPoints?: number;
    /** Auto-connect on mount */
    autoConnect?: boolean;
    /** COM port for auto-connect */
    defaultPort?: string;
}

export interface UseInnovateLiveReturn {
    // Connection state
    isConnected: boolean;
    isStreaming: boolean;
    port: string | null;
    deviceType: string | null;
    error: string | null;
    
    // Available ports
    availablePorts: { port: string; description: string }[];
    
    // Channel data
    channelA: InnovateChannelData | null;  // Sensor A (Channel 1)
    channelB: InnovateChannelData | null;  // Sensor B (Channel 2)
    
    // History for charts
    historyA: { time: number; afr: number; lambda: number }[];
    historyB: { time: number; afr: number; lambda: number }[];
    
    // Actions
    connect: (port: string, deviceType?: string) => Promise<boolean>;
    disconnect: () => Promise<void>;
    refreshPorts: () => Promise<void>;
    clearHistory: () => void;
}

export function useInnovateLive(options: UseInnovateLiveOptions = {}): UseInnovateLiveReturn {
    const {
        apiUrl = 'http://127.0.0.1:5001/api/jetdrive',
        pollInterval = 250,
        maxHistoryPoints = 300,
        autoConnect = false,
        defaultPort = 'COM5',
    } = options;

    // Connection state
    const [isConnected, setIsConnected] = useState(false);
    const [isStreaming, setIsStreaming] = useState(false);
    const [port, setPort] = useState<string | null>(null);
    const [deviceType, setDeviceType] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    
    // Available ports
    const [availablePorts, setAvailablePorts] = useState<{ port: string; description: string }[]>([]);
    
    // Channel data
    const [channelA, setChannelA] = useState<InnovateChannelData | null>(null);
    const [channelB, setChannelB] = useState<InnovateChannelData | null>(null);
    
    // History for charts
    const [historyA, setHistoryA] = useState<{ time: number; afr: number; lambda: number }[]>([]);
    const [historyB, setHistoryB] = useState<{ time: number; afr: number; lambda: number }[]>([]);
    
    // Refs for polling
    const pollRef = useRef<NodeJS.Timeout | null>(null);
    const startTimeRef = useRef<number>(Date.now());

    // Refresh available ports
    const refreshPorts = useCallback(async () => {
        try {
            const response = await fetch(`${apiUrl}/innovate/ports`);
            const data = await response.json();
            
            if (data.success && data.ports) {
                setAvailablePorts(data.ports);
            }
        } catch (err) {
            console.error('Failed to fetch ports:', err);
        }
    }, [apiUrl]);

    // Connect to device
    const connect = useCallback(async (portName: string, devType: string = 'DLG-1'): Promise<boolean> => {
        setError(null);
        
        try {
            const response = await fetch(`${apiUrl}/innovate/connect`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ port: portName, device_type: devType }),
            });
            
            const data = await response.json();
            
            if (data.success) {
                setIsConnected(true);
                setPort(portName);
                setDeviceType(devType);
                startTimeRef.current = Date.now();
                return true;
            } else {
                setError(data.error || 'Connection failed');
                return false;
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Connection error');
            return false;
        }
    }, [apiUrl]);

    // Disconnect from device
    const disconnect = useCallback(async () => {
        try {
            await fetch(`${apiUrl}/innovate/disconnect`, { method: 'POST' });
        } catch (err) {
            console.error('Disconnect error:', err);
        }
        
        setIsConnected(false);
        setIsStreaming(false);
        setPort(null);
        setChannelA(null);
        setChannelB(null);
    }, [apiUrl]);

    // Clear history
    const clearHistory = useCallback(() => {
        setHistoryA([]);
        setHistoryB([]);
        startTimeRef.current = Date.now();
    }, []);

    // Poll for status updates
    const pollStatus = useCallback(async () => {
        if (!isConnected) return;
        
        try {
            const response = await fetch(`${apiUrl}/innovate/status`);
            const data = await response.json();
            
            if (data.success && data.connected) {
                setIsStreaming(data.streaming);
                
                const now = Date.now();
                const relativeTime = (now - startTimeRef.current) / 1000;
                
                // Update Channel A (Channel 1)
                if (data.samples?.channel_1) {
                    const sample = data.samples.channel_1;
                    const channelData: InnovateChannelData = {
                        channel: 1,
                        name: 'Sensor A',
                        afr: sample.afr,
                        lambda: sample.lambda,
                        timestamp: sample.timestamp,
                        connected: sample.afr > 5 && sample.afr < 25, // Valid AFR range
                    };
                    setChannelA(channelData);
                    
                    // Add to history if valid
                    if (channelData.connected) {
                        setHistoryA(prev => {
                            const newHistory = [...prev, { time: relativeTime, afr: sample.afr, lambda: sample.lambda }];
                            return newHistory.slice(-maxHistoryPoints);
                        });
                    }
                }
                
                // Update Channel B (Channel 2)
                if (data.samples?.channel_2) {
                    const sample = data.samples.channel_2;
                    const channelData: InnovateChannelData = {
                        channel: 2,
                        name: 'Sensor B',
                        afr: sample.afr,
                        lambda: sample.lambda,
                        timestamp: sample.timestamp,
                        connected: sample.afr > 5 && sample.afr < 25, // Valid AFR range
                    };
                    setChannelB(channelData);
                    
                    // Add to history if valid
                    if (channelData.connected) {
                        setHistoryB(prev => {
                            const newHistory = [...prev, { time: relativeTime, afr: sample.afr, lambda: sample.lambda }];
                            return newHistory.slice(-maxHistoryPoints);
                        });
                    }
                }
            } else if (!data.connected) {
                setIsConnected(false);
                setIsStreaming(false);
            }
        } catch (err) {
            console.error('Poll error:', err);
        }
    }, [apiUrl, isConnected, maxHistoryPoints]);

    // Start/stop polling
    useEffect(() => {
        if (isConnected) {
            // Initial poll
            pollStatus();
            
            // Start interval
            pollRef.current = setInterval(pollStatus, pollInterval);
            
            return () => {
                if (pollRef.current) {
                    clearInterval(pollRef.current);
                    pollRef.current = null;
                }
            };
        }
    }, [isConnected, pollStatus, pollInterval]);

    // Auto-connect on mount
    useEffect(() => {
        refreshPorts();
        
        if (autoConnect && defaultPort) {
            connect(defaultPort, 'DLG-1');
        }
        
        return () => {
            if (pollRef.current) {
                clearInterval(pollRef.current);
            }
        };
    }, []);  // Only on mount

    return {
        isConnected,
        isStreaming,
        port,
        deviceType,
        error,
        availablePorts,
        channelA,
        channelB,
        historyA,
        historyB,
        connect,
        disconnect,
        refreshPorts,
        clearHistory,
    };
}

// Default export
export default useInnovateLive;

