import { Play } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import { cn } from '@/lib/utils';
import type { UseJetDriveLiveReturn } from '@/hooks/useJetDriveLive';
import { CommandCenter } from '@/components/jetdrive/CommandCenter';

type ActiveView = 'command-center' | 'tuning';

interface CommandCenterPaneProps {
  activeView: ActiveView;
  isSimulatorActive: boolean;
  simThrottle: number;
  onThrottleChange: (value: number) => void;
  simulatorState: string | null;
  isTriggeringPull: boolean;
  onTriggerPull: () => void;
  live: UseJetDriveLiveReturn;
  hardwareOpen: boolean;
  onHardwareOpenChange: (open: boolean) => void;
}

export function CommandCenterPane({
  activeView,
  isSimulatorActive,
  simThrottle,
  onThrottleChange,
  simulatorState,
  isTriggeringPull,
  onTriggerPull,
  live,
  hardwareOpen,
  onHardwareOpenChange,
}: CommandCenterPaneProps) {
  return (
    <div className={cn('flex flex-1 flex-col min-h-0', activeView !== 'command-center' && 'hidden')}>
      {isSimulatorActive && (
        <>
          <div className="flex h-6 items-center justify-center bg-yellow-500/10 border-b border-yellow-500/30 text-xs font-bold uppercase tracking-widest text-yellow-400">
            Simulator Mode
          </div>
          <div className="flex items-center gap-4 bg-zinc-900/50 border-b border-yellow-500/30 px-6 py-3">
            <div className="flex items-center gap-3 text-sm text-zinc-300">
              <span className="font-semibold">Throttle:</span>
              <span className="font-mono text-yellow-400 font-bold min-w-[4ch] text-right">
                {Math.round(simThrottle)}%
              </span>
            </div>
            <div className="flex-1 max-w-md">
              <Slider
                value={[Math.max(0, Math.min(100, simThrottle))]}
                onValueChange={(v) => onThrottleChange(v[0] ?? 0)}
                min={0}
                max={100}
                step={1}
              />
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-zinc-400">
                State: {simulatorState ?? 'unknown'}
              </span>
              <Button
                type="button"
                size="sm"
                className="h-7 bg-orange-600 hover:bg-orange-500 text-white"
                onClick={onTriggerPull}
                disabled={isTriggeringPull || !!(simulatorState && simulatorState !== 'idle')}
              >
                <Play className="mr-1.5 h-3.5 w-3.5" />
                {isTriggeringPull ? 'Starting...' : 'Trigger Pull'}
              </Button>
            </div>
          </div>
        </>
      )}
      <div className={cn('flex-1 min-h-0', isSimulatorActive && 'ring-2 ring-yellow-500/70 rounded-md m-1')}>
        <CommandCenter
          live={live}
          hardwareOpen={hardwareOpen}
          onHardwareOpenChange={onHardwareOpenChange}
        />
      </div>
    </div>
  );
}
