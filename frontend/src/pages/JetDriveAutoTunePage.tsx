import { useState, lazy } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useJetDriveLive } from '@/hooks/useJetDriveLive';
import {
  HardwareStatusProvider,
  useHardwareStatusContext,
} from '@/hooks/HardwareStatusContext';
import { JetDriveTopBar } from '@/components/jetdrive/page-sections/JetDriveTopBar';
import { CommandCenterPane } from '@/components/jetdrive/page-sections/CommandCenterPane';
import { TuningPane, type TuningSubTab } from '@/components/jetdrive/page-sections/TuningPane';
import { WorkspaceBrowser } from '@/components/workspace/WorkspaceBrowser';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:5001';
const API_BASE = `${API_BASE_URL}/api/jetdrive`;

const EmbeddedWorkspace = () => <WorkspaceBrowser showHeader={false} />;

const LazyBaseMapGenerator = lazy(() =>
  import('@/components/jetdrive/BaseMapGenerator').then((m) => ({ default: m.BaseMapGenerator })),
);

type ActiveView = 'command-center' | 'tuning';

function JetDriveAutoTunePageInner() {
  const [searchParams] = useSearchParams();
  const initialView: ActiveView = searchParams.get('view') === 'tuning' ? 'tuning' : 'command-center';
  const [hardwareOpen, setHardwareOpen] = useState(false);
  const [activeView, setActiveView] = useState<ActiveView>(initialView);
  const [tuningSubTab, setTuningSubTab] = useState<TuningSubTab>('workspace');

  const jetdriveLive = useJetDriveLive({
    apiUrl: API_BASE,
    autoConnect: true,
    pollInterval: 800,
    useSse: true,
    enableDrain: true,
  });

  // Top-line connection state comes from the shared hardware-status
  // context so the JetDrive header reflects the same truth as the Channel
  // Health Board and the Mapping Confidence panel. ``useJetDriveLive``
  // still owns the live channel/sample stream that the Command Center
  // renders.
  const { status: unifiedStatus } = useHardwareStatusContext();
  const isConnected =
    unifiedStatus !== null
      ? unifiedStatus.provider.connected || unifiedStatus.capture.capturing
      : jetdriveLive.isConnected;

  return (
    <div className="flex h-full flex-col">
      <JetDriveTopBar
        activeView={activeView}
        onViewChange={setActiveView}
        isConnected={isConnected}
        onOpenHardware={() => setHardwareOpen(true)}
      />

      <CommandCenterPane
        activeView={activeView}
        live={jetdriveLive}
        hardwareOpen={hardwareOpen}
        onHardwareOpenChange={setHardwareOpen}
      />
      <TuningPane
        activeView={activeView}
        tuningSubTab={tuningSubTab}
        onTuningSubTabChange={setTuningSubTab}
        BaseMapComponent={LazyBaseMapGenerator}
        WorkspaceComponent={EmbeddedWorkspace}
      />
    </div>
  );
}

export default function JetDriveAutoTunePage() {
  return (
    <HardwareStatusProvider apiUrl={API_BASE}>
      <JetDriveAutoTunePageInner />
    </HardwareStatusProvider>
  );
}
