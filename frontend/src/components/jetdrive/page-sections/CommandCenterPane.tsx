import { cn } from '@/lib/utils';
import type { UseJetDriveLiveReturn } from '@/hooks/useJetDriveLive';
import { CommandCenter } from '@/components/jetdrive/CommandCenter';

type ActiveView = 'command-center' | 'tuning';

interface CommandCenterPaneProps {
  activeView: ActiveView;
  live: UseJetDriveLiveReturn;
  hardwareOpen: boolean;
  onHardwareOpenChange: (open: boolean) => void;
}

export function CommandCenterPane({
  activeView,
  live,
  hardwareOpen,
  onHardwareOpenChange,
}: CommandCenterPaneProps) {
  return (
    <div className={cn('flex flex-1 flex-col min-h-0', activeView !== 'command-center' && 'hidden')}>
      <div className="flex-1 min-h-0">
        <CommandCenter
          live={live}
          hardwareOpen={hardwareOpen}
          onHardwareOpenChange={onHardwareOpenChange}
        />
      </div>
    </div>
  );
}
