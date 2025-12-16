/**
 * Feed component showing Jetstream runs
 */

import { useState } from 'react';
import { RefreshCw, Filter, Loader2, Database } from 'lucide-react';
import { Button } from '../ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Skeleton } from '../ui/skeleton';
import { JetstreamRunCard } from './JetstreamRunCard';
import { JetstreamProcessingCard } from './JetstreamProcessingCard';
import { useJetstreamRuns, useJetstreamStatus } from '../../hooks/useJetstream';
import { useJetstreamProgress } from '../../hooks/useJetstreamProgress';
import type { RunStatus } from '../../api/jetstream';

interface JetstreamFeedProps {
  refetchInterval?: number;
}

export function JetstreamFeed({ refetchInterval = 30000 }: JetstreamFeedProps) {
  const [statusFilter, setStatusFilter] = useState<RunStatus | 'all'>('all');

  const { data: status } = useJetstreamStatus();
  const { data: runsData, isLoading, error, refetch, isRefetching } = useJetstreamRuns(
    statusFilter === 'all' ? undefined : { status: statusFilter },
    refetchInterval
  );

  // Subscribe to progress for currently processing run
  const processingRunId = status?.processing_run ?? undefined;
  const progress = useJetstreamProgress(processingRunId);

  const handleRefresh = () => {
    void refetch();
  };

  const handleFilterChange = (value: string) => {
    setStatusFilter(value as RunStatus | 'all');
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <Skeleton className="h-10 w-40 bg-muted/30" />
          <Skeleton className="h-10 w-24 bg-muted/30" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-48 rounded-lg bg-gradient-to-br from-muted/20 to-muted/5 border border-border/30 animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-16 border-dashed border-destructive/20 bg-destructive/5 rounded-xl relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(255,100,100,0.05)_0%,transparent_70%)] pointer-events-none" />
        <p className="text-destructive font-mono uppercase tracking-[0.2em] text-sm">Telemetry Link Failed</p>
        <Button variant="outline" onClick={handleRefresh} className="mt-4 border-destructive/30 hover:border-destructive/50 hover:bg-destructive/10 font-mono uppercase tracking-wider text-xs">
          Retry Connection
        </Button>
      </div>
    );
  }

  const runs = runsData?.runs ?? [];

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="flex flex-wrap justify-between items-center gap-4 bg-gradient-to-r from-card/40 via-card/30 to-card/40 p-3 rounded-lg border border-border/30 backdrop-blur-sm relative overflow-hidden">
        {/* Subtle glow effect */}
        <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/5 via-transparent to-cyan-500/5 pointer-events-none" />
        
        <div className="flex items-center gap-2 relative z-10">
          <Filter className="h-4 w-4 text-cyan-400/60" />
          <Select value={statusFilter} onValueChange={handleFilterChange}>
            <SelectTrigger className="w-40 font-mono text-xs h-8 border-border/40 bg-background/50 hover:border-cyan-500/40 transition-colors">
              <SelectValue placeholder="STATUS FILTER" />
            </SelectTrigger>
            <SelectContent className="bg-background/95 backdrop-blur-xl border-border/50">
              <SelectItem value="all" className="font-mono text-xs tracking-wider">ALL RECORDS</SelectItem>
              <SelectItem value="pending" className="font-mono text-xs tracking-wider">PENDING</SelectItem>
              <SelectItem value="processing" className="font-mono text-xs tracking-wider">PROCESSING</SelectItem>
              <SelectItem value="complete" className="font-mono text-xs tracking-wider">COMPLETE</SelectItem>
              <SelectItem value="error" className="font-mono text-xs tracking-wider">ERROR</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <Button variant="ghost" size="sm" onClick={handleRefresh} disabled={isRefetching} className="font-mono text-xs h-8 text-muted-foreground hover:text-cyan-400 tracking-wider relative z-10 transition-colors">
          {isRefetching ? (
            <Loader2 className="h-3 w-3 animate-spin mr-2" />
          ) : (
            <RefreshCw className="h-3 w-3 mr-2" />
          )}
          REFRESH FEED
        </Button>
      </div>

      {/* Processing card */}
      {processingRunId && (
        <JetstreamProcessingCard runId={processingRunId} progress={progress} />
      )}

      {/* Runs grid */}
      {runs.length === 0 ? (
        <div className="text-center py-20 bg-gradient-to-b from-muted/10 to-transparent rounded-xl border border-border/20 border-dashed relative overflow-hidden">
          {/* Decorative grid pattern */}
          <div className="absolute inset-0 bg-[linear-gradient(to_right,transparent_49.5%,rgba(100,200,255,0.03)_49.5%,rgba(100,200,255,0.03)_50.5%,transparent_50.5%)] bg-[length:40px_40px] pointer-events-none" />
          <div className="absolute inset-0 bg-[linear-gradient(to_bottom,transparent_49.5%,rgba(100,200,255,0.03)_49.5%,rgba(100,200,255,0.03)_50.5%,transparent_50.5%)] bg-[length:40px_40px] pointer-events-none" />
          
          <Database className="h-12 w-12 text-cyan-400/30 mx-auto mb-4" />
          <p className="text-muted-foreground font-mono uppercase tracking-[0.2em] text-sm">No Data Packets Found</p>
          <p className="text-xs text-muted-foreground/50 mt-2 font-mono tracking-wider">
            {statusFilter !== 'all'
              ? 'ADJUST FILTER PARAMETERS'
              : 'INITIATE SYNC TO RETRIEVE RECORDS'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {runs.map((run) => (
            <JetstreamRunCard key={run.run_id} run={run} />
          ))}
        </div>
      )}

      {/* Total count */}
      {runsData && (
        <p className="text-[10px] text-cyan-400/40 text-center font-mono uppercase tracking-[0.25em]">
          Displaying {runs.length} / {runsData.total} Records
        </p>
      )}
    </div>
  );
}
