import { useEffect, useRef, useState } from 'react';

/**
 * Debounces a value by delaying updates until after the specified delay
 * Useful for reducing re-renders on rapidly changing data
 */
export function useDebounce<T>(value: T, delay: number = 300): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}

/**
 * Throttles a value by limiting updates to once per interval.
 * Uses ref-based timing to avoid a self-referencing dependency cycle.
 * Leading edge fires immediately when the interval has elapsed;
 * trailing edge schedules exactly one deferred update.
 */
export function useThrottle<T>(value: T, interval: number = 100): T {
  const [throttledValue, setThrottledValue] = useState<T>(value);
  const lastFiredRef = useRef<number>(0);
  const pendingRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const now = Date.now();
    const elapsed = now - lastFiredRef.current;

    if (elapsed >= interval) {
      // Leading edge: fire immediately
      lastFiredRef.current = now;
      setThrottledValue(value);
      if (pendingRef.current) {
        clearTimeout(pendingRef.current);
        pendingRef.current = null;
      }
    } else if (!pendingRef.current) {
      // Trailing edge: schedule one deferred update
      pendingRef.current = setTimeout(() => {
        lastFiredRef.current = Date.now();
        setThrottledValue(value);
        pendingRef.current = null;
      }, interval - elapsed);
    }

    return () => {
      if (pendingRef.current) {
        clearTimeout(pendingRef.current);
        pendingRef.current = null;
      }
    };
  }, [value, interval]);

  return throttledValue;
}

