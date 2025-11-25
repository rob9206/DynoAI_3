/**
 * Card component for displaying a Jetstream run
 */

import { Link } from 'react-router-dom';
import { Clock, FileText, ChevronRight, AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import type { JetstreamRun, RunStatus } from '../../api/jetstream';

interface JetstreamRunCardProps {
  run: JetstreamRun;
}

const statusConfig: Record<RunStatus, { label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline'; icon: React.ComponentType<{ className?: string }> }> = {
  pending: { label: 'Pending', variant: 'outline', icon: Clock },
  downloading: { label: 'Downloading', variant: 'secondary', icon: Loader2 },
  converting: { label: 'Converting', variant: 'secondary', icon: Loader2 },
  validating: { label: 'Validating', variant: 'secondary', icon: Loader2 },
  processing: { label: 'Processing', variant: 'default', icon: Loader2 },
  complete: { label: 'Complete', variant: 'default', icon: CheckCircle2 },
  error: { label: 'Error', variant: 'destructive', icon: AlertCircle },
};

export function JetstreamRunCard({ run }: JetstreamRunCardProps) {
  const status = statusConfig[run.status] ?? statusConfig.pending;
  const StatusIcon = status.icon;
  const isProcessing = ['downloading', 'converting', 'validating', 'processing'].includes(run.status);

  // Format timestamp
  const timestamp = run.created_at ? new Date(run.created_at).toLocaleString() : 'Unknown';

  // Get vehicle from metadata if available
  const vehicle = run.jetstream_metadata?.vehicle ?? 'Unknown Vehicle';

  return (
    <Card className="hover:border-primary/50 transition-colors">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <CardTitle className="text-base font-medium">
              {run.run_id.length > 20 ? `${run.run_id.substring(0, 20)}...` : run.run_id}
            </CardTitle>
            <p className="text-sm text-muted-foreground">{vehicle}</p>
          </div>
          <Badge variant={status.variant} className="flex items-center gap-1">
            <StatusIcon className={`h-3 w-3 ${isProcessing ? 'animate-spin' : ''}`} />
            {status.label}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {/* Timestamp */}
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Clock className="h-4 w-4" />
            <span>{timestamp}</span>
          </div>

          {/* Source badge */}
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-xs">
              {run.source === 'jetstream' ? 'Jetstream' : 'Manual Upload'}
            </Badge>
            {run.jetstream_id && (
              <span className="text-xs text-muted-foreground">
                JS: {run.jetstream_id.substring(0, 8)}...
              </span>
            )}
          </div>

          {/* Progress for processing runs */}
          {isProcessing && run.progress_percent !== undefined && (
            <div className="space-y-1">
              <div className="flex justify-between text-xs">
                <span>{run.current_stage ?? 'Processing'}</span>
                <span>{run.progress_percent}%</span>
              </div>
              <div className="h-1.5 bg-secondary rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary transition-all duration-300"
                  style={{ width: `${run.progress_percent}%` }}
                />
              </div>
            </div>
          )}

          {/* Results summary for complete runs */}
          {run.status === 'complete' && run.results_summary && (
            <div className="flex items-center gap-2 text-sm">
              <FileText className="h-4 w-4 text-muted-foreground" />
              <span>Analysis complete</span>
            </div>
          )}

          {/* Error message */}
          {run.error && (
            <p className="text-sm text-destructive">{run.error.message}</p>
          )}

          {/* View button */}
          <Button asChild variant="ghost" className="w-full justify-between">
            <Link to={`/runs/${run.run_id}`}>
              View Details
              <ChevronRight className="h-4 w-4" />
            </Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
