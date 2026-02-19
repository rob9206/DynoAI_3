import { useEffect, useRef } from 'react';

interface PerformanceMetrics {
  renderCount: number;
  lastRenderTime: number;
  averageRenderTime: number;
  slowRenders: number;
}

/**
 * Hook to monitor component render performance
 * Useful for identifying performance bottlenecks
 * 
 * @param componentName - Name of the component for logging
 * @param slowThreshold - Threshold in ms to consider a render "slow" (default: 16ms = 60fps)
 */
export function usePerformanceMonitor(
  componentName: string,
  slowThreshold: number = 16
) {
  const metricsRef = useRef<PerformanceMetrics>({
    renderCount: 0,
    lastRenderTime: 0,
    averageRenderTime: 0,
    slowRenders: 0,
  });

  const renderStartRef = useRef<number>(0);

  // Mark render start
  renderStartRef.current = performance.now();

  useEffect(() => {
    // Calculate render time
    const renderTime = performance.now() - renderStartRef.current;
    const metrics = metricsRef.current;

    // Update metrics
    metrics.renderCount++;
    metrics.lastRenderTime = renderTime;
    metrics.averageRenderTime =
      (metrics.averageRenderTime * (metrics.renderCount - 1) + renderTime) /
      metrics.renderCount;

    if (renderTime > slowThreshold) {
      metrics.slowRenders++;
      console.warn(
        `[Performance] Slow render detected in ${componentName}:`,
        `${renderTime.toFixed(2)}ms (threshold: ${slowThreshold}ms)`
      );
    }

    // Log summary every 100 renders
    if (metrics.renderCount % 100 === 0) {
      console.log(`[Performance] ${componentName} summary:`, {
        totalRenders: metrics.renderCount,
        avgRenderTime: `${metrics.averageRenderTime.toFixed(2)}ms`,
        slowRenders: metrics.slowRenders,
        slowRenderRate: `${((metrics.slowRenders / metrics.renderCount) * 100).toFixed(1)}%`,
      });
    }
  });

  return metricsRef.current;
}

/**
 * Hook to measure and log the time taken by an async operation
 */
export function useAsyncPerformance() {
  const measure = async <T,>(
    operationName: string,
    operation: () => Promise<T>
  ): Promise<T> => {
    const start = performance.now();
    try {
      const result = await operation();
      const duration = performance.now() - start;
      console.log(`[Performance] ${operationName}: ${duration.toFixed(2)}ms`);
      return result;
    } catch (error) {
      const duration = performance.now() - start;
      console.error(
        `[Performance] ${operationName} failed after ${duration.toFixed(2)}ms:`,
        error
      );
      throw error;
    }
  };

  return { measure };
}

/**
 * Hook to track Web Vitals metrics
 */
export function useWebVitals() {
  useEffect(() => {
    // Check if Performance Observer is supported
    if (typeof PerformanceObserver === 'undefined') return;

    // Largest Contentful Paint (LCP)
    const lcpObserver = new PerformanceObserver((list) => {
      const entries = list.getEntries();
      const lastEntry = entries[entries.length - 1];
      console.log('[Web Vitals] LCP:', `${lastEntry.startTime.toFixed(2)}ms`);
    });

    try {
      lcpObserver.observe({ entryTypes: ['largest-contentful-paint'] });
    } catch (e) {
      // LCP not supported
    }

    // First Input Delay (FID)
    const fidObserver = new PerformanceObserver((list) => {
      const entries = list.getEntries();
      entries.forEach((entry: any) => {
        const fid = entry.processingStart - entry.startTime;
        console.log('[Web Vitals] FID:', `${fid.toFixed(2)}ms`);
      });
    });

    try {
      fidObserver.observe({ entryTypes: ['first-input'] });
    } catch (e) {
      // FID not supported
    }

    // Cumulative Layout Shift (CLS)
    let clsScore = 0;
    const clsObserver = new PerformanceObserver((list) => {
      const entries = list.getEntries();
      entries.forEach((entry: any) => {
        if (!entry.hadRecentInput) {
          clsScore += entry.value;
        }
      });
      console.log('[Web Vitals] CLS:', clsScore.toFixed(4));
    });

    try {
      clsObserver.observe({ entryTypes: ['layout-shift'] });
    } catch (e) {
      // CLS not supported
    }

    return () => {
      lcpObserver.disconnect();
      fidObserver.disconnect();
      clsObserver.disconnect();
    };
  }, []);
}

/**
 * Hook to detect slow network conditions
 */
export function useNetworkStatus() {
  useEffect(() => {
    if (!('connection' in navigator)) return;

    const connection = (navigator as any).connection;
    
    const logNetworkInfo = () => {
      console.log('[Network]', {
        effectiveType: connection.effectiveType,
        downlink: `${connection.downlink} Mbps`,
        rtt: `${connection.rtt}ms`,
        saveData: connection.saveData,
      });

      // Warn on slow connections
      if (connection.effectiveType === 'slow-2g' || connection.effectiveType === '2g') {
        console.warn('[Network] Slow connection detected. Consider reducing data usage.');
      }
    };

    logNetworkInfo();
    connection.addEventListener('change', logNetworkInfo);

    return () => {
      connection.removeEventListener('change', logNetworkInfo);
    };
  }, []);
}

