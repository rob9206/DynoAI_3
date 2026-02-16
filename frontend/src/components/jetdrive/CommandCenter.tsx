import { useEffect, useRef, useState } from 'react';
import { Settings } from 'lucide-react';
import { toast } from '@/lib/toast';
import { downloadAllFormats } from '@/utils/veExport';
import { cn } from '../../lib/utils';
import { useJetDriveLive, type UseJetDriveLiveReturn } from '../../hooks/useJetDriveLive';
import type { LiveVEExportData } from './LiveVETable';
import { DEFAULT_AFR_TARGETS } from './AFRTargetTable';
import { TelemetryStrip } from './TelemetryStrip';
import { SafetyStrip } from './SafetyStrip';
import { VEHeatmapPanel } from './VEHeatmapPanel';
import { SessionBar } from './SessionBar';
import { AICoach } from './AICoach';
import { HardwareSlideOver } from './HardwareSlideOver';

const NAV_TABS = ['Dashboard', 'JetDrive', 'Results', 'History'] as const;

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
  const [currentRunId, setCurrentRunId] = useState<string | undefined>();
  const [liveExportData, setLiveExportData] = useState<LiveVEExportData | null>(null);
  const [targetMarker, setTargetMarker] = useState<{ rpm: number; map: number; label?: string } | null>(null);
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
    <div className={cn('flex h-full w-full flex-col overflow-hidden bg-zinc-950 text-zinc-50', className)}>
      {/* ── Top Header Bar ──────────────────────────────────────────── */}
      <header className="flex h-12 shrink-0 items-center border-b border-zinc-800 bg-zinc-950 px-4 gap-8">
        {/* Branding */}
        <div className="flex items-center gap-3">
          <span className="text-[15px] font-bold tracking-tight text-zinc-50">
            THUNDERHORSE
          </span>
          <span className="text-[13px] font-medium text-zinc-500">
            DynoAI
          </span>
        </div>

        {/* Nav tabs */}
        <nav className="flex gap-1">
          {NAV_TABS.map((tab) => (
            <button
              key={tab}
              type="button"
              className={cn(
                'px-4 py-1.5 text-xs font-medium transition-colors',
                tab === 'JetDrive'
                  ? 'bg-zinc-800 text-zinc-50'
                  : 'text-zinc-400 hover:text-zinc-300',
              )}
            >
              {tab}
            </button>
          ))}
        </nav>

        {/* Status indicators */}
        <div className="ml-auto flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className={cn(
              'h-2 w-2 rounded-full',
              live.isConnected ? 'bg-green-500' : 'bg-zinc-600',
            )} />
            <span className="text-xs text-zinc-400">
              {live.isConnected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
          {captureState === 'recording' && (
            <div className="flex items-center gap-2">
              <div className="h-2 w-2 rounded-full bg-red-500 animate-pulse" />
              <span className="text-xs text-zinc-400">Recording</span>
            </div>
          )}
          <button
            type="button"
            className="p-1.5 rounded transition-colors hover:bg-zinc-800"
            onClick={() => setHardwareOpen(true)}
            title="Hardware settings"
          >
            <Settings className="h-4 w-4 text-zinc-400" />
          </button>
        </div>
      </header>

      {/* ── Main Content ────────────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: telemetry + heatmap + session bar */}
        <div className="flex min-w-0 flex-1 flex-col">
          <TelemetryStrip live={live} afrTargets={afrTargets} />
          <SafetyStrip live={live} />
          <div className="flex min-h-0 flex-1 flex-col">
            <VEHeatmapPanel
              live={live}
              afrTargets={afrTargets}
              activeCylinder={activeCylinder}
              onCylinderChange={setActiveCylinder}
              targetMarker={targetMarker}
              onHitCountsChange={(frontHits, rearHits, rpmBins, mapBins) => {
                setHitData({ frontHits, rearHits, rpmBins, mapBins });
              }}
              onLiveDataUpdate={setLiveExportData}
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

        {/* Right: AI Coach sidebar */}
        <div className="w-[330px] shrink-0">
          <AICoach
            activeCylinder={activeCylinder}
            onCylinderChange={setActiveCylinder}
            afrTargets={afrTargets}
            onAfrTargetsChange={setAfrTargets}
            hitData={hitData}
            runId={currentRunId}
            onRunIdChange={setCurrentRunId}
            onTargetChange={setTargetMarker}
            onExport={() => {
              if (!liveExportData || liveExportData.totalHits <= 0) {
                toast.info('No VE correction data to export yet.');
                return;
              }
              downloadAllFormats(liveExportData, 'JetDrive_VE_Corrections');
              toast.success('Exported VE corrections (CSV, JSON, PVV).');
            }}
          />
        </div>
      </div>

      <HardwareSlideOver apiUrl={apiUrl} open={hardwareOpen} onOpenChange={setHardwareOpen} />

      {/* Keyboard shortcut helper — fixed bottom-left overlay */}
      <div className="fixed bottom-2 left-2 z-50 rounded bg-zinc-900/90 border border-zinc-800 px-2.5 py-1 text-[9px] text-zinc-500 pointer-events-none select-none">
        <span className="text-zinc-600">Ctrl+Space</span> arm{' · '}
        <span className="text-zinc-600">Ctrl+F</span> front{' · '}
        <span className="text-zinc-600">Ctrl+Shift+F</span> rear{' · '}
        <span className="text-zinc-600">Ctrl+H</span> hardware{' · '}
        <span className="text-zinc-600">Ctrl+R</span> rollback{' · '}
        <span className="text-zinc-600">Ctrl+E</span> export
      </div>
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
    pollInterval: 250,  // 250ms polling fallback; SSE is preferred (~20Hz event-driven)
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
