import { Link } from 'react-router-dom';
import { Settings2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

type ActiveView = 'command-center' | 'tuning';
type LiveSource = 'jetdrive' | 'yourdyno';

interface NavItem {
  label: string;
  to: string;
}

interface JetDriveTopBarProps {
  activeView: ActiveView;
  onViewChange: (view: ActiveView) => void;
  navItems: NavItem[];
  isRouteActive: (path: string) => boolean;
  activeLiveSource: LiveSource;
  onLiveSourceChange: (source: LiveSource) => void;
  isConnected: boolean;
  isCapturing: boolean;
  isSimulatorActive: boolean;
  isStartingSim: boolean;
  onToggleSimulator: () => void;
  onOpenHardware: () => void;
}

export function JetDriveTopBar({
  activeView,
  onViewChange,
  navItems,
  isRouteActive,
  activeLiveSource,
  onLiveSourceChange,
  isConnected,
  isCapturing,
  isSimulatorActive,
  isStartingSim,
  onToggleSimulator,
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
        <div className="w-px h-4 bg-zinc-700 mx-1" />
        {navItems.filter((item) => item.to !== '/jetdrive').map((item) => (
          <Link
            key={item.to}
            to={item.to}
            className={cn(
              'rounded-md px-3 py-2 transition-colors',
              isRouteActive(item.to)
                ? 'bg-zinc-800 text-white'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900',
            )}
          >
            {item.label}
          </Link>
        ))}
      </nav>

      <div className="flex items-center gap-4 text-xs text-zinc-300">
        <div className="flex items-center gap-1 rounded-full border border-zinc-800 bg-zinc-900/70 p-1">
          <Button
            type="button"
            variant={activeLiveSource === 'jetdrive' ? 'default' : 'ghost'}
            size="sm"
            className={cn(
              'h-7 px-3 text-[11px] font-semibold',
              activeLiveSource === 'jetdrive'
                ? 'bg-blue-600 text-white hover:bg-blue-500'
                : 'text-zinc-300 hover:text-white',
            )}
            onClick={() => onLiveSourceChange('jetdrive')}
          >
            JetDrive
          </Button>
          <Button
            type="button"
            variant={activeLiveSource === 'yourdyno' ? 'default' : 'ghost'}
            size="sm"
            className={cn(
              'h-7 px-3 text-[11px] font-semibold',
              activeLiveSource === 'yourdyno'
                ? 'bg-emerald-600 text-white hover:bg-emerald-500'
                : 'text-zinc-300 hover:text-white',
            )}
            onClick={() => onLiveSourceChange('yourdyno')}
          >
            YourDyno
          </Button>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={cn(
              'h-2 w-2 rounded-full',
              isConnected ? 'bg-green-500 animate-pulse' : 'bg-zinc-600',
            )}
          />
          <span>{isConnected ? 'Connected' : 'Disconnected'}</span>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={cn(
              'h-2 w-2 rounded-full',
              isCapturing ? 'bg-red-500 animate-pulse' : 'bg-zinc-600',
            )}
          />
          <span>Recording</span>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className={cn(
            'h-7 px-3 text-xs font-medium transition-colors',
            isSimulatorActive
              ? 'bg-yellow-500/20 text-yellow-400 hover:bg-yellow-500/30 border border-yellow-500/40'
              : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800',
            activeLiveSource === 'yourdyno' && 'opacity-60 cursor-not-allowed',
          )}
          onClick={onToggleSimulator}
          disabled={isStartingSim || activeLiveSource === 'yourdyno'}
        >
          {isStartingSim ? 'Starting...' : isSimulatorActive ? 'Sim ON' : 'Sim OFF'}
        </Button>
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
