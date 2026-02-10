import { useEffect, useRef, useState } from 'react';
import { toast } from '@/lib/toast';
import { cn } from '../../lib/utils';
import { useJetDriveLive, type UseJetDriveLiveReturn } from '../../hooks/useJetDriveLive';
import { DEFAULT_AFR_TARGETS } from './AFRTargetTable';
import { TelemetryStrip } from './TelemetryStrip';
import { SafetyStrip } from './SafetyStrip';
import { VEHeatmapPanel } from './VEHeatmapPanel';
import { SessionBar } from './SessionBar';
import { AICoach } from './AICoach';
import { HardwareSlideOver } from './HardwareSlideOver';

type Cylinder = 'front' | 'rear';

interface CommandCenterProps {
  apiUrl?: string;
  live?: UseJetDriveLiveReturn;
  hardwareOpen?: boolean;
  onHardwareOpenChange?: (open: boolean) => void;
  className?: string;
}

function CommandCenterContent({
  apiUrl,
  live,
  hardwareOpen: hardwareOpenProp,
  onHardwareOpenChange,
  className,
}: CommandCenterProps & { live: UseJetDriveLiveReturn }) {

  const [activeCylinder, setActiveCylinder] = useState<Cylinder>('front');
  const [afrTargets, setAfrTargets] = useState<Record<number, number>>(DEFAULT_AFR_TARGETS);
  const [captureState, setCaptureState] = useState<'idle' | 'armed' | 'recording'>('idle');
  const [selectedPull, setSelectedPull] = useState<number | null>(null);
  const [localHardwareOpen, setLocalHardwareOpen] = useState(false);
  const [hitData, setHitData] = useState<{
    frontHits: number[][];
    rearHits: number[][];
    rpmBins: number[];
    mapBins: number[];
  } | null>(null);
  const hardwareOpen = hardwareOpenProp ?? localHardwareOpen;
  const setHardwareOpen = onHardwareOpenChange ?? setLocalHardwareOpen;
  const hasAutoOpenedHardware = useRef(false);

  useEffect(() => {
    if (!live.isConnected && !hardwareOpen && !hasAutoOpenedHardware.current) {
      hasAutoOpenedHardware.current = true;
      setHardwareOpen(true);
    }
  }, [hardwareOpen, live.isConnected]);

  useEffect(() => {
    if (live.isCapturing) {
      setCaptureState('recording');
    } else if (captureState === 'recording') {
      setCaptureState('idle');
    }
  }, [captureState, live.isCapturing]);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const isTyping =
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        (target?.getAttribute('contenteditable') === 'true');
      if (isTyping) return;

      if (event.key === 'Escape') {
        setHardwareOpen(false);
        return;
      }

      const isCtrl = event.ctrlKey || event.metaKey;
      if (!isCtrl) return;

      const key = event.key.toLowerCase();
      if (key === ' ') {
        event.preventDefault();
        setCaptureState((prev) => (prev === 'idle' ? 'armed' : 'idle'));
      } else if (key === 'h') {
        event.preventDefault();
        setHardwareOpen(true);
      } else if (key === 'f') {
        event.preventDefault();
        setActiveCylinder(event.shiftKey ? 'rear' : 'front');
      } else if (key === 'r') {
        event.preventDefault();
        window.dispatchEvent(new CustomEvent('dynoai:shortcut', { detail: { action: 'rollback' } }));
      } else if (key === 'e') {
        event.preventDefault();
        window.dispatchEvent(new CustomEvent('dynoai:shortcut', { detail: { action: 'export' } }));
      } else if (key === 'd') {
        event.preventDefault();
        window.dispatchEvent(new CustomEvent('dynoai:shortcut', { detail: { action: 'toggleDevToolbar' } }));
      } else if (key === '?' || (key === '/' && event.shiftKey)) {
        event.preventDefault();
        toast.info('Shortcuts: Ctrl+Space arm, Ctrl+H hardware, Ctrl+F front, Ctrl+Shift+F rear, Ctrl+R rollback, Ctrl+E export, Ctrl+D dev toolbar.');
      } else if (/^[1-9]$/.test(key)) {
        event.preventDefault();
        const pull = Number(key);
        setSelectedPull(pull);
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [setHardwareOpen]);

  return (
    <div className={cn('flex h-full w-full gap-4', className)}>
      <div className="flex min-w-0 flex-1 flex-col gap-3">
        <TelemetryStrip live={live} afrTargets={afrTargets} />
        <SafetyStrip live={live} />
        <div className="flex min-h-0 flex-1 flex-col">
          <VEHeatmapPanel
            live={live}
            afrTargets={afrTargets}
            activeCylinder={activeCylinder}
            onCylinderChange={setActiveCylinder}
            onHitCountsChange={(frontHits, rearHits, rpmBins, mapBins) => {
              setHitData({ frontHits, rearHits, rpmBins, mapBins });
            }}
            className="flex-1 min-h-0"
          />
          <SessionBar
            className="mt-0"
            selectedPull={selectedPull}
            captureState={captureState}
            onCaptureStateChange={setCaptureState}
            onSelectPull={(pull) => setSelectedPull(pull)}
          />
        </div>
      </div>

      <div className="w-[330px] shrink-0 max-[1440px]:w-[286px]">
        <AICoach
          activeCylinder={activeCylinder}
          onCylinderChange={setActiveCylinder}
          afrTargets={afrTargets}
          onAfrTargetsChange={setAfrTargets}
          hitData={hitData}
          onExport={() => {
            toast.info('Export is not wired to a run yet.');
          }}
        />
      </div>

      <HardwareSlideOver apiUrl={apiUrl} open={hardwareOpen} onOpenChange={setHardwareOpen} />
    </div>
  );
}

function CommandCenterWithLive({
  apiUrl = 'http://127.0.0.1:5001/api/jetdrive',
  hardwareOpen,
  onHardwareOpenChange,
  className,
}: Omit<CommandCenterProps, 'live'>) {
  const live = useJetDriveLive({
    apiUrl,
    autoConnect: true,
    pollInterval: 800,
    useSse: true,
  });

  return (
    <CommandCenterContent
      apiUrl={apiUrl}
      live={live}
      hardwareOpen={hardwareOpen}
      onHardwareOpenChange={onHardwareOpenChange}
      className={className}
    />
  );
}

export function CommandCenter(props: CommandCenterProps) {
  if (props.live) {
    return <CommandCenterContent {...props} live={props.live} />;
  }

  return <CommandCenterWithLive {...props} />;
}
