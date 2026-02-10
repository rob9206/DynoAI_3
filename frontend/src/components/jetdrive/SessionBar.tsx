import { useMemo, useState } from 'react';
import { cn } from '../../lib/utils';
import { Button } from '../ui/button';

type CaptureState = 'idle' | 'armed' | 'recording';

interface PullStats {
  peakRpm?: number;
  peakHp?: number;
  maxAfrDeviation?: number;
}

interface SessionBarProps {
  pullCount?: number;
  estimatedPulls?: number;
  selectedPull?: number | null;
  captureState?: CaptureState;
  pullStats?: Record<number, PullStats>;
  onCaptureStateChange?: (state: CaptureState) => void;
  onSelectPull?: (pullNumber: number) => void;
  onEndSession?: () => void;
  className?: string;
}

export function SessionBar({
  pullCount = 0,
  estimatedPulls = 8,
  selectedPull = null,
  captureState,
  pullStats,
  onCaptureStateChange,
  onSelectPull,
  onEndSession,
  className,
}: SessionBarProps) {
  const [localCaptureState, setLocalCaptureState] = useState<CaptureState>('idle');
  const state = captureState ?? localCaptureState;

  const totalPulls = Math.max(estimatedPulls, pullCount + 1);
  const currentPull = state === 'recording' ? pullCount + 1 : pullCount;

  const dots = useMemo(() => {
    return Array.from({ length: totalPulls }, (_, index) => {
      const pullNumber = index + 1;
      const isComplete = pullNumber <= pullCount;
      const isActive = pullNumber === currentPull && state === 'recording';
      const isSelected = selectedPull === pullNumber;
      return { pullNumber, isComplete, isActive, isSelected };
    });
  }, [currentPull, pullCount, state, totalPulls, selectedPull]);

  const handleCaptureToggle = () => {
    const nextState = state === 'idle' ? 'armed' : 'idle';
    setLocalCaptureState(nextState);
    onCaptureStateChange?.(nextState);
  };

  const getDotTooltip = (dot: { pullNumber: number; isComplete: boolean }) => {
    if (!dot.isComplete) return `Pull ${dot.pullNumber} (estimated)`;
    const stats = pullStats?.[dot.pullNumber];
    if (!stats) return `Pull ${dot.pullNumber} (completed)`;
    const parts = [`Pull ${dot.pullNumber}`];
    if (stats.peakRpm) parts.push(`peak RPM: ${Math.round(stats.peakRpm).toLocaleString()}`);
    if (stats.peakHp) parts.push(`peak HP: ${stats.peakHp.toFixed(1)}`);
    if (stats.maxAfrDeviation !== undefined) parts.push(`max AFR dev: ±${stats.maxAfrDeviation.toFixed(2)}`);
    return parts.join(' | ');
  };

  return (
    <div
      className={cn(
        'flex h-12 items-center justify-between gap-4 border-t border-zinc-800 bg-zinc-950/60 px-4',
        className,
      )}
    >
      <div className="flex items-center gap-3">
        <span className="text-xs text-zinc-400">
          Pulls: {pullCount} / ~{totalPulls}
        </span>
        <div className="flex items-center gap-2">
          {dots.map((dot) => (
            <button
              key={dot.pullNumber}
              type="button"
              className={cn(
                'h-2.5 w-2.5 rounded-full transition-colors',
                // Completed: filled bright
                dot.isComplete && !dot.isActive ? 'bg-zinc-100' : null,
                // Estimated remaining: dim
                !dot.isComplete && !dot.isActive ? 'bg-zinc-700' : null,
                // Active/recording: pulsing orange
                dot.isActive ? 'bg-orange-500 animate-pulse ring-1 ring-orange-500/50' : null,
                // Selected
                dot.isSelected && !dot.isActive ? 'ring-2 ring-orange-500' : null,
              )}
              title={getDotTooltip(dot)}
              onClick={() => dot.isComplete && onSelectPull?.(dot.pullNumber)}
            />
          ))}
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant={state === 'idle' ? 'default' : 'secondary'}
          className={cn(
            'h-8 px-3 text-xs',
            state === 'idle' && 'bg-orange-500 hover:bg-orange-600 text-white',
            state === 'armed' && 'border border-green-500/40 text-green-300 hover:text-green-200',
            state === 'recording' && 'border border-red-500/40 text-red-300 hover:text-red-200',
          )}
          onClick={handleCaptureToggle}
        >
          {/* Status dot before label */}
          {state === 'armed' && (
            <span className="mr-1.5 inline-block h-2 w-2 rounded-full bg-green-500 animate-pulse" />
          )}
          {state === 'recording' && (
            <span className="mr-1.5 inline-block h-2 w-2 rounded-full bg-red-500 animate-pulse" />
          )}
          {state === 'idle' && '▶ Arm Capture'}
          {state === 'armed' && 'Armed — Waiting...'}
          {state === 'recording' && `Recording pull #${currentPull}...`}
        </Button>
        <Button type="button" variant="secondary" className="h-8 px-3 text-xs" onClick={onEndSession}>
          ⏹ End Session
        </Button>
      </div>
    </div>
  );
}
