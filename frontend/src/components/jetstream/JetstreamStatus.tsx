/**
 * Jetstream connection status indicator
 */

import { Wifi, WifiOff, Loader2 } from 'lucide-react';
import { Badge } from '../ui/badge';
import { Skeleton } from '../ui/skeleton';
import { useJetstreamStatus } from '../../hooks/useJetstream';

export function JetstreamStatus() {
  const { data: status, isLoading, error } = useJetstreamStatus();

  if (isLoading) {
    return (
      <div className="flex items-center gap-2">
        <Skeleton className="h-4 w-4 rounded-full" />
        <Skeleton className="h-5 w-24" />
      </div>
    );
  }

  if (error ?? !status) {
    return (
      <div className="flex items-center gap-2">
        <WifiOff className="h-4 w-4 text-destructive" />
        <span className="text-sm text-muted-foreground">Disconnected</span>
      </div>
    );
  }

  const isConnected = status.connected;
  const hasPending = status.pending_runs > 0;
  const isProcessing = !!status.processing_run;

  return (
    <div className="flex items-center gap-3 px-3 py-1.5 rounded-full bg-card/30 border border-border/30">
      {/* Connection indicator */}
      <div className="flex items-center gap-2">
            {isConnected ? (
          <>
            <div className="relative">
              <Wifi className="h-4 w-4 text-emerald-400" />
              {isProcessing && (
                <span className="absolute -top-1 -right-1 h-2 w-2 bg-emerald-400 rounded-full animate-pulse shadow-[0_0_4px_rgba(52,211,153,0.3)]" />
              )}
            </div>
            <span className="text-xs text-muted-foreground font-mono uppercase tracking-wider">Jetstream</span>
          </>
        ) : (
          <>
            <WifiOff className="h-4 w-4 text-muted-foreground/50" />
            <span className="text-xs text-muted-foreground/60 font-mono uppercase tracking-wider">Offline</span>
          </>
        )}
      </div>

      {/* Pending runs badge */}
      {hasPending && (
        <Badge variant="secondary" className="text-[10px] font-mono uppercase tracking-wider bg-amber-500/10 text-amber-400/80 border-amber-500/20">
          {status.pending_runs} pending
        </Badge>
      )}

      {/* Processing indicator */}
      {isProcessing && (
        <div className="flex items-center gap-1.5 text-xs text-cyan-400/70 font-mono uppercase tracking-wider">
          <Loader2 className="h-3 w-3 animate-spin" />
          <span>Processing</span>
        </div>
      )}

      {/* Error indicator */}
      {status.error && (
        <Badge variant="destructive" className="text-[10px] font-mono uppercase tracking-wider">
          Error
        </Badge>
      )}
    </div>
  );
}
