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
    <Card className="border-border/30 bg-gradient-to-br from-card/50 to-card/20 backdrop-blur-sm hover:border-cyan-500/30 hover:from-card/60 hover:to-card/30 transition-all duration-300 overflow-hidden group relative">
      {/* Left accent bar */}
      <div className="absolute left-0 top-0 w-0.5 h-full bg-gradient-to-b from-cyan-500/0 via-cyan-500/0 to-cyan-500/0 group-hover:from-cyan-400/40 group-hover:via-cyan-500/30 group-hover:to-cyan-400/40 transition-all duration-500"></div>
      
      {/* Subtle corner glow on hover */}
      <div className="absolute -top-8 -right-8 w-16 h-16 bg-cyan-400/0 group-hover:bg-cyan-400/5 rounded-full blur-xl transition-all duration-500 pointer-events-none"></div>
      
      <CardHeader className="pb-2 pl-5">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <CardTitle className="text-sm font-bold font-mono uppercase tracking-wide text-foreground/90 group-hover:text-foreground transition-colors">
              {run.run_id.length > 20 ? `${run.run_id.substring(0, 20)}...` : run.run_id}
            </CardTitle>
            <p className="text-xs text-muted-foreground/70 flex items-center gap-1.5 font-mono uppercase tracking-wider">
                <Car className="h-3 w-3 text-cyan-400/50" />
                {vehicle}
            </p>
          </div>
          <Badge variant={status.variant} className="flex items-center gap-1 font-mono text-[10px] uppercase tracking-[0.1em] border-border/50">
            <StatusIcon className={`h-3 w-3 ${isProcessing ? 'animate-spin' : ''}`} />
            {status.label}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="pl-5">
        <div className="space-y-3">
          {/* Timestamp */}
          <div className="flex items-center gap-2 text-xs text-muted-foreground/60 font-mono">
            <Clock className="h-3 w-3 text-cyan-400/40" />
            <span>{timestamp}</span>
          </div>

          {/* Source badge */}
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-[10px] font-mono uppercase tracking-wider border-cyan-500/20 text-cyan-400/60 bg-cyan-500/5">
              {run.source === 'jetstream' ? 'Cloud Link' : 'Local'}
            </Badge>
            {run.jetstream_id && (
              <span className="text-[10px] text-muted-foreground/40 font-mono uppercase tracking-wider">
                JSID: {run.jetstream_id.substring(0, 8)}
              </span>
            )}
          </div>

          {/* Progress for processing runs */}
          {isProcessing && run.progress_percent !== undefined && (
            <div className="space-y-1.5 pt-2">
              <div className="flex justify-between text-[10px] font-mono uppercase text-muted-foreground/70 tracking-wider">
                <span>{run.current_stage ?? 'Processing'}</span>
                <span className="text-cyan-400/70">{run.progress_percent}%</span>
              </div>
              <div className="h-1 bg-muted/30 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-cyan-500 to-cyan-400 transition-all duration-300 shadow-[0_0_4px_rgba(34,211,238,0.2)]"
                  style={{ width: `${run.progress_percent}%` }}
                />
              </div>
            </div>
          )}

          {/* Results summary for complete runs */}
          {run.status === 'complete' && run.results_summary && (
            <div className="flex items-center gap-2 text-xs text-emerald-400/70 font-mono uppercase tracking-wider pt-1">
              <FileCode className="h-3 w-3" />
              <span>Artifacts Generated</span>
            </div>
          )}

          {/* Error message */}
          {run.error && (
            <p className="text-xs text-destructive/90 font-mono mt-2 border-l-2 border-destructive/50 pl-2 py-1 bg-destructive/5 rounded-r">
                {run.error.message}
            </p>
          )}

          {/* View button */}
          <Button asChild variant="ghost" className="w-full justify-between mt-2 h-8 hover:bg-cyan-500/10 hover:text-cyan-400 group-hover:translate-x-0.5 transition-all duration-300">
            <Link to={`/runs/${run.run_id}`} className="text-xs font-mono uppercase tracking-[0.15em]">
              Access Data
              <ChevronRight className="h-3 w-3 group-hover:translate-x-0.5 transition-transform" />
            </Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
