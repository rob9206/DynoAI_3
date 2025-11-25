import { useMutation, useQueryClient } from '@tanstack/react-query';
import { baselineApi, BaselineResult } from '@/api/baseline';
import { toast } from 'sonner';

export function useGenerateBaseline() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (runId: string) => baselineApi.generate(runId),
    onSuccess: (data) => {
      if (data.status === 'ok') {
        toast.success('Baseline generated successfully', {
          description: `${data.summary.measured_cells} measured, ${data.summary.extrapolated_cells} extrapolated cells`
        });
        queryClient.invalidateQueries({ queryKey: ['runs'] });
      }
    },
    onError: (error: Error) => {
      toast.error('Baseline generation failed', {
        description: error.message
      });
    }
  });
}

export function usePreviewBaseline() {
  return useMutation({
    mutationFn: (runId: string) => baselineApi.preview(runId),
  });
}
