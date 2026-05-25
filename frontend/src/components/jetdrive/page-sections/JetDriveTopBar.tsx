import { Settings2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

type ActiveView = 'command-center' | 'tuning';

interface JetDriveTopBarProps {
  activeView: ActiveView;
  onViewChange: (view: ActiveView) => void;
  isConnected: boolean;
  onOpenHardware: () => void;
}

export function JetDriveTopBar({
  activeView,
  onViewChange,
  isConnected,
  onOpenHardware,
}: JetDriveTopBarProps) {
  return (
    <header className="flex h-12 items-center justify-between border-b border-zinc-800 bg-zinc-950 px-4">
      <div className="flex items-center gap-3">
        <div className="text-xs font-bold uppercase tracking-[0.2em] text-zinc-200">
          THUNDERHORSE
        </div>
        <div className="text-xs text-zinc-500">·</div>
        <div className="text-sm font-semibold text-zinc-100">DynoAI</div>
      </div>

      <nav className="flex items-center gap-2 text-xs">
        <button
          type="button"
          onClick={() => onViewChange('command-center')}
          className={cn(
            'rounded-md px-3 py-2 transition-colors font-medium',
            activeView === 'command-center'
              ? 'bg-zinc-800 text-white'
              : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900',
          )}
        >
          JetDrive
        </button>
        <button
          type="button"
          onClick={() => onViewChange('tuning')}
          className={cn(
            'rounded-md px-3 py-2 transition-colors font-medium',
            activeView === 'tuning'
              ? 'bg-zinc-800 text-white'
              : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900',
          )}
        >
          Tuning
        </button>
      </nav>

      <div className="flex items-center gap-4 text-xs text-zinc-300">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              'h-2 w-2 rounded-full',
              isConnected ? 'bg-green-500 animate-pulse' : 'bg-zinc-600',
            )}
          />
          <span>{isConnected ? 'Connected' : 'Disconnected'}</span>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-8 w-8 text-zinc-400 hover:text-zinc-200"
          onClick={onOpenHardware}
        >
          <Settings2 className="h-4 w-4" />
        </Button>
      </div>
    </header>
  );
}
