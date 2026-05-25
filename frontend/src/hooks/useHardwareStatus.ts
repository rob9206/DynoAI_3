/**
 * useHardwareStatus — single source of truth for the JetDrive Hardware UI.
 *
 * Consumes one backend payload (``/hardware/status``) that aggregates:
 *   - provider/monitor state
 *   - capture state
 *   - per-canonical channel health (renderer truth for the Health Board)
 *   - top-line mapping confidence
 *   - ingestion validator summary
 *
 * Transport policy (no retry storms):
 *   1. Subscribe to the existing ``/hardware/live/stream`` SSE channel and
 *      prefer ``event: health`` events when available (~2 Hz, server-pushed).
 *   2. If SSE is unavailable or hasn't delivered a health event recently,
 *      fall back to polling ``GET /hardware/status`` at 1.5 s.
 *   3. The polling loop disables itself the moment SSE confirms a health
 *      event arrived inside the freshness window, so two transports never
 *      race or double-fetch.
 *
 * Strict TypeScript renderer policy: this hook only relays backend-derived
 * values to consumers. No physics, no unit conversion, no plausibility
 * math. See ``.cursor/rules/no-physics-in-frontend.mdc``.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { subscribeSse } from '../lib/sseManager';

export type ChannelStatus =
  | 'OK'
  | 'STALE'
  | 'UNMAPPED'
  | 'INVALID'
  | 'NO_SIGNAL';

export type SummaryState =
  | 'idle'
  | 'unmapped'
  | 'warming_up'
  | 'stale'
  | 'invalid'
  | 'all_healthy';

export interface ChannelSource {
  provider_id: string | null;
  channel_id: number | null;
  raw_name: string | null;
}

export interface ChannelHealthRow {
  canonical_name: string;
  category: string;
  required: boolean;
  expected_units: string;
  status: ChannelStatus;
  value: number | null;
  units: string | null;
  age_seconds: number | null;
  source: ChannelSource | null;
  flags: string[];
  reasons: string[];
  samples_per_second?: number;
  total_samples?: number;
  lc2_peg_count_60s?: number;
  value_out_of_range_count_60s?: number;
  min_value?: number | null;
  max_value?: number | null;
}

export interface ChannelsHealthPayload {
  capturing: boolean;
  provider: {
    provider_id: string | null;
    name: string | null;
    host: string | null;
  };
  all_required_ok: boolean;
  summary: {
    state: SummaryState;
    message: string;
    counts: Record<ChannelStatus, number>;
  };
  afr_plausibility: { min: number; max: number };
  lc2_ceiling: number;
  stale_threshold_seconds: number;
  wot_tps_threshold: number;
  channels: ChannelHealthRow[];
  timestamp: number;
  error: string | null;
  error_code: string | null;
}

export interface ProviderBlock {
  monitor_running: boolean;
  last_check: string | null;
  connected: boolean;
  count: number;
  providers: {
    provider_id: number;
    name: string;
    host: string;
    channel_count: number;
  }[];
}

export interface CaptureBlock {
  capturing: boolean;
  last_update_ts: number | null;
  data_age_seconds: number | null;
  provider_id: string | null;
  provider_name: string | null;
  provider_host: string | null;
  error: string | null;
  error_code: string | null;
}

export interface MappingSavedBlock {
  provider_signature: string;
  provider_id: string | null;
  provider_name: string;
  ready_for_capture: boolean;
  missing_required: string[];
  mapped_count: number;
  required_canonicals: string[];
}

export interface MappingTransientBlock {
  provider_signature: string;
  provider_id: string | null;
  provider_id_int: number;
  provider_name: string;
  host: string;
  proposed_at: number;
  expires_at: number;
  source: string;
  mapping: Record<string, unknown>;
  ttl_remaining_seconds: number;
}

export interface MappingBlock {
  saved: MappingSavedBlock | null;
  transient_proposal: MappingTransientBlock | null;
}

export interface IngestionBlock {
  overall_health: string;
  health_reason?: string | null;
  healthy_channels: number;
  total_channels: number;
  drop_rate_percent: number;
  active_provider_id?: string | null;
}

export interface UnifiedStatusPayload {
  timestamp: number;
  provider: ProviderBlock;
  capture: CaptureBlock;
  channels: ChannelsHealthPayload;
  mapping: MappingBlock | null;
  ingestion: IngestionBlock;
}

export interface UseHardwareStatusOptions {
  /** Backend base URL (default: ``http://127.0.0.1:5001/api/jetdrive``). */
  apiUrl?: string;
  /** Polling fallback interval (default: 1500 ms). 0 disables polling. */
  pollIntervalMs?: number;
  /** Max age (ms) we trust a SSE-pushed payload before falling back to polling. */
  ssePayloadTtlMs?: number;
}

