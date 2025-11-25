import { useState, useCallback } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ConfirmationDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'default' | 'destructive' | 'warning';
  onConfirm: () => void | Promise<void>;
  onCancel?: () => void;
  isLoading?: boolean;
  children?: React.ReactNode;
}

export function ConfirmationDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'default',
  onConfirm,
  onCancel,
  isLoading = false,
  children,
}: ConfirmationDialogProps): JSX.Element {
  const [internalLoading, setInternalLoading] = useState(false);
  const loading = isLoading || internalLoading;

  const handleConfirm = useCallback(async () => {
    try {
      setInternalLoading(true);
      await onConfirm();
    } finally {
      setInternalLoading(false);
    }
  }, [onConfirm]);

  const handleCancel = useCallback(() => {
    if (!loading) {
      onCancel?.();
      onOpenChange(false);
    }
  }, [loading, onCancel, onOpenChange]);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (event.key === 'Enter' && !loading) {
        event.preventDefault();
        void handleConfirm();
      }
    },
    [loading, handleConfirm]
  );

  const getConfirmButtonVariant = () => {
    if (variant === 'destructive') return 'destructive';
    return 'default';
  };

  return (
    <Dialog open={open} onOpenChange={loading ? undefined : onOpenChange}>
      <DialogContent
        onKeyDown={handleKeyDown}
        aria-describedby="confirmation-dialog-description"
      >
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription id="confirmation-dialog-description">
            {description}
          </DialogDescription>
        </DialogHeader>

        {children && <div className="py-4">{children}</div>}

        <DialogFooter
          className={cn(
            'flex flex-col-reverse gap-2 sm:flex-row sm:justify-end'
          )}
        >
          <Button
            type="button"
            variant="outline"
            onClick={handleCancel}
            disabled={loading}
          >
            {cancelLabel}
          </Button>
          <Button
            type="button"
            variant={getConfirmButtonVariant()}
            onClick={() => void handleConfirm()}
            disabled={loading}
            className={cn(
              variant === 'warning' &&
                'bg-amber-600 hover:bg-amber-700 text-white'
            )}
          >
            {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
