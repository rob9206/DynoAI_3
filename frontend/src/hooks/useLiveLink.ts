/**
 * useLiveLink - React hook for real-time dyno data streaming via WebSocket
 * 
 * Connects to the DynoAI LiveLink WebSocket server and provides:
 * - Real-time channel data updates
 * - Connection status management
 * - Auto-reconnection handling
 * - Channel subscription filtering
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { io, Socket } from 'socket.io-client';

// Types for LiveLink data
export interface LiveLinkChannel {
  name: string;
  value: number;
  units: string;
  timestamp: number;
}

export interface LiveLinkSnapshot {
  timestamp: number;
  channels: Record<string, number>;
  units: Record<string, string>;
}

export interface LiveLinkStatus {
  connected: boolean;
  mode: 'wcf' | 'poll' | 'simulation' | null;
  clients: number;
}

export interface UseLiveLinkOptions {
  /** WebSocket server URL (default: http://127.0.0.1:5003) */
  serverUrl?: string;
  /** Namespace for socket.io (default: /livelink) */
  namespace?: string;
  /** Auto-connect on mount (default: false) */
  autoConnect?: boolean;
  /** Connection mode (default: simulation) */
  mode?: 'wcf' | 'poll' | 'simulation' | 'auto';
  /** Channels to subscribe to (empty = all) */
  channels?: string[];
  /** Update interval in ms (default: 100) */
  updateInterval?: number;
  /** Max reconnection attempts (default: 5) */
  maxReconnectAttempts?: number;
}

export interface UseLiveLinkReturn {
  // Connection state
  isConnected: boolean;
  isConnecting: boolean;
  connectionError: string | null;
  mode: string | null;

  // Data
  channels: Record<string, LiveLinkChannel>;
  snapshot: LiveLinkSnapshot | null;

  // History for charts (last 60 seconds at 10Hz = 600 points)
  history: Record<string, { time: number; value: number }[]>;

  // Actions
  connect: () => void;
  disconnect: () => void;
  requestSnapshot: () => Promise<LiveLinkSnapshot | null>;
  getChannelValue: (channel: string) => number | null;
  subscribeChannels: (channels: string[]) => void;
  clearHistory: () => void;
}

const DEFAULT_OPTIONS: Required<UseLiveLinkOptions> = {
  serverUrl: 'http://127.0.0.1:5003',
  namespace: '/livelink',
  autoConnect: false,
  mode: 'simulation',
  channels: [],
  updateInterval: 100,
  maxReconnectAttempts: 5,
};

const MAX_HISTORY_POINTS = 600; // 60 seconds at 10Hz

