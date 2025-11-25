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
    <div className="flex items-center gap-3">
      {/* Connection indicator */}
      <div className="flex items-center gap-2">
        {isConnected ? (
          <>
            <div className="relative">
              <Wifi className="h-4 w-4 text-green-500" />
              {isProcessing && (
                <span className="absolute -top-1 -right-1 h-2 w-2 bg-green-500 rounded-full animate-pulse" />
              )}
            </div>
            <span className="text-sm text-muted-foreground">Jetstream</span>
          </>
        ) : (
          <>
            <WifiOff className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm text-muted-foreground">Offline</span>
          </>
        )}
      </div>

      {/* Pending runs badge */}
      {hasPending && (
        <Badge variant="secondary" className="text-xs">
          {status.pending_runs} pending
        </Badge>
      )}

      {/* Processing indicator */}
      {isProcessing && (
        <div className="flex items-center gap-1 text-sm text-muted-foreground">
          <Loader2 className="h-3 w-3 animate-spin" />
          <span>Processing</span>
        </div>
      )}

      {/* Error indicator */}
      {status.error && (
        <Badge variant="destructive" className="text-xs">
          Error
        </Badge>
      )}
    </div>
  );
}
