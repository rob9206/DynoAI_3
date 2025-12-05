/**
 * Feed component showing Jetstream runs
 */

import { useState } from 'react';
import { RefreshCw, Filter, Loader2 } from 'lucide-react';
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
      <div className="text-center py-8">
        <p className="text-destructive">Failed to load runs</p>
        <Button variant="outline" onClick={handleRefresh} className="mt-4">
          Retry
        </Button>
      </div>
    );
  }

  const runs = runsData?.runs ?? [];

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="flex flex-wrap justify-between items-center gap-4">
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <Select value={statusFilter} onValueChange={handleFilterChange}>
            <SelectTrigger className="w-40">
              <SelectValue placeholder="Filter by status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Runs</SelectItem>
              <SelectItem value="pending">Pending</SelectItem>
              <SelectItem value="processing">Processing</SelectItem>
              <SelectItem value="complete">Complete</SelectItem>
              <SelectItem value="error">Error</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <Button variant="outline" size="sm" onClick={handleRefresh} disabled={isRefetching}>
          {isRefetching ? (
            <Loader2 className="h-4 w-4 animate-spin mr-2" />
          ) : (
            <RefreshCw className="h-4 w-4 mr-2" />
          )}
          Refresh
        </Button>
      </div>

      {/* Processing card */}
      {processingRunId && (
        <JetstreamProcessingCard runId={processingRunId} progress={progress} />
      )}

      {/* Runs grid */}
      {runs.length === 0 ? (
        <div className="text-center py-12 bg-muted/50 rounded-lg">
          <p className="text-muted-foreground">No runs found</p>
          <p className="text-sm text-muted-foreground mt-1">
            {statusFilter !== 'all'
              ? 'Try changing the filter or sync with Jetstream'
              : 'Connect to Jetstream or upload a file to get started'}
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
        <p className="text-sm text-muted-foreground text-center">
          Showing {runs.length} of {runsData.total} runs
        </p>
      )}
    </div>
  );
}
