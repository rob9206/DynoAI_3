import { useState, useCallback } from 'react';
import { Check, Loader2, RotateCcw, Upload } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { ConfirmationDialog } from './ConfirmationDialog';
import { ApplyConfirmationContent } from './ApplyConfirmationContent';
import { RollbackConfirmationContent } from './RollbackConfirmationContent';
import { cn } from '@/lib/utils';
import { useIsMobile } from '@/hooks/use-mobile';

interface ApplyRollbackControlsProps {
  runId: string;
  status: 'idle' | 'applying' | 'rolling_back' | 'success' | 'error';
  canApply: boolean;
  canRollback: boolean;
  lastApplied?: string;
  lastRolledBack?: string;
  onApply: () => Promise<void>;
  onRollback: () => Promise<void>;
  applySummary?: {
    cellsToCorrect: number;
    maxCorrection: number;
    clampedCells: number;
    coveragePercent?: number;
  };
  className?: string;
}

export function ApplyRollbackControls({
  runId,
  status,
  canApply,
  canRollback,
  lastApplied,
  onApply,
  onRollback,
  applySummary,
  className,
}: ApplyRollbackControlsProps): JSX.Element {
  const [applyDialogOpen, setApplyDialogOpen] = useState(false);
  const [rollbackDialogOpen, setRollbackDialogOpen] = useState(false);
  const isMobile = useIsMobile();

  const isApplying = status === 'applying';
  const isRollingBack = status === 'rolling_back';
  const isSuccess = status === 'success';
  const isError = status === 'error';
  const isLoading = isApplying || isRollingBack;

  const handleApplyClick = useCallback(() => {
    setApplyDialogOpen(true);
  }, []);

  const handleRollbackClick = useCallback(() => {
    setRollbackDialogOpen(true);
  }, []);

  const handleConfirmApply = useCallback(async () => {
    await onApply();
    setApplyDialogOpen(false);
  }, [onApply]);

  const handleConfirmRollback = useCallback(async () => {
    await onRollback();
    setRollbackDialogOpen(false);
  }, [onRollback]);

  const getApplyButtonContent = () => {
    if (isApplying) {
      return (
        <>
          <Loader2 className="h-4 w-4 animate-spin" />
          <span>Applying...</span>
        </>
      );
    }
    if (isSuccess && !canApply) {
      return (
        <>
          <Check className="h-4 w-4" />
          <span>Applied</span>
        </>
      );
    }
    return (
      <>
        <Upload className="h-4 w-4" />
        <span>Apply to ECU</span>
      </>
    );
  };

  const getRollbackButtonContent = () => {
    if (isRollingBack) {
      return (
        <>
          <Loader2 className="h-4 w-4 animate-spin" />
          <span>Rolling back...</span>
        </>
      );
    }
    return (
      <>
        <RotateCcw className="h-4 w-4" />
        <span>Rollback</span>
      </>
    );
  };

  const getApplyTooltip = () => {
    if (!canApply) return 'Already applied. Rollback first to re-apply.';
    return 'Apply VE corrections to the ECU';
  };

  const getRollbackTooltip = () => {
    if (!canRollback) return 'No changes to rollback';
    return 'Revert to previous VE table values';
  };

  return (
    <TooltipProvider>
      <div
        className={cn(
          'flex gap-3',
          isMobile ? 'flex-col' : 'flex-row',
          className
        )}
        role="group"
        aria-label="VE table operations"
      >
        <Tooltip>
          <TooltipTrigger asChild>
            <span className={isMobile ? 'w-full' : ''}>
              <Button
                onClick={handleApplyClick}
                disabled={!canApply || isLoading}
                className={cn(
                  'gap-2',
                  isMobile ? 'w-full' : '',
                  isSuccess &&
                    !canApply &&
                    'bg-green-600 hover:bg-green-700',
                  isError && 'border-destructive'
                )}
                aria-busy={isApplying}
                aria-disabled={!canApply || isLoading}
              >
                {getApplyButtonContent()}
              </Button>
            </span>
          </TooltipTrigger>
          <TooltipContent>
            <p>{getApplyTooltip()}</p>
          </TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger asChild>
            <span className={isMobile ? 'w-full' : ''}>
              <Button
                variant="outline"
                onClick={handleRollbackClick}
                disabled={!canRollback || isLoading}
                className={cn('gap-2', isMobile ? 'w-full' : '')}
                aria-busy={isRollingBack}
                aria-disabled={!canRollback || isLoading}
              >
                {getRollbackButtonContent()}
              </Button>
            </span>
          </TooltipTrigger>
          <TooltipContent>
            <p>{getRollbackTooltip()}</p>
          </TooltipContent>
        </Tooltip>

        {/* Apply Confirmation Dialog */}
        <ConfirmationDialog
          open={applyDialogOpen}
          onOpenChange={setApplyDialogOpen}
          title="Apply VE Corrections"
          description="Review the correction summary before applying to your ECU."
          confirmLabel="Apply to ECU"
          cancelLabel="Cancel"
          variant="warning"
          onConfirm={handleConfirmApply}
          isLoading={isApplying}
        >
          {applySummary && (
            <ApplyConfirmationContent
              summary={{
                ...applySummary,
                coveragePercent: applySummary.coveragePercent ?? 0,
              }}
            />
          )}
        </ConfirmationDialog>

        {/* Rollback Confirmation Dialog */}
        <ConfirmationDialog
          open={rollbackDialogOpen}
          onOpenChange={setRollbackDialogOpen}
          title="Rollback VE Corrections"
          description="This will revert the VE table to its previous state."
          confirmLabel="Rollback"
          cancelLabel="Cancel"
          variant="destructive"
          onConfirm={handleConfirmRollback}
          isLoading={isRollingBack}
        >
          {lastApplied && (
            <RollbackConfirmationContent
              lastAppliedAt={lastApplied}
              originalRunId={runId}
            />
          )}
        </ConfirmationDialog>
      </div>
    </TooltipProvider>
  );
}
