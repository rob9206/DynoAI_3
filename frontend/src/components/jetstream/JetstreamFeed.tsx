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
          <Skeleton className="h-10 w-40" />
          <Skeleton className="h-10 w-24" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-48" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12 border-dashed border-border/50 bg-card/20 rounded-lg">
        <p className="text-destructive font-mono uppercase tracking-wide">Telemetry Link Failed</p>
        <Button variant="outline" onClick={handleRefresh} className="mt-4 border-destructive/30 hover:border-destructive/60">
          Retry Connection
        </Button>
      </div>
    );
  }

  const runs = runsData?.runs ?? [];

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="flex flex-wrap justify-between items-center gap-4 bg-card/30 p-3 rounded-lg border border-border/50 backdrop-blur-sm">
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <Select value={statusFilter} onValueChange={handleFilterChange}>
            <SelectTrigger className="w-40 font-mono text-xs h-8 border-border/50">
              <SelectValue placeholder="STATUS FILTER" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all" className="font-mono text-xs">ALL RECORDS</SelectItem>
              <SelectItem value="pending" className="font-mono text-xs">PENDING</SelectItem>
              <SelectItem value="processing" className="font-mono text-xs">PROCESSING</SelectItem>
              <SelectItem value="complete" className="font-mono text-xs">COMPLETE</SelectItem>
              <SelectItem value="error" className="font-mono text-xs">ERROR</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <Button variant="ghost" size="sm" onClick={handleRefresh} disabled={isRefetching} className="font-mono text-xs h-8 text-muted-foreground hover:text-primary">
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
        <div className="text-center py-16 bg-muted/10 rounded-lg border border-border/30 border-dashed">
          <Database className="h-12 w-12 text-muted-foreground mx-auto mb-4 opacity-50" />
          <p className="text-muted-foreground font-mono uppercase tracking-wider text-sm">No Data Packets Found</p>
          <p className="text-xs text-muted-foreground/60 mt-2 font-mono">
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
        <p className="text-[10px] text-muted-foreground text-center font-mono uppercase tracking-widest">
          Displaying {runs.length} / {runsData.total} Records
        </p>
      )}
    </div>
  );
}
