/**
 * Card showing active processing progress
 */

import { Loader2, AlertCircle, CheckCircle2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Progress } from '../ui/progress';
import type { ProgressState } from '../../hooks/useJetstreamProgress';

interface JetstreamProcessingCardProps {
  runId: string;
  progress: ProgressState;
}

const stageLabels: Record<string, string> = {
  downloading: 'Downloading data from Jetstream',
  converting: 'Converting to DynoAI format',
  validating: 'Validating input data',
  processing: 'Running analysis',
  complete: 'Analysis complete',
};

export function JetstreamProcessingCard({ runId, progress }: JetstreamProcessingCardProps) {
  const stageLabel = progress.stage ? (stageLabels[progress.stage] ?? progress.stage) : 'Initializing';
  const progressPercent = progress.progress ?? 0;

  return (
    <Card className="border-primary/50 bg-primary/5">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-lg">
          {progress.error ? (
            <AlertCircle className="h-5 w-5 text-destructive" />
          ) : progress.complete ? (
            <CheckCircle2 className="h-5 w-5 text-green-500" />
          ) : (
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
          )}
          {progress.complete ? 'Processing Complete' : 'Processing Run'}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Run ID */}
        <p className="text-sm text-muted-foreground font-mono">
          {runId}
        </p>

        {/* Progress bar */}
        {!progress.error && (
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span>{stageLabel}</span>
              <span>{progressPercent}%</span>
            </div>
            <Progress value={progressPercent} className="h-2" />
            {progress.substage && (
              <p className="text-xs text-muted-foreground">{progress.substage}</p>
            )}
          </div>
        )}

        {/* Error display */}
        {progress.error && (
          <div className="rounded-md bg-destructive/10 p-3 text-sm">
            <p className="font-medium text-destructive">
              Error in {progress.error.stage}: {progress.error.code}
            </p>
            <p className="mt-1 text-muted-foreground">{progress.error.message}</p>
          </div>
        )}

        {/* Connection status */}
        {!progress.connected && !progress.complete && !progress.error && (
          <p className="text-xs text-muted-foreground flex items-center gap-1">
            <Loader2 className="h-3 w-3 animate-spin" />
            Connecting to progress stream...
          </p>
        )}
      </CardContent>
    </Card>
  );
}
