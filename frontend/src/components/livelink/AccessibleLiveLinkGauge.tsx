/**
 * AccessibleLiveLinkGauge - ARIA-compliant gauge component for JetDrive Command Center
 * 
 * Features:
 * - Full ARIA meter implementation with proper roles and labels
 * - Keyboard navigation support
 * - Screen reader announcements for value changes
 * - High contrast mode support
 * - Responsive design with mobile-first approach
 */

import { useEffect, useRef, useState } from 'react';
import { cn } from '../../lib/utils';

interface AccessibleLiveLinkGaugeProps {
  name: string;
  value: number;
  units?: string;
  min?: number;
  max?: number;
  decimals?: number;
  color?: string;
  warningThreshold?: number;
  criticalThreshold?: number;
  className?: string;
  size?: 'small' | 'medium' | 'large';
  showProgress?: boolean;
  onKeyDown?: (event: React.KeyboardEvent) => void;
}

export function AccessibleLiveLinkGauge({
  name,
  value,
  units = '',
  min = 0,
  max = 100,
  decimals = 1,
  color = '#888',
  warningThreshold,
  criticalThreshold,
  className,
  size = 'medium',
  showProgress = true,
  onKeyDown,
}: AccessibleLiveLinkGaugeProps) {
  const gaugeRef = useRef<HTMLDivElement>(null);
  const [previousValue, setPreviousValue] = useState(value);
  const [isChanged, setIsChanged] = useState(false);

  // Calculate percentage and ensure it's within bounds
  const clampedValue = Math.max(min, Math.min(max, value));
  const percentage = ((clampedValue - min) / (max - min)) * 100;

  // Determine status color based on thresholds
  const getStatusColor = () => {
    if (criticalThreshold !== undefined && value >= criticalThreshold) return '#ef4444'; // red-500
    if (warningThreshold !== undefined && value >= warningThreshold) return '#f59e0b'; // amber-500
    return color;
  };

  const statusColor = getStatusColor();

  // Handle value changes for screen reader announcements
  useEffect(() => {
    if (value !== previousValue) {
      setIsChanged(true);
      setTimeout(() => setIsChanged(false), 1000); // Reset after animation
      setPreviousValue(value);
    }
  }, [value, previousValue]);

  // Format value with proper decimals
  const formatValue = (val: number) => {
    return val.toFixed(decimals);
  };

  // Get gauge sizing based on size prop
  const getGaugeSizing = () => {
    switch (size) {
      case 'small':
        return {
          card: 'p-3',
          value: 'text-2xl',
          label: 'text-xs',
          unit: 'text-[10px]',
          height: 'h-32',
        };
      case 'large':
        return {
          card: 'p-5',
          value: 'text-4xl',
          label: 'text-sm',
          unit: 'text-xs',
          height: 'h-48',
        };
      default: // medium
        return {
          card: 'p-4',
          value: 'text-3xl',
          label: 'text-xs',
          unit: 'text-[10px]',
          height: 'h-40',
        };
    }
  };

  const sizing = getGaugeSizing();

  // Get ARIA label for screen readers
  const getAriaLabel = () => {
    return `${name}: ${formatValue(value)} ${units}. Range: ${min} to ${max}`;
  };

  // Get status text for screen readers
  const getStatusText = () => {
    if (criticalThreshold !== undefined && value >= criticalThreshold) return 'Critical';
    if (warningThreshold !== undefined && value >= warningThreshold) return 'Warning';
    return 'Normal';
  };

  return (
    <div
      ref={gaugeRef}
      role="meter"
      aria-label={getAriaLabel()}
      aria-valuenow={clampedValue}
      aria-valuemin={min}
      aria-valuemax={max}
      aria-valuetext={`${formatValue(value)} ${units} - ${getStatusText()}`}
      tabIndex={0}
      onKeyDown={onKeyDown}
      className={cn(
        'group relative rounded-xl bg-gradient-to-br from-zinc-900/90 to-zinc-950/90 border border-zinc-800/60',
        'hover:border-zinc-700/60 transition-all duration-300',
        'focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-zinc-950',
        'focus:ring-blue-500 focus:border-blue-500',
        sizing.card,
        className
      )}
    >
      {/* Value change announcement for screen readers */}
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {isChanged && `${name} changed to ${formatValue(value)} ${units}`}
      </div>

      {/* Gauge Header */}
      <div className="flex items-center justify-between mb-2">
        <div 
          className={cn(
            'font-medium uppercase tracking-wide truncate',
            'text-zinc-400 group-hover:text-zinc-300 transition-colors',
            sizing.label
          )}
          title={name}
        >
          {name}
        </div>
        {units && (
          <div className={cn('text-zinc-500 font-mono', sizing.unit)}>
            {units}
          </div>
        )}
      </div>

      {/* Main Value Display */}
      <div className="flex items-center justify-center mb-3">
        <div
          className={cn(
            'font-bold tabular-nums tracking-tight transition-colors duration-200',
            'text-center',
            sizing.value
          )}
          style={{ color: statusColor }}
        >
          {formatValue(value)}
        </div>
      </div>

      {/* Progress Bar (optional) */}
      {showProgress && (
        <div className="relative">
          <div className="h-2 bg-zinc-800/50 rounded-full overflow-hidden">
            <div
              className={cn(
                'h-full transition-all duration-300 ease-out',
                'rounded-full'
              )}
              style={{
                width: `${percentage}%`,
                backgroundColor: statusColor,
                boxShadow: `0 0 6px ${statusColor}30`,
              }}
              role="progressbar"
              aria-valuenow={percentage}
              aria-valuemin={0}
              aria-valuemax={100}
            />
          </div>
          
          {/* Threshold indicators */}
          {warningThreshold && (
            <div
              className="absolute top-0 w-0.5 h-full bg-yellow-500/50"
              style={{ left: `${((warningThreshold - min) / (max - min)) * 100}%` }}
              role="presentation"
              aria-hidden="true"
            />
          )}
          {criticalThreshold && (
            <div
              className="absolute top-0 w-0.5 h-full bg-red-500/50"
              style={{ left: `${((criticalThreshold - min) / (max - min)) * 100}%` }}
              role="presentation"
              aria-hidden="true"
            />
          )}
        </div>
      )}

      {/* Range Information for Screen Readers */}
      <div className="sr-only">
        Range from {min} to {max}, current value is {formatValue(value)}
        {warningThreshold && `, warning at ${warningThreshold}`}
        {criticalThreshold && `, critical at ${criticalThreshold}`}
      </div>
    </div>
  );
}