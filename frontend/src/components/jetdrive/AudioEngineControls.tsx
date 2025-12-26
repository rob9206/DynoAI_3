import { useEffect, useMemo, useState } from 'react';
import { Power } from 'lucide-react';
import { Button } from '../ui/button';
import type { AudioEngineApi } from '../../hooks/useAudioEngine';

export interface AudioEngineControlsProps {
  rpm: number;
  load: number; // 0..1
  autoStart?: boolean;
  autoStartRpm?: number;
  compact?: boolean;
  cylinders?: number;
  funMode?: boolean;
  externalAudioEngine?: AudioEngineApi;
}

export function AudioEngineControls({
  rpm,
  load,
  autoStart = false,
  autoStartRpm = 1200,
  compact = false,
  externalAudioEngine,
}: AudioEngineControlsProps) {
  const engine = externalAudioEngine;
  const isPlaying = !!engine?.state?.isPlaying;

  const [starting, setStarting] = useState(false);

  const canAutoStart = useMemo(() => autoStart && rpm >= autoStartRpm, [autoStart, rpm, autoStartRpm]);

  // Opportunistically keep the external engine updated (safe even if the page also updates it).
  useEffect(() => {
    if (!engine) return;
    engine.setRpm(rpm);
    engine.setLoad(load);
  }, [engine, rpm, load]);

  // Auto-start if requested.
  useEffect(() => {
    if (!engine) return;
    if (!canAutoStart) return;
    if (engine.state.isPlaying) return;
    void engine.startEngine().catch((err) => {
      console.debug('[AudioEngineControls] Auto-start failed', err);
    });
  }, [engine, canAutoStart]);

  const toggle = async () => {
    if (!engine) return;
    try {
      if (engine.state.isPlaying) {
        engine.stopEngine();
        engine.playShutdown();
        return;
      }
      setStarting(true);
      await engine.startEngine();
      engine.playStartup();
    } finally {
      setStarting(false);
    }
  };

  return (
    <div className={`flex items-center gap-2 ${compact ? '' : 'p-2 rounded-md bg-zinc-900/40 border border-zinc-800/60'}`}>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={() => {
          void toggle();
        }}
        disabled={!engine || starting}
        className={`h-6 px-2 text-xs ${isPlaying ? 'bg-green-500/15 text-green-300 hover:bg-green-500/25' : 'bg-zinc-800/60 text-zinc-300 hover:bg-zinc-700/70'}`}
        title={engine?.state?.error ? `Audio error: ${engine.state.error}` : (isPlaying ? 'Stop engine sound' : 'Start engine sound')}
      >
        <Power className={`w-3.5 h-3.5 mr-1.5 ${isPlaying ? 'text-green-400' : 'text-zinc-400'}`} />
        {isPlaying ? 'On' : 'Off'}
      </Button>

      {!compact && (
        <div className="text-[10px] text-zinc-500 tabular-nums">
          {Math.round(rpm)} RPM • {Math.round(load * 100)}%
        </div>
      )}
    </div>
  );
}


