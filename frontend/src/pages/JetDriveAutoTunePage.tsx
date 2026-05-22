import { useState, useEffect, useCallback, useRef, lazy } from 'react';
import { useLocation } from 'react-router-dom';
import { toast } from '@/lib/toast';
import { useJetDriveLive } from '@/hooks/useJetDriveLive';
import { useYourDynoLive } from '@/hooks/useYourDynoLive';
import { JetDriveTopBar } from '@/components/jetdrive/page-sections/JetDriveTopBar';
import { CommandCenterPane } from '@/components/jetdrive/page-sections/CommandCenterPane';
import { TuningPane } from '@/components/jetdrive/page-sections/TuningPane';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:5001';
const API_BASE = `${API_BASE_URL}/api/jetdrive`;
const YOURDYNO_API_BASE = `${API_BASE_URL}/api/yourdyno`;

const NAV_ITEMS = [
  { label: 'Dashboard', to: '/dashboard' },
  { label: 'JetDrive', to: '/jetdrive' },
  { label: 'Results', to: '/results/last' },
  { label: 'History', to: '/history' },
];

const LazyV3TuningTab = lazy(() =>
  import('@/components/jetdrive/V3TuningTab').then((m) => ({ default: m.V3TuningTab })),
);
const LazyBaseMapGenerator = lazy(() =>
  import('@/components/jetdrive/BaseMapGenerator').then((m) => ({ default: m.BaseMapGenerator })),
);

type ActiveView = 'command-center' | 'tuning';
type TuningSubTab = 'base-map' | 'session';

