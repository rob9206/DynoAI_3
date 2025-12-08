/**
 * Card component for displaying a Jetstream run
 */

import { Link } from 'react-router-dom';
import { Clock, FileText, ChevronRight, AlertCircle, CheckCircle2, Loader2, Car, FileCode } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import type { JetstreamRun, RunStatus } from '../../api/jetstream';

interface JetstreamRunCardProps {
  run: JetstreamRun;
}

const statusConfig: Record<RunStatus, { label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline'; icon: React.ComponentType<{ className?: string }> }> = {
  pending: { label: 'PENDING', variant: 'outline', icon: Clock },
  downloading: { label: 'DOWNLOADING', variant: 'secondary', icon: Loader2 },
  converting: { label: 'CONVERTING', variant: 'secondary', icon: Loader2 },
  validating: { label: 'VALIDATING', variant: 'secondary', icon: Loader2 },
  processing: { label: 'PROCESSING', variant: 'default', icon: Loader2 },
  complete: { label: 'COMPLETE', variant: 'default', icon: CheckCircle2 },
  error: { label: 'ERROR', variant: 'destructive', icon: AlertCircle },
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
    <Card className="border-border/50 bg-card/30 backdrop-blur-sm hover:border-primary/50 hover:bg-card/50 transition-all duration-300 overflow-hidden group">
      <div className="absolute left-0 top-0 w-1 h-full bg-primary/0 group-hover:bg-primary/50 transition-all duration-300"></div>
      <CardHeader className="pb-2 pl-5">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <CardTitle className="text-sm font-bold font-mono uppercase tracking-tight text-foreground">
              {run.run_id.length > 20 ? `${run.run_id.substring(0, 20)}...` : run.run_id}
            </CardTitle>
            <p className="text-xs text-muted-foreground flex items-center gap-1 font-mono uppercase tracking-wide">
                <Car className="h-3 w-3 opacity-70" />
                {vehicle}
            </p>
          </div>
          <Badge variant={status.variant} className="flex items-center gap-1 font-mono text-[10px] uppercase tracking-wider">
            <StatusIcon className={`h-3 w-3 ${isProcessing ? 'animate-spin' : ''}`} />
            {status.label}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="pl-5">
        <div className="space-y-3">
          {/* Timestamp */}
          <div className="flex items-center gap-2 text-xs text-muted-foreground font-mono">
            <Clock className="h-3 w-3 opacity-70" />
            <span>{timestamp}</span>
          </div>

          {/* Source badge */}
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-[10px] font-mono uppercase border-border/50 text-muted-foreground">
              {run.source === 'jetstream' ? 'Cloud Link' : 'Local'}
            </Badge>
            {run.jetstream_id && (
              <span className="text-[10px] text-muted-foreground/50 font-mono uppercase">
                JSID: {run.jetstream_id.substring(0, 8)}
              </span>
            )}
          </div>

          {/* Progress for processing runs */}
          {isProcessing && run.progress_percent !== undefined && (
            <div className="space-y-1 pt-2">
              <div className="flex justify-between text-[10px] font-mono uppercase text-muted-foreground">
                <span>{run.current_stage ?? 'Processing'}</span>
                <span>{run.progress_percent}%</span>
              </div>
              <div className="h-1 bg-secondary/50 rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary transition-all duration-300"
                  style={{ width: `${run.progress_percent}%` }}
                />
              </div>
            </div>
          )}

          {/* Results summary for complete runs */}
          {run.status === 'complete' && run.results_summary && (
            <div className="flex items-center gap-2 text-xs text-green-500/80 font-mono uppercase tracking-wide pt-1">
              <FileCode className="h-3 w-3" />
              <span>Artifacts Generated</span>
            </div>
          )}

          {/* Error message */}
          {run.error && (
            <p className="text-xs text-destructive font-mono mt-2 border-l-2 border-destructive pl-2 py-1 bg-destructive/5">
                {run.error.message}
            </p>
          )}

          {/* View button */}
          <Button asChild variant="ghost" className="w-full justify-between mt-2 h-8 hover:bg-primary/10 hover:text-primary group-hover:translate-x-1 transition-all duration-300">
            <Link to={`/runs/${run.run_id}`} className="text-xs font-mono uppercase tracking-wider">
              Access Data
              <ChevronRight className="h-3 w-3" />
            </Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
