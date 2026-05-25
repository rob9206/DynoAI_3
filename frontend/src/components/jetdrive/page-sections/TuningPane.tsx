import { Suspense, type ComponentType } from 'react';
import { cn } from '@/lib/utils';

type ActiveView = 'command-center' | 'tuning';
export type TuningSubTab = 'base-map' | 'workspace';

interface TuningPaneProps {
  activeView: ActiveView;
  tuningSubTab: TuningSubTab;
  onTuningSubTabChange: (tab: TuningSubTab) => void;
  BaseMapComponent: ComponentType;
  WorkspaceComponent: ComponentType;
}

export function TuningPane({
  activeView,
  tuningSubTab,
  onTuningSubTabChange,
  BaseMapComponent,
  WorkspaceComponent,
}: TuningPaneProps) {
  return (
    <div className={cn('flex flex-1 flex-col min-h-0 bg-zinc-950', activeView !== 'tuning' && 'hidden')}>
      <div className="flex items-center gap-1 border-b border-zinc-800 px-6 py-2">
        <button
          type="button"
          onClick={() => onTuningSubTabChange('workspace')}
          className={cn(
            'rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
            tuningSubTab === 'workspace'
              ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30'
              : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800',
          )}
        >
          Workspace
        </button>
        <button
          type="button"
          onClick={() => onTuningSubTabChange('base-map')}
          className={cn(
            'rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
            tuningSubTab === 'base-map'
              ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
              : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800',
          )}
        >
          Base Map Explorer
        </button>
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto">
        <Suspense fallback={(
          <div className="flex items-center justify-center h-64 text-zinc-400 text-sm">
            Loading...
          </div>
        )}
        >
          <div className={cn('mx-auto w-full max-w-5xl px-6 py-6', tuningSubTab !== 'workspace' && 'hidden')}>
            <WorkspaceComponent />
          </div>
          <div className={cn('mx-auto max-w-6xl px-4 py-6', tuningSubTab !== 'base-map' && 'hidden')}>
            <BaseMapComponent />
          </div>
        </Suspense>
      </div>
    </div>
  );
}
