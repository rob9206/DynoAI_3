/**
 * useIngestionHealth - React hook for monitoring data ingestion health
 * 
 * Provides real-time visibility into:
 * - Channel health and data quality
 * - Circuit breaker states
 * - Queue statistics
 * - Frame drop rates
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  getDataHealth,
  getReliabilityHealth,
  resetCircuitBreaker,
  type DataHealth,
  type ReliabilityHealth,
  type ChannelHealth,
  type CircuitBreakerState,
} from '../api/ingestion';

export interface UseIngestionHealthOptions {
  /** Poll interval in ms (default: 2000) */
  pollInterval?: number;
  /** Auto-start polling (default: true) */
  autoStart?: boolean;
  /** Enable reliability monitoring (default: true) */
  enableReliability?: boolean;
}

export interface UseIngestionHealthReturn {
  // Data health
  dataHealth: DataHealth | null;
  overallHealth: DataHealth['overall_health'] | 'unknown';
  healthyChannels: number;
  totalChannels: number;
  channels: Record<string, ChannelHealth>;
  frameStats: {
    total: number;
    dropped: number;
    dropRate: number;
  };

  // Reliability
  reliabilityHealth: ReliabilityHealth | null;
  circuitBreakers: Record<string, CircuitBreakerState>;
  openCircuits: number;
  
  // State
  isLoading: boolean;
  error: string | null;
  lastUpdate: number;

  // Actions
  refresh: () => Promise<void>;
  resetCircuit: (name: string) => Promise<boolean>;
  startPolling: () => void;
  stopPolling: () => void;
}

const DEFAULT_OPTIONS: Required<UseIngestionHealthOptions> = {
  pollInterval: 2000,
  autoStart: true,
  enableReliability: true,
};

export function useIngestionHealth(options: UseIngestionHealthOptions = {}): UseIngestionHealthReturn {
  const opts = { ...DEFAULT_OPTIONS, ...options };

  // Data health state
  const [dataHealth, setDataHealth] = useState<DataHealth | null>(null);
  
  // Reliability state
  const [reliabilityHealth, setReliabilityHealth] = useState<ReliabilityHealth | null>(null);
  
  // UI state
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState(0);
  
  // Polling ref
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isPollingRef = useRef(false);

  // Fetch data health
  const fetchDataHealth = useCallback(async () => {
    try {
      const health = await getDataHealth();
      setDataHealth(health);
      setError(null);
      setLastUpdate(Date.now());
    } catch (err) {
      // Don't overwrite existing data on error
      if (!dataHealth) {
        setError(err instanceof Error ? err.message : 'Failed to fetch data health');
      }
    }
  }, [dataHealth]);

  // Fetch reliability health
  const fetchReliabilityHealth = useCallback(async () => {
    if (!opts.enableReliability) return;
    
    try {
      const health = await getReliabilityHealth();
      setReliabilityHealth(health);
    } catch {
      // Silent fail for reliability - it's supplementary data
    }
  }, [opts.enableReliability]);

  // Combined refresh
  const refresh = useCallback(async () => {
    setIsLoading(true);
    await Promise.all([
      fetchDataHealth(),
      fetchReliabilityHealth(),
    ]);
    setIsLoading(false);
  }, [fetchDataHealth, fetchReliabilityHealth]);

  // Reset circuit breaker
  const resetCircuit = useCallback(async (name: string): Promise<boolean> => {
    try {
      await resetCircuitBreaker(name);
      // Refresh to get updated state
      await fetchReliabilityHealth();
      return true;
    } catch {
      return false;
    }
  }, [fetchReliabilityHealth]);

  // Start polling
  const startPolling = useCallback(() => {
    if (isPollingRef.current) return;
    
    isPollingRef.current = true;
    refresh(); // Initial fetch
    
    pollIntervalRef.current = setInterval(() => {
      fetchDataHealth();
      // Fetch reliability less frequently
      if (Math.random() < 0.5) {
        fetchReliabilityHealth();
      }
    }, opts.pollInterval);
  }, [opts.pollInterval, refresh, fetchDataHealth, fetchReliabilityHealth]);

  // Stop polling
  const stopPolling = useCallback(() => {
    isPollingRef.current = false;
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  }, []);

  // Auto-start effect
  useEffect(() => {
    if (opts.autoStart) {
      startPolling();
    }
    
    return () => {
      stopPolling();
    };
  }, [opts.autoStart, startPolling, stopPolling]);

  // Computed values
  const overallHealth = dataHealth?.overall_health || 'unknown';
  const healthyChannels = dataHealth?.healthy_channels || 0;
  const totalChannels = dataHealth?.total_channels || 0;
  const channels = dataHealth?.channels || {};
  
  const frameStats = {
    total: dataHealth?.frame_stats?.total_frames || 0,
    dropped: dataHealth?.frame_stats?.dropped_frames || 0,
    dropRate: dataHealth?.frame_stats?.drop_rate_percent || 0,
  };
  
  const circuitBreakers = reliabilityHealth?.circuit_breakers || {};
  const openCircuits = reliabilityHealth?.stats?.open_circuits || 0;

  return {
    // Data health
    dataHealth,
    overallHealth,
    healthyChannels,
    totalChannels,
    channels,
    frameStats,
    
    // Reliability
    reliabilityHealth,
    circuitBreakers,
    openCircuits,
    
    // State
    isLoading,
    error,
    lastUpdate,
    
    // Actions
    refresh,
    resetCircuit,
    startPolling,
    stopPolling,
  };
}

export default useIngestionHealth;

