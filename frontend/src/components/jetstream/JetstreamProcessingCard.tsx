/**
 * Card showing active processing progress
 */

import { Loader2, AlertCircle, CheckCircle2, Cpu } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Progress } from '../ui/progress';
import type { ProgressState } from '../../hooks/useJetstreamProgress';

interface JetstreamProcessingCardProps {
  runId: string;
  progress: ProgressState;
}

const stageLabels: Record<string, string> = {
  downloading: 'RETRIEVING PACKET',
  converting: 'FORMAT CONVERSION',
  validating: 'DATA VALIDATION',
  processing: 'ANALYSIS SEQUENCE',
  complete: 'SEQUENCE COMPLETE',
};

export function JetstreamProcessingCard({ runId, progress }: JetstreamProcessingCardProps) {
  const stageLabel = progress.stage ? (stageLabels[progress.stage] ?? progress.stage.toUpperCase()) : 'INITIALIZING';
  const progressPercent = progress.progress ?? 0;

  return (
    <Card className="border-primary/30 bg-primary/5 backdrop-blur-sm shadow-[0_0_15px_rgba(var(--primary),0.1)] animate-pulse-slow">
      <CardHeader className="pb-2 border-b border-primary/10">
        <CardTitle className="flex items-center gap-2 text-lg font-mono uppercase tracking-tight text-primary">
          {progress.error ? (
            <AlertCircle className="h-5 w-5 text-destructive" />
          ) : progress.complete ? (
            <CheckCircle2 className="h-5 w-5 text-green-500" />
          ) : (
            <Cpu className="h-5 w-5 animate-pulse text-primary" />
          )}
          {progress.complete ? 'Processing Complete' : 'Active Process Monitor'}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 pt-4">
        {/* Run ID */}
        <div className="flex justify-between items-center text-xs font-mono text-muted-foreground">
            <span className="uppercase tracking-wider">Target ID:</span>
            <span className="text-foreground">{runId}</span>
        </div>

        {/* Progress bar */}
        {!progress.error && (
          <div className="space-y-2">
            <div className="flex justify-between text-xs font-mono uppercase text-primary/80">
              <span>{stageLabel}</span>
              <span>{progressPercent}%</span>
            </div>
            <Progress value={progressPercent} className="h-2 bg-primary/20" />
            {progress.substage && (
              <p className="text-[10px] text-muted-foreground font-mono uppercase tracking-widest pl-1 border-l-2 border-primary/30">
                &gt; {progress.substage}
              </p>
            )}
          </div>
        )}

        {/* Error display */}
        {progress.error && (
          <div className="rounded bg-destructive/10 p-3 text-xs font-mono border border-destructive/30">
            <p className="font-bold text-destructive uppercase">
              Error in {progress.error.stage}: {progress.error.code}
            </p>
            <p className="mt-1 text-destructive/80">{progress.error.message}</p>
          </div>
        )}

        {/* Connection status */}
        {!progress.connected && !progress.complete && !progress.error && (
          <p className="text-[10px] text-muted-foreground flex items-center gap-2 font-mono uppercase tracking-wider">
            <Loader2 className="h-3 w-3 animate-spin" />
            Establishing Uplink...
          </p>
        )}
      </CardContent>
    </Card>
  );
}
