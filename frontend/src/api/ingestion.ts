/**
 * Ingestion Reliability API Client
 * 
 * Provides endpoints for monitoring ingestion health, queue status,
 * circuit breaker state, and data validation metrics.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5001';

const buildErrorMessage = async (response: Response, fallback: string): Promise<string> => {
  const statusLabel = response.statusText ? `${response.status} ${response.statusText}` : `${response.status}`;
  const baseMessage = `${fallback} (${statusLabel})`;

  try {
    const contentType = response.headers.get('content-type') ?? '';
    if (contentType.includes('application/json')) {
      const payload: unknown = await response.json();
      const errorValue =
        payload &&
        typeof payload === 'object' &&
        'error' in payload
          ? (payload as { error?: unknown }).error
          : payload;

      if (typeof errorValue === 'string' && errorValue.trim().length > 0) {
        return `${baseMessage}: ${errorValue}`;
      }

      if (errorValue != null) {
        return `${baseMessage}: ${JSON.stringify(errorValue)}`;
      }
    }

    const text = await response.text();
    return text.trim().length > 0 ? `${baseMessage}: ${text}` : baseMessage;
  } catch {
    return baseMessage;
  }
};

// === Types ===

export interface ChannelHealth {
  channel_id: number;
  channel_name: string;
  health: 'healthy' | 'warning' | 'critical' | 'stale' | 'invalid';
  health_reason: string;
  last_value: number;
  last_timestamp_ms: number;
  age_seconds: number;
  samples_per_second: number;
  total_samples: number;
  invalid_value_count: number;
}

export interface FrameStats {
  total_frames: number;
  dropped_frames: number;
  malformed_frames: number;
  non_provider_frames: number;
  drop_rate_percent: number;
}

export interface DataHealth {
  overall_health: 'healthy' | 'warning' | 'critical' | 'stale' | 'unknown';
  health_reason: string;
  healthy_channels: number;
  total_channels: number;
  channels: Record<string, ChannelHealth>;
  frame_stats: FrameStats;
  timestamp: number;
}

export interface ChannelSummary {
  name: string;
  id: number;
  health: string;
  value: number;
  age_seconds: number;
  rate_hz: number;
}

export interface CircuitBreakerState {
  name: string;
  state: 'closed' | 'open' | 'half_open';
  failure_count: number;
  success_rate: number;
  last_failure: number | null;
}

export interface HealthMonitorState {
  name: string;
  status: 'healthy' | 'degraded' | 'unhealthy' | 'unknown';
  success_rate: number;
  avg_latency_ms: number | null;
  consecutive_failures: number;
  last_check: number | null;
}

export interface ReliabilityHealth {
  status: 'healthy' | 'degraded' | 'unhealthy' | 'unknown';
  timestamp: number;
  circuit_breakers: Record<string, CircuitBreakerState>;
  health_monitors: Record<string, HealthMonitorState>;
  recent_alerts: Alert[];
  stats: {
    total_circuits: number;
    open_circuits: number;
    unhealthy_monitors: number;
    alerts_count: number;
  };
}

export interface Alert {
  type: string;
  message: string;
  timestamp: number;
  data: Record<string, unknown>;
}

export interface QueueStats {
  total_enqueued: number;
  total_processed: number;
  total_failed: number;
  total_dropped: number;
  current_size: number;
  high_watermark: number;
  processing_rate_per_sec: number;
  average_latency_ms: number;
  last_process_time: number;
  items_by_priority: Record<number, number>;
}

export interface ValidationStats {
  total_validated: number;
  passed: number;
  failed: number;
  warnings: number;
  error_types: Record<string, number>;
}

export interface IngestionMetrics {
  data_health: DataHealth;
  reliability: ReliabilityHealth;
  queue?: QueueStats;
  validation?: ValidationStats;
}

// === API Functions ===

/**
 * Get comprehensive data health status
 */
