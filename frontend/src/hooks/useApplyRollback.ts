import { useState, useCallback } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from '@/lib/toast';
import api from '@/lib/api';

interface UseApplyRollbackOptions {
  runId: string;
  onSuccess?: (action: 'apply' | 'rollback') => void;
  onError?: (action: 'apply' | 'rollback', error: Error) => void;
  initialCanApply?: boolean;
  initialCanRollback?: boolean;
  initialLastApplied?: string | null;
}

interface ApplyResponse {
  success: boolean;
  applied_at: string;
  cells_modified: number;
}

interface RollbackResponse {
  success: boolean;
  rolled_back_at: string;
}

interface UseApplyRollbackReturn {
  apply: () => Promise<void>;
  rollback: () => Promise<void>;
  status: 'idle' | 'applying' | 'rolling_back';
  error: Error | null;
  canApply: boolean;
  canRollback: boolean;
  lastApplied: string | null;
}

export function useApplyRollback({
  runId,
  onSuccess,
  onError,
  initialCanApply = true,
  initialCanRollback = false,
  initialLastApplied = null,
}: UseApplyRollbackOptions): UseApplyRollbackReturn {
  const queryClient = useQueryClient();
  const [lastApplied, setLastApplied] = useState<string | null>(initialLastApplied);
  const [canApply, setCanApply] = useState(initialCanApply);
  const [canRollback, setCanRollback] = useState(initialCanRollback);

  const applyMutation = useMutation({
    mutationFn: async (): Promise<ApplyResponse> => {
      const response = await api.post('/api/apply', { run_id: runId });
      return response.data as ApplyResponse;
    },
    onSuccess: (data) => {
      setLastApplied(data.applied_at);
      setCanApply(false);
      setCanRollback(true);

      toast.success('VE corrections applied', {
        description: `Successfully modified ${data.cells_modified} cells`,
      });

      void queryClient.invalidateQueries({ queryKey: ['ve-data', runId] });
      void queryClient.invalidateQueries({ queryKey: ['job-status', runId] });

      onSuccess?.('apply');
    },
    onError: (error: Error) => {
      toast.error('Failed to apply corrections', {
        description: error.message,
      });

      onError?.('apply', error);
    },
  });

  const rollbackMutation = useMutation({
    mutationFn: async (): Promise<RollbackResponse> => {
      const response = await api.post('/api/rollback', { run_id: runId });
      return response.data as RollbackResponse;
    },
    onSuccess: () => {
      setLastApplied(null);
      setCanApply(true);
      setCanRollback(false);

      toast.success('Rollback completed', {
        description: 'VE table restored to previous state',
      });

      void queryClient.invalidateQueries({ queryKey: ['ve-data', runId] });
      void queryClient.invalidateQueries({ queryKey: ['job-status', runId] });

      onSuccess?.('rollback');
    },
    onError: (error: Error) => {
      toast.error('Failed to rollback', {
        description: error.message,
      });

      onError?.('rollback', error);
    },
  });

  const apply = useCallback(async (): Promise<void> => {
    await applyMutation.mutateAsync();
  }, [applyMutation]);

  const rollback = useCallback(async (): Promise<void> => {
    await rollbackMutation.mutateAsync();
  }, [rollbackMutation]);

  const getStatus = (): 'idle' | 'applying' | 'rolling_back' => {
    if (applyMutation.isPending) return 'applying';
    if (rollbackMutation.isPending) return 'rolling_back';
    return 'idle';
  };

  const getError = (): Error | null => {
    if (applyMutation.error) return applyMutation.error;
    if (rollbackMutation.error) return rollbackMutation.error;
    return null;
  };

  return {
    apply,
    rollback,
    status: getStatus(),
    error: getError(),
    canApply,
    canRollback,
    lastApplied,
  };
}
