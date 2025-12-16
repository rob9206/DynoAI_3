/**
 * Performance utility functions
 * Centralized location for performance-related helpers
 */

/**
 * Measure the execution time of a function
 */
export async function measurePerformance<T>(
  name: string,
  fn: () => Promise<T> | T
): Promise<T> {
  const start = performance.now();
  try {
    const result = await fn();
    const duration = performance.now() - start;
    console.log(`[Performance] ${name}: ${duration.toFixed(2)}ms`);
    return result;
  } catch (error) {
    const duration = performance.now() - start;
    console.error(`[Performance] ${name} failed after ${duration.toFixed(2)}ms:`, error);
    throw error;
  }
}

/**
 * Check if the user is on a slow connection
 */
export function isSlowConnection(): boolean {
  if (!('connection' in navigator)) return false;
  const connection = (navigator as any).connection;
  return (
    connection.effectiveType === 'slow-2g' ||
    connection.effectiveType === '2g' ||
    connection.saveData === true
  );
}

/**
 * Get current FPS (frames per second)
 */
export function measureFPS(duration: number = 1000): Promise<number> {
  return new Promise((resolve) => {
    let frames = 0;
    let lastTime = performance.now();
    
    const countFrame = () => {
      frames++;
      const currentTime = performance.now();
      
      if (currentTime - lastTime >= duration) {
        const fps = Math.round((frames * 1000) / (currentTime - lastTime));
        resolve(fps);
      } else {
        requestAnimationFrame(countFrame);
      }
    };
    
    requestAnimationFrame(countFrame);
  });
}

/**
 * Preload critical resources
 */
export function preloadResource(url: string, type: 'script' | 'style' | 'image' | 'font') {
  const link = document.createElement('link');
  link.rel = 'preload';
  link.href = url;
  link.as = type;
  
  if (type === 'font') {
    link.crossOrigin = 'anonymous';
  }
  
  document.head.appendChild(link);
}

/**
 * Prefetch resources for future navigation
 */
export function prefetchResource(url: string) {
  const link = document.createElement('link');
  link.rel = 'prefetch';
  link.href = url;
  document.head.appendChild(link);
}

/**
 * Check if device has enough resources for heavy animations
 */
export function canHandleHeavyAnimations(): boolean {
  // Check for reduced motion preference
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    return false;
  }
  
  // Check for low-end device indicators
  const connection = (navigator as any).connection;
  if (connection?.saveData) {
    return false;
  }
  
  // Check for hardware concurrency (CPU cores)
  if (navigator.hardwareConcurrency && navigator.hardwareConcurrency < 4) {
    return false;
  }
  
  return true;
}

/**
 * Batch multiple DOM updates
 */
export function batchDOMUpdates(updates: Array<() => void>) {
  requestAnimationFrame(() => {
    updates.forEach(update => update());
  });
}

/**
 * Idle callback wrapper with fallback
 */
export function runWhenIdle(callback: () => void, timeout: number = 1000) {
  if ('requestIdleCallback' in window) {
    (window as any).requestIdleCallback(callback, { timeout });
  } else {
    setTimeout(callback, 1);
  }
}

/**
 * Get performance metrics summary
 */
export function getPerformanceMetrics() {
  const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
  
  if (!navigation) {
    return null;
  }
  
  return {
    // Load times
    domContentLoaded: navigation.domContentLoadedEventEnd - navigation.domContentLoadedEventStart,
    loadComplete: navigation.loadEventEnd - navigation.loadEventStart,
    
    // Network
    dns: navigation.domainLookupEnd - navigation.domainLookupStart,
    tcp: navigation.connectEnd - navigation.connectStart,
    request: navigation.responseStart - navigation.requestStart,
    response: navigation.responseEnd - navigation.responseStart,
    
    // Processing
    domProcessing: navigation.domComplete - navigation.domInteractive,
    
    // Total
    totalTime: navigation.loadEventEnd - navigation.fetchStart,
  };
}

/**
 * Log performance metrics to console
 */
export function logPerformanceMetrics() {
  const metrics = getPerformanceMetrics();
  
  if (!metrics) {
    console.log('[Performance] Metrics not available yet');
    return;
  }
  
  console.table({
    'DNS Lookup': `${metrics.dns.toFixed(2)}ms`,
    'TCP Connection': `${metrics.tcp.toFixed(2)}ms`,
    'Request Time': `${metrics.request.toFixed(2)}ms`,
    'Response Time': `${metrics.response.toFixed(2)}ms`,
    'DOM Processing': `${metrics.domProcessing.toFixed(2)}ms`,
    'Total Load Time': `${metrics.totalTime.toFixed(2)}ms`,
  });
}

/**
 * Export for use in performance monitoring
 */
export const performance_utils = {
  measurePerformance,
  isSlowConnection,
  measureFPS,
  preloadResource,
  prefetchResource,
  canHandleHeavyAnimations,
  batchDOMUpdates,
  runWhenIdle,
  getPerformanceMetrics,
  logPerformanceMetrics,
};