export async function getDataHealth(): Promise<DataHealth> {
  const response = await fetch(`${API_BASE_URL}/api/jetdrive/hardware/live/health`);
  if (!response.ok) {
    throw new Error(await buildErrorMessage(response, 'Failed to fetch data health'));
  }
  return response.json();
}

/**
 * Get quick channel summary
 */
export async function getChannelSummary(): Promise<{ channels: ChannelSummary[]; timestamp: number }> {
  const response = await fetch(`${API_BASE_URL}/api/jetdrive/hardware/live/health/summary`);
  if (!response.ok) {
    throw new Error(await buildErrorMessage(response, 'Failed to fetch channel summary'));
  }
  return response.json();
}

/**
 * Get reliability agent status (circuit breakers, health monitors)
 */
export async function getReliabilityHealth(): Promise<ReliabilityHealth> {
  const response = await fetch(`${API_BASE_URL}/api/reliability/health`);
  if (!response.ok) {
    throw new Error(await buildErrorMessage(response, 'Failed to fetch reliability health'));
  }
  return response.json();
}

/**
 * Reset a specific circuit breaker
 */
export async function resetCircuitBreaker(name: string): Promise<{ success: boolean }> {
  const response = await fetch(`${API_BASE_URL}/api/reliability/circuit-breaker/${name}/reset`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error(await buildErrorMessage(response, 'Failed to reset circuit breaker'));
  }
  return response.json();
}

/**
 * Get all ingestion metrics combined
 */
export async function getIngestionMetrics(): Promise<IngestionMetrics> {
  const [dataHealth, reliability] = await Promise.all([
    getDataHealth().catch(() => null),
    getReliabilityHealth().catch(() => null),
  ]);

  return {
    data_health: dataHealth || {
      overall_health: 'unknown' as const,
      health_reason: 'Unable to fetch data health',
      healthy_channels: 0,
      total_channels: 0,
      channels: {},
      frame_stats: {
        total_frames: 0,
        dropped_frames: 0,
        malformed_frames: 0,
        non_provider_frames: 0,
        drop_rate_percent: 0,
      },
      timestamp: Date.now() / 1000,
    },
    reliability: reliability || {
      status: 'unknown' as const,
      timestamp: Date.now() / 1000,
      circuit_breakers: {},
      health_monitors: {},
      recent_alerts: [],
      stats: {
        total_circuits: 0,
        open_circuits: 0,
        unhealthy_monitors: 0,
        alerts_count: 0,
      },
    },
  };
}

// === Utility Functions ===

export function getHealthColor(health: string): string {
  switch (health) {
    case 'healthy':
      return 'text-green-500';
    case 'warning':
      return 'text-yellow-500';
    case 'critical':
    case 'unhealthy':
      return 'text-red-500';
    case 'stale':
      return 'text-gray-500';
    case 'degraded':
      return 'text-orange-500';
    default:
      return 'text-gray-400';
  }
}

export function getHealthBgColor(health: string): string {
  switch (health) {
    case 'healthy':
      return 'bg-green-500/20 border-green-500/30';
    case 'warning':
      return 'bg-yellow-500/20 border-yellow-500/30';
    case 'critical':
    case 'unhealthy':
      return 'bg-red-500/20 border-red-500/30';
    case 'stale':
      return 'bg-gray-500/20 border-gray-500/30';
    case 'degraded':
      return 'bg-orange-500/20 border-orange-500/30';
    default:
      return 'bg-gray-500/20 border-gray-500/30';
  }
}

export function formatTimestamp(timestamp: number): string {
  return new Date(timestamp * 1000).toLocaleTimeString();
}

export function formatDuration(seconds: number): string {
  if (seconds < 60) {
    return `${seconds.toFixed(1)}s`;
  }
  if (seconds < 3600) {
    return `${Math.floor(seconds / 60)}m ${Math.floor(seconds % 60)}s`;
  }
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}

