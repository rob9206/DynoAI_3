/**
 * React hooks for Jetstream integration
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getJetstreamStatus,
  getJetstreamConfig,
  updateJetstreamConfig,
  listJetstreamRuns,
  getJetstreamRun,
  triggerJetstreamSync,
  type JetstreamStatus,
  type JetstreamConfig,
  type JetstreamRun,
  type ListRunsFilter,
  type ListRunsResponse,
  type SyncResponse,
} from '../api/jetstream';

/**
 * Hook to get Jetstream poller status with auto-refresh
 */
export function useJetstreamStatus(refetchInterval = 10000) {
  return useQuery<JetstreamStatus>({
    queryKey: ['jetstream', 'status'],
    queryFn: getJetstreamStatus,
    refetchInterval,
    staleTime: 5000,
  });
}

/**
 * Hook to get Jetstream configuration
 */
export function useJetstreamConfig() {
  return useQuery<JetstreamConfig>({
    queryKey: ['jetstream', 'config'],
    queryFn: getJetstreamConfig,
    staleTime: 60000,
  });
}

/**
 * Hook to update Jetstream configuration
 */
export function useUpdateJetstreamConfig() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (config: Partial<JetstreamConfig>) => updateJetstreamConfig(config),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['jetstream', 'config'] });
      void queryClient.invalidateQueries({ queryKey: ['jetstream', 'status'] });
    },
  });
}

/**
 * Hook to list Jetstream runs with optional filtering
 */
export function useJetstreamRuns(filter?: ListRunsFilter, refetchInterval = 30000) {
  return useQuery<ListRunsResponse>({
    queryKey: ['jetstream', 'runs', filter],
    queryFn: () => listJetstreamRuns(filter),
    refetchInterval,
    staleTime: 10000,
  });
}

/**
 * Hook to get a single run by ID
 */
export function useJetstreamRun(runId: string | undefined, refetchInterval?: number) {
  return useQuery<JetstreamRun>({
    queryKey: ['jetstream', 'run', runId],
    queryFn: () => getJetstreamRun(runId!),
    enabled: !!runId,
    refetchInterval,
    staleTime: 5000,
  });
}

/**
 * Hook to trigger manual sync
 */
export function useJetstreamSync() {
  const queryClient = useQueryClient();

  return useMutation<SyncResponse>({
    mutationFn: triggerJetstreamSync,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['jetstream', 'runs'] });
      void queryClient.invalidateQueries({ queryKey: ['jetstream', 'status'] });
    },
  });
}
