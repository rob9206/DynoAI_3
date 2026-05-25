/**
 * HardwareStatusContext — single shared subscription for the JetDrive shell.
 *
 * Without this provider, ``ChannelHealthBoard``, ``MappingConfidencePanel``,
 * the JetDrive top bar, and any future consumer would each call
 * ``useHardwareStatus()`` and open their own ``EventSource`` and polling
 * loop. Even with the shared SSE manager handling fan-out, every consumer
 * would still allocate parallel React state and parallel ``fetch`` polls.
 *
 * Hoisting the hook into a provider gives every consumer a single
 * ``UnifiedStatusPayload`` reference per render and lets the SSE manager
 * keep the subscriber count to exactly one.
 *
 * Strict renderer policy: this module relays the value from
 * ``useHardwareStatus`` unchanged.
 */

import { createContext, useContext, type ReactNode } from 'react';
import {
  useHardwareStatus,
  type UseHardwareStatusOptions,
  type UseHardwareStatusReturn,
} from './useHardwareStatus';

const HardwareStatusContext = createContext<UseHardwareStatusReturn | null>(null);

interface HardwareStatusProviderProps extends UseHardwareStatusOptions {
  children: ReactNode;
}

export function HardwareStatusProvider({
  children,
  ...options
}: HardwareStatusProviderProps) {
  const value = useHardwareStatus(options);
  return (
    <HardwareStatusContext.Provider value={value}>
      {children}
    </HardwareStatusContext.Provider>
  );
}

const FALLBACK_STATUS: UseHardwareStatusReturn = {
  status: null,
  isFetching: false,
  error: null,
  source: 'none',
  refresh: () => undefined,
};

/**
 * Read the shared hardware status.
 *
 * In dev: throws a clear error if a consumer is mounted outside the
 * provider so the missing wrapper is impossible to overlook.
 * In prod: degrades to ``FALLBACK_STATUS`` (status=null, isFetching=false)
 * so the UI shows a benign "Loading…" rather than crashing or spinning.
 */
export function useHardwareStatusContext(): UseHardwareStatusReturn {
  const value = useContext(HardwareStatusContext);
  if (value === null) {
    if (import.meta.env.DEV) {
      throw new Error(
        'useHardwareStatusContext must be used within <HardwareStatusProvider>',
      );
    }
    return FALLBACK_STATUS;
  }
  return value;
}

/** Test seam: make the fallback object referentially stable for assertions. */
export const __HARDWARE_STATUS_FALLBACK_FOR_TESTS = FALLBACK_STATUS;
