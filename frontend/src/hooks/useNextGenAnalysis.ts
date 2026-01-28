/**
 * React Query hooks for NextGen Analysis API
 * 
 * Provides:
 * - useNextGenAnalysis: Query for cached analysis payload
 * - useGenerateNextGen: Mutation to generate analysis
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  getNextGenAnalysis, 
  generateNextGenAnalysis,
  type NextGenAnalysisPayload,
  type NextGenGenerateResponse,
} from '@/lib/api';
import { AxiosError } from 'axios';

/** Query key factory for NextGen queries */
export const nextGenKeys = {
  all: ['nextgen'] as const,
  analysis: (runId: string) => [...nextGenKeys.all, 'analysis', runId] as const,
  surfaces: (runId: string) => [...nextGenKeys.all, 'surfaces', runId] as const,
  hypotheses: (runId: string) => [...nextGenKeys.all, 'hypotheses', runId] as const,
};

/**
 * Hook to fetch cached NextGen analysis payload
 * 
 * Handles 404 gracefully (returns undefined, not an error state)
 * to allow the UI to show "Generate" button instead of error.
 */
export function useNextGenAnalysis(runId: string | undefined) {
  return useQuery({
    queryKey: nextGenKeys.analysis(runId ?? ''),
    queryFn: async (): Promise<NextGenAnalysisPayload | null> => {
      if (!runId) throw new Error('Run ID is required');
      try {
        return await getNextGenAnalysis(runId);
      } catch (error) {
        // Return null for 404 (not generated yet) instead of throwing
        if (error instanceof AxiosError && error.response?.status === 404) {
          return null;
        }
        throw error;
      }
    },
    enabled: !!runId,
    staleTime: 5 * 60 * 1000, // 5 minutes - analysis doesn't change often
    retry: (failureCount, error) => {
      // Don't retry 404s
      if (error instanceof AxiosError && error.response?.status === 404) {
        return false;
      }
      return failureCount < 2;
    },
  });
}

interface GenerateOptions {
  force?: boolean;
  includeFull?: boolean;
}

/**
 * Hook to generate NextGen analysis
 * 
 * Automatically invalidates the analysis query on success.
 */
export function useGenerateNextGen(runId: string | undefined) {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (options?: GenerateOptions): Promise<NextGenGenerateResponse> => {
      if (!runId) throw new Error('Run ID is required');
      return await generateNextGenAnalysis(runId, options);
    },
    onSuccess: (data) => {
      if (runId) {
        // If we got the full payload, set it directly in cache
        if (data.payload) {
          queryClient.setQueryData(nextGenKeys.analysis(runId), data.payload);
        } else {
          // Otherwise invalidate to trigger a refetch
          queryClient.invalidateQueries({ queryKey: nextGenKeys.analysis(runId) });
        }
      }
    },
  });
}

/**
 * Combined hook for convenience
 * 
 * Returns both the query state and generate mutation.
 */
export function useNextGen(runId: string | undefined) {
  const query = useNextGenAnalysis(runId);
  const mutation = useGenerateNextGen(runId);
  
  return {
    // Query state
    data: query.data,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    
    // Computed state
    hasAnalysis: query.data !== null && query.data !== undefined,
    isNotGenerated: query.data === null,
    
    // Mutation
    generate: mutation.mutate,
    generateAsync: mutation.mutateAsync,
    isGenerating: mutation.isPending,
    generateError: mutation.error,
    
    // Refetch
    refetch: query.refetch,
  };
}
