import { AlertTriangle } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

interface ApplyConfirmationContentProps {
  summary: {
    cellsToCorrect: number;
    maxCorrection: number;
    clampedCells: number;
    coveragePercent: number;
  };
}

export function ApplyConfirmationContent({
  summary,
}: ApplyConfirmationContentProps): JSX.Element {
  const { cellsToCorrect, maxCorrection, clampedCells, coveragePercent } =
    summary;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4 text-sm">
        <div className="space-y-1">
          <p className="text-muted-foreground">Cells to correct</p>
          <p className="font-mono font-medium text-lg">{cellsToCorrect}</p>
        </div>
        <div className="space-y-1">
          <p className="text-muted-foreground">Max correction</p>
          <p className="font-mono font-medium text-lg">
            {maxCorrection.toFixed(1)}%
          </p>
        </div>
        <div className="space-y-1">
          <p className="text-muted-foreground">Coverage</p>
          <p className="font-mono font-medium text-lg">
            {coveragePercent.toFixed(0)}%
          </p>
        </div>
        <div className="space-y-1">
          <p className="text-muted-foreground">Clamped cells</p>
          <p
            className={`font-mono font-medium text-lg ${
              clampedCells > 0 ? 'text-amber-500' : 'text-green-500'
            }`}
          >
            {clampedCells}
          </p>
        </div>
      </div>

      {clampedCells > 0 && (
        <Alert variant="default" className="border-amber-500/50 bg-amber-500/10">
          <AlertTriangle className="h-4 w-4 text-amber-500" />
          <AlertTitle className="text-amber-500">Clamped Values</AlertTitle>
          <AlertDescription className="text-amber-400/80">
            {clampedCells} cell{clampedCells > 1 ? 's were' : ' was'} clamped to
            the maximum allowed correction. Review these cells in the VE table
            visualization.
          </AlertDescription>
        </Alert>
      )}

      <Alert variant="destructive">
        <AlertTriangle className="h-4 w-4" />
        <AlertTitle>ECU Modification Warning</AlertTitle>
        <AlertDescription>
          This action will modify the VE table on your ECU. Make sure you have a
          backup of your current tune before proceeding. This operation can be
          rolled back if needed.
        </AlertDescription>
      </Alert>
    </div>
  );
}