export function useLiveLink(options: UseLiveLinkOptions = {}): UseLiveLinkReturn {
  const opts = { ...DEFAULT_OPTIONS, ...options };

  // Socket reference
  const socketRef = useRef<Socket | null>(null);
  const reconnectAttemptsRef = useRef(0);

  // Connection state
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [mode, setMode] = useState<string | null>(null);

  // Data state
  const [channels, setChannels] = useState<Record<string, LiveLinkChannel>>({});
  const [snapshot, setSnapshot] = useState<LiveLinkSnapshot | null>(null);
  const [history, setHistory] = useState<Record<string, { time: number; value: number }[]>>({});

  // Update channel data and history
  const updateChannel = useCallback((data: { channel: string; value: number; units?: string; timestamp?: number }) => {
    const timestamp = data.timestamp || Date.now();

    setChannels(prev => ({
      ...prev,
      [data.channel]: {
        name: data.channel,
        value: data.value,
        units: data.units || prev[data.channel]?.units || '',
        timestamp,
      },
    }));

    // Update history for charts with circular buffer for better memory management
    setHistory(prev => {
      const channelHistory = prev[data.channel] || [];
      const newPoint = { time: timestamp, value: data.value };

      // Only keep MAX_HISTORY_POINTS, drop oldest
      if (channelHistory.length >= MAX_HISTORY_POINTS) {
        const updated = [...channelHistory.slice(1), newPoint];
        return { ...prev, [data.channel]: updated };
      }

      return { ...prev, [data.channel]: [...channelHistory, newPoint] };
    });
  }, []);

  // Connect to WebSocket server
  const connect = useCallback(() => {
    if (socketRef.current?.connected) {
      console.log('[LiveLink] Already connected');
      return;
    }

    setIsConnecting(true);
    setConnectionError(null);

    const socket = io(opts.serverUrl + opts.namespace, {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: opts.maxReconnectAttempts,
      reconnectionDelay: 1000,
    });

    socketRef.current = socket;

    socket.on('connect', () => {
      console.log('[LiveLink] Connected to WebSocket');
      setIsConnected(true);
      setIsConnecting(false);
      setConnectionError(null);
      reconnectAttemptsRef.current = 0;

      // Start LiveLink streaming
      socket.emit('start', { mode: opts.mode }, (response: { success: boolean; error?: string }) => {
        if (response.success) {
          console.log('[LiveLink] Streaming started');
        } else {
          console.error('[LiveLink] Failed to start:', response.error);
          setConnectionError(response.error || 'Failed to start LiveLink');
        }
      });

      // Subscribe to specific channels if provided
      if (opts.channels.length > 0) {
        socket.emit('subscribe', { channels: opts.channels });
      }
    });

    socket.on('disconnect', (reason) => {
      console.log('[LiveLink] Disconnected:', reason);
      setIsConnected(false);
      setMode(null);
    });

    socket.on('connect_error', (error) => {
      console.error('[LiveLink] Connection error:', error.message);
      setIsConnecting(false);
      setConnectionError(error.message);
      reconnectAttemptsRef.current++;
    });

    socket.on('status', (data: LiveLinkStatus) => {
      setMode(data.mode);
    });

    socket.on('data', (data: { channel: string; value: number; units?: string; timestamp?: number }) => {
      updateChannel(data);
    });

    socket.on('snapshot', (data: LiveLinkSnapshot) => {
      setSnapshot(data);

      // Update all channels from snapshot
      Object.entries(data.channels).forEach(([channel, value]) => {
        updateChannel({
          channel,
          value,
          units: data.units[channel],
          timestamp: data.timestamp * 1000,
        });
      });
    });
  }, [opts.serverUrl, opts.namespace, opts.mode, opts.channels, opts.maxReconnectAttempts, updateChannel]);

  // Disconnect from WebSocket server
  const disconnect = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.emit('stop');
      socketRef.current.disconnect();
      socketRef.current = null;
    }
    setIsConnected(false);
    setIsConnecting(false);
    setMode(null);
  }, []);

  // Request current snapshot
  const requestSnapshot = useCallback(async (): Promise<LiveLinkSnapshot | null> => {
    return new Promise((resolve) => {
      if (!socketRef.current?.connected) {
        resolve(null);
        return;
      }

      socketRef.current.emit('get_snapshot', {}, (response: { success: boolean; timestamp?: number; channels?: Record<string, number>; units?: Record<string, string>; error?: string }) => {
        if (response.success && response.timestamp && response.channels && response.units) {
          const snapshot: LiveLinkSnapshot = {
            timestamp: response.timestamp,
            channels: response.channels,
            units: response.units,
          };
          setSnapshot(snapshot);

          // Also update individual channels
          Object.entries(response.channels).forEach(([channel, value]) => {
            updateChannel({
              channel,
              value,
              units: response.units![channel],
              timestamp: response.timestamp! * 1000,
            });
          });

          resolve(snapshot);
        } else {
          resolve(null);
        }
      });
    });
  }, [updateChannel]);

  // Get specific channel value
  const getChannelValue = useCallback((channel: string): number | null => {
    return channels[channel]?.value ?? null;
  }, [channels]);

  // Subscribe to specific channels
  const subscribeChannels = useCallback((channelList: string[]) => {
    if (socketRef.current?.connected) {
      socketRef.current.emit('subscribe', { channels: channelList });
    }
  }, []);

  // Clear history data
  const clearHistory = useCallback(() => {
    setHistory({});
  }, []);

  // Periodic cleanup of old history data for memory efficiency
  useEffect(() => {
    if (!isConnected) return;

    const cleanupInterval = setInterval(() => {
      const now = Date.now();
      const maxAge = 60000; // 60 seconds

      setHistory(prev => {
        const cleaned: Record<string, { time: number; value: number }[]> = {};
        let hasChanges = false;

        Object.entries(prev).forEach(([channel, points]) => {
          const filtered = points.filter(p => now - p.time < maxAge);
          if (filtered.length !== points.length) {
            hasChanges = true;
          }
          if (filtered.length > 0) {
            cleaned[channel] = filtered;
          }
        });

        return hasChanges ? cleaned : prev;
      });
    }, 10000); // Clean up every 10 seconds

    return () => clearInterval(cleanupInterval);
  }, [isConnected]);

  // Auto-connect on mount if enabled - FIXED: removed connect/disconnect from deps to prevent infinite loop
  useEffect(() => {
    if (opts.autoConnect) {
      connect();
    }

    // Cleanup function with direct socket reference to avoid stale closure
    return () => {
      if (socketRef.current) {
        try {
          socketRef.current.emit('stop');
          socketRef.current.disconnect();
        } catch (error) {
          console.error('[LiveLink] Error during cleanup:', error);
        }
        socketRef.current = null;
      }
      setIsConnected(false);
      setIsConnecting(false);
      setMode(null);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opts.autoConnect]); // Only depend on autoConnect, not connect/disconnect

  return {
    isConnected,
    isConnecting,
    connectionError,
    mode,
    channels,
    snapshot,
    history,
    connect,
    disconnect,
    requestSnapshot,
    getChannelValue,
    subscribeChannels,
    clearHistory,
  };
}

export default useLiveLink;