export interface UseHardwareStatusReturn {
  status: UnifiedStatusPayload | null;
  isFetching: boolean;
  /** Last error message from either SSE parsing or polling. */
  error: string | null;
  /** Source of the most recent payload. */
  source: 'sse' | 'poll' | 'none';
  /** Trigger an explicit poll (debug / manual refresh). */
  refresh: () => void;
}

const DEFAULT_API_URL = 'http://127.0.0.1:5001/api/jetdrive';
const DEFAULT_POLL_INTERVAL = 1500;
// SSE health events fire at ~2 Hz; if we haven't seen one in 3 s, we fall
// back to polling so the UI never freezes on a quiet stream.
const DEFAULT_SSE_PAYLOAD_TTL_MS = 3000;

function isHealthSelfSufficient(
  payload: UnifiedStatusPayload | null,
): boolean {
  return Boolean(payload?.channels && payload?.provider && payload?.capture);
}

export function useHardwareStatus(
  options: UseHardwareStatusOptions = {},
): UseHardwareStatusReturn {
  const apiUrl = options.apiUrl ?? DEFAULT_API_URL;
  const pollIntervalMs = options.pollIntervalMs ?? DEFAULT_POLL_INTERVAL;
  const sseTtlMs = options.ssePayloadTtlMs ?? DEFAULT_SSE_PAYLOAD_TTL_MS;

  const [status, setStatus] = useState<UnifiedStatusPayload | null>(null);
  const [isFetching, setIsFetching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<'sse' | 'poll' | 'none'>('none');
  const [pollTick, setPollTick] = useState(0);

  const lastSseAtRef = useRef<number>(0);

  // Subscribe to the shared SSE manager and listen for ``event: health``.
  // The shared manager guarantees at most one EventSource per origin even
  // when ``useJetDriveLive`` and ``useHardwareStatus`` are both mounted.
  useEffect(() => {
    let cancelled = false;
    const url = `${apiUrl}/hardware/live/stream`;
    const unsubscribe = subscribeSse(url, {
      onEvent: (eventName, data) => {
        if (cancelled) return;
        if (eventName !== 'health') return;
        try {
          const parsed = JSON.parse(data) as UnifiedStatusPayload;
          if (!isHealthSelfSufficient(parsed)) return;
          lastSseAtRef.current = Date.now();
          setStatus(parsed);
          setSource('sse');
          setError(null);
        } catch (err) {
          setError(err instanceof Error ? err.message : 'SSE parse error');
        }
      },
    });

    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, [apiUrl]);

  // Polling fallback. Only fires when the SSE freshness window has lapsed.
  useEffect(() => {
    if (pollIntervalMs <= 0) return;
    let cancelled = false;
    let timeoutId: number | null = null;

    const tick = async () => {
      if (cancelled) return;
      const sinceLastSse = Date.now() - lastSseAtRef.current;
      if (lastSseAtRef.current > 0 && sinceLastSse < sseTtlMs) {
        // SSE is still fresh; defer the next attempt.
        timeoutId = window.setTimeout(() => void tick(), pollIntervalMs);
        return;
      }
      try {
        setIsFetching(true);
        const response = await fetch(`${apiUrl}/hardware/status`);
        if (!response.ok) {
          throw new Error(`hardware/status returned ${response.status}`);
        }
        const data = (await response.json()) as UnifiedStatusPayload;
        if (cancelled) return;
        if (isHealthSelfSufficient(data)) {
          setStatus(data);
          setSource('poll');
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'status fetch failed');
        }
      } finally {
        if (!cancelled) {
          setIsFetching(false);
          timeoutId = window.setTimeout(() => void tick(), pollIntervalMs);
        }
      }
    };

    void tick();
    return () => {
      cancelled = true;
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [apiUrl, pollIntervalMs, sseTtlMs, pollTick]);

  const refresh = useMemo(
    () => () => {
      // Force the polling loop to re-tick by busting the dep array.
      setPollTick((value) => value + 1);
    },
    [],
  );

  return {
    status,
    isFetching,
    error,
    source,
    refresh,
  };
}

export default useHardwareStatus;
