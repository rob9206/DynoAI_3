/**
 * React Query hooks for the Tuning Workspace.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  analyzeIteration,
  createIteration,
  createSession,
  createVehicle,
  getSession,
  getSessionStatus,
  getVehicle,
  listAnalyses,
  listIterations,
  listPatches,
  listPulls,
  listSessions,
  listVehicles,
  uploadToSession,
  type AnalysisResult,
  type Iteration,
  type SessionStatus,
  type TuningSession,
  type UploadResponse,
  type Vehicle,
} from '../api/workspace';

const STALE_SHORT = 5_000;
const STALE_MED = 30_000;

export function useVehicles() {
  return useQuery<Vehicle[]>({
    queryKey: ['workspace', 'vehicles'],
    queryFn: listVehicles,
    staleTime: STALE_MED,
  });
}

export function useVehicle(vehicleId: string | undefined) {
  return useQuery<Vehicle>({
    queryKey: ['workspace', 'vehicle', vehicleId],
    queryFn: () => getVehicle(vehicleId!),
    enabled: !!vehicleId,
    staleTime: STALE_MED,
  });
}

export function useCreateVehicle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createVehicle,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['workspace', 'vehicles'] });
    },
  });
}

export function useSessions(vehicleId: string | undefined) {
  return useQuery<TuningSession[]>({
    queryKey: ['workspace', 'sessions', vehicleId],
    queryFn: () => listSessions(vehicleId!),
    enabled: !!vehicleId,
    staleTime: STALE_SHORT,
  });
}

export function useSession(
  vehicleId: string | undefined,
  sessionId: string | undefined
) {
  return useQuery<TuningSession>({
    queryKey: ['workspace', 'session', vehicleId, sessionId],
    queryFn: () => getSession(vehicleId!, sessionId!),
    enabled: !!vehicleId && !!sessionId,
    staleTime: STALE_SHORT,
  });
}

export function useSessionStatus(
  vehicleId: string | undefined,
  sessionId: string | undefined,
  refetchInterval: number | false = false
) {
  return useQuery<SessionStatus>({
    queryKey: ['workspace', 'status', vehicleId, sessionId],
    queryFn: () => getSessionStatus(vehicleId!, sessionId!),
    enabled: !!vehicleId && !!sessionId,
    staleTime: STALE_SHORT,
    refetchInterval,
  });
}

export function useCreateSession(vehicleId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { id?: string; notes?: string }) =>
      createSession(vehicleId!, payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['workspace', 'sessions', vehicleId] });
    },
  });
}

export function useIterations(
  vehicleId: string | undefined,
  sessionId: string | undefined
) {
  return useQuery<Iteration[]>({
    queryKey: ['workspace', 'iterations', vehicleId, sessionId],
    queryFn: () => listIterations(vehicleId!, sessionId!),
    enabled: !!vehicleId && !!sessionId,
    staleTime: STALE_SHORT,
  });
}

export function useCreateIteration(
  vehicleId: string | undefined,
  sessionId: string | undefined
) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patchFilename?: string) =>
      createIteration(vehicleId!, sessionId!, patchFilename),
    onSuccess: () => {
      void qc.invalidateQueries({
        queryKey: ['workspace', 'iterations', vehicleId, sessionId],
      });
      void qc.invalidateQueries({
        queryKey: ['workspace', 'status', vehicleId, sessionId],
      });
      void qc.invalidateQueries({
        queryKey: ['workspace', 'session', vehicleId, sessionId],
      });
    },
  });
}

export function usePulls(
  vehicleId: string | undefined,
  sessionId: string | undefined,
  iterationId: string | undefined
) {
  return useQuery({
    queryKey: ['workspace', 'pulls', vehicleId, sessionId, iterationId],
    queryFn: () => listPulls(vehicleId!, sessionId!, iterationId!),
    enabled: !!vehicleId && !!sessionId && !!iterationId,
    staleTime: STALE_SHORT,
  });
}

export function usePatches(
  vehicleId: string | undefined,
  sessionId: string | undefined,
  iterationId: string | undefined
) {
  return useQuery({
    queryKey: ['workspace', 'patches', vehicleId, sessionId, iterationId],
    queryFn: () => listPatches(vehicleId!, sessionId!, iterationId!),
    enabled: !!vehicleId && !!sessionId && !!iterationId,
    staleTime: STALE_SHORT,
  });
}

export function useAnalyses(
  vehicleId: string | undefined,
  sessionId: string | undefined,
  iterationId: string | undefined
) {
  return useQuery({
    queryKey: ['workspace', 'analyses', vehicleId, sessionId, iterationId],
    queryFn: () => listAnalyses(vehicleId!, sessionId!, iterationId!),
    enabled: !!vehicleId && !!sessionId && !!iterationId,
    staleTime: STALE_SHORT,
  });
}

export function useAnalyzeIteration(
  vehicleId: string | undefined,
  sessionId: string | undefined
) {
  const qc = useQueryClient();
  return useMutation<AnalysisResult, Error, { iterationId?: string }>({
    mutationFn: ({ iterationId }) =>
      analyzeIteration(vehicleId!, sessionId!, iterationId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['workspace', 'patches'] });
      void qc.invalidateQueries({ queryKey: ['workspace', 'analyses'] });
      void qc.invalidateQueries({
        queryKey: ['workspace', 'status', vehicleId, sessionId],
      });
    },
  });
}

export function useUploadToSession(
  vehicleId: string | undefined,
  sessionId: string | undefined
) {
  const qc = useQueryClient();
  return useMutation<
    UploadResponse,
    Error,
    { files: File[]; iterationId?: string; treatAs?: 'base_tune' | 'patches' | 'pulls' }
  >({
    mutationFn: ({ files, iterationId, treatAs }) =>
      uploadToSession(vehicleId!, sessionId!, files, { iterationId, treatAs }),
    onSuccess: () => {
      void qc.invalidateQueries({
        queryKey: ['workspace', 'status', vehicleId, sessionId],
      });
      void qc.invalidateQueries({ queryKey: ['workspace', 'pulls'] });
      void qc.invalidateQueries({ queryKey: ['workspace', 'patches'] });
      void qc.invalidateQueries({
        queryKey: ['workspace', 'session', vehicleId, sessionId],
      });
    },
  });
}
