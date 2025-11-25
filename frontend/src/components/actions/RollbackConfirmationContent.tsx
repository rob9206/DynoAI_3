import { AlertTriangle, Clock, RotateCcw } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

interface RollbackConfirmationContentProps {
  lastAppliedAt: string;
  originalRunId?: string;
}

export function RollbackConfirmationContent({
  lastAppliedAt,
  originalRunId,
}: RollbackConfirmationContentProps): JSX.Element {
  const formattedDate = new Date(lastAppliedAt).toLocaleString();

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-border bg-muted/30 p-4 space-y-3">
        <div className="flex items-center gap-2 text-sm">
          <Clock className="h-4 w-4 text-muted-foreground" />
          <span className="text-muted-foreground">Last applied:</span>
          <span className="font-mono font-medium">{formattedDate}</span>
        </div>

        {originalRunId && (
          <div className="flex items-center gap-2 text-sm">
            <RotateCcw className="h-4 w-4 text-muted-foreground" />
            <span className="text-muted-foreground">Run ID:</span>
            <span className="font-mono text-xs">{originalRunId}</span>
          </div>
        )}
      </div>

      <Alert variant="default" className="border-blue-500/50 bg-blue-500/10">
        <AlertTriangle className="h-4 w-4 text-blue-500" />
        <AlertTitle className="text-blue-500">Reversible Operation</AlertTitle>
        <AlertDescription className="text-blue-400/80">
          This operation will restore the VE table to its previous state before
          the last apply. You can re-apply the corrections after rollback if
          needed.
        </AlertDescription>
      </Alert>

      <Alert variant="destructive">
        <AlertTriangle className="h-4 w-4" />
        <AlertTitle>Confirm Rollback</AlertTitle>
        <AlertDescription>
          This will revert the VE table to the values before the corrections
          were applied. Any tuning progress from the current session will be
          undone.
        </AlertDescription>
      </Alert>
    </div>
  );
}