export default function JetDriveAutoTunePage() {
  const location = useLocation();
  const [hardwareOpen, setHardwareOpen] = useState(false);
  const [isSimulatorActive, setIsSimulatorActive] = useState(false);
  const [isStartingSim, setIsStartingSim] = useState(false);
  const [isTriggeringPull, setIsTriggeringPull] = useState(false);
  const [simThrottle, setSimThrottle] = useState(0);
  const [activeLiveSource, setActiveLiveSource] = useState<'jetdrive' | 'yourdyno'>('jetdrive');
  const [activeView, setActiveView] = useState<ActiveView>('command-center');
  const [tuningSubTab, setTuningSubTab] = useState<TuningSubTab>('base-map');
  const simThrottleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const jetdriveLive = useJetDriveLive({
    apiUrl: API_BASE,
    autoConnect: true,
    pollInterval: 800,
    useSse: true,
    isSimulatorActive,
    enableDrain: activeLiveSource === 'jetdrive',
  });

  const yourdynoLive = useYourDynoLive({
    apiUrl: YOURDYNO_API_BASE,
    autoConnect: true,
    pollInterval: 800,
    useSse: true,
    isSimulatorActive: false,
    enableDrain: activeLiveSource === 'yourdyno',
  });

  const activeLive = activeLiveSource === 'yourdyno' ? yourdynoLive : jetdriveLive;

  const isActive = (path: string) =>
    location.pathname === path || location.pathname.startsWith(`${path}/`);

  const stopSimulator = useCallback(
    async (silent?: boolean) => {
      try {
        await fetch(`${API_BASE}/simulator/stop`, { method: 'POST' });
        await jetdriveLive.clearChannels();
        setIsSimulatorActive(false);
        setSimThrottle(0);
        if (!silent) {
          toast.info('Simulator stopped');
        }
      } catch (error) {
        if (!silent) {
          toast.error('Failed to stop simulator');
        }
        console.error('Simulator stop error:', error);
      }
    },
    [jetdriveLive],
  );

  const handleToggleSimulator = async () => {
    if (activeLiveSource === 'yourdyno') {
      toast.info('Simulator is only available with JetDrive source.');
      return;
    }
    if (isSimulatorActive) {
      await stopSimulator();
      return;
    }

    setIsStartingSim(true);
    try {
      const res = await fetch(`${API_BASE}/simulator/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          profile: 'm8_114',
          virtual_ecu: { enabled: false },
          auto_pull: false,
        }),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
        throw new Error(errorData.error || `HTTP ${res.status}`);
      }

      const data = await res.json();
      if (data.success) {
        setIsSimulatorActive(true);
        toast.success(`Simulator started: ${data.profile?.name || 'M8 114'}`, {
          description: `${data.profile?.max_hp || 114} HP @ ${data.profile?.redline_rpm || 6200} RPM`,
        });
      } else {
        toast.error('Failed to start simulator', {
          description: data.error || 'Unknown error',
        });
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to start simulator';
      toast.error('Failed to start simulator', {
        description: errorMessage,
      });
      console.error('Simulator start error:', error);
    } finally {
      setIsStartingSim(false);
    }
  };

  useEffect(() => {
    if (activeLiveSource === 'yourdyno' && isSimulatorActive) {
      void stopSimulator(true);
      toast.info('Simulator controls are only available with JetDrive source.');
    }
  }, [activeLiveSource, isSimulatorActive, stopSimulator]);

  const handleThrottleChange = (value: number) => {
    const clampedValue = Math.max(0, Math.min(100, value));
    setSimThrottle(clampedValue);

    if (simThrottleTimerRef.current) {
      clearTimeout(simThrottleTimerRef.current);
    }

    simThrottleTimerRef.current = setTimeout(async () => {
      simThrottleTimerRef.current = null;
      try {
        await fetch(`${API_BASE}/simulator/throttle`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tps: clampedValue }),
        });
      } catch (error) {
        console.error('Failed to set throttle:', error);
      }
    }, 100);
  };

  const handleTriggerPull = async () => {
    if (!isSimulatorActive) return;
    if (jetdriveLive.simState && jetdriveLive.simState !== 'idle') {
      toast.warning(`Cannot trigger pull while simulator is ${jetdriveLive.simState}`);
      return;
    }

    setIsTriggeringPull(true);
    try {
      const throttlePct = Math.round(simThrottle);

      await fetch(`${API_BASE}/simulator/throttle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tps: throttlePct }),
      });

      const res = await fetch(`${API_BASE}/simulator/pull`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ throttle: throttlePct, tps: throttlePct }),
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.success) {
        toast.error(data.error || 'Cannot start pull');
        return;
      }

      setTimeout(() => {
        fetch(`${API_BASE}/simulator/throttle`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tps: throttlePct }),
        }).catch(() => undefined);
      }, 80);

      window.dispatchEvent(
        new CustomEvent('dynoai:simulator-pull', {
          detail: { throttle: throttlePct },
        }),
      );
      toast.success(`Pull started at ${throttlePct}% throttle`);
    } catch (error) {
      toast.error('Failed to trigger pull');
      console.error('Trigger pull error:', error);
    } finally {
      setIsTriggeringPull(false);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <JetDriveTopBar
        activeView={activeView}
        onViewChange={setActiveView}
        navItems={NAV_ITEMS}
        isRouteActive={isActive}
        activeLiveSource={activeLiveSource}
        onLiveSourceChange={setActiveLiveSource}
        isConnected={activeLive.isConnected}
        isCapturing={activeLive.isCapturing}
        isSimulatorActive={isSimulatorActive}
        isStartingSim={isStartingSim}
        onToggleSimulator={handleToggleSimulator}
        onOpenHardware={() => setHardwareOpen(true)}
      />

      <CommandCenterPane
        activeView={activeView}
        isSimulatorActive={isSimulatorActive}
        simThrottle={simThrottle}
        onThrottleChange={handleThrottleChange}
        simulatorState={jetdriveLive.simState}
        isTriggeringPull={isTriggeringPull}
        onTriggerPull={handleTriggerPull}
        live={activeLive}
        hardwareOpen={hardwareOpen}
        onHardwareOpenChange={setHardwareOpen}
      />
      <TuningPane
        activeView={activeView}
        tuningSubTab={tuningSubTab}
        onTuningSubTabChange={setTuningSubTab}
        BaseMapComponent={LazyBaseMapGenerator}
        SessionComponent={LazyV3TuningTab}
      />
    </div>
  );
}
