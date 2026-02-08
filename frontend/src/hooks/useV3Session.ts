/**
 * useV3Session — React Query hook for the v3 Accelerated Calibration session.
 *
 * Provides queries (session status, convergence, uncertainty, next pull, overlay)
 * and mutations (create, ingest pull, finalize, veto, kill switch).
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useCallback, useMemo } from "react";
import {
  createSession,
  getSession,
  ingestPull,
  importBaseVE,
  importCorrections,
  finalizeSession,
  suggestNextPull,
  checkConvergence,
  operatorVeto,
  getUncertaintyMap,
  getOverlayStatus,
  activateKillSwitch,
  listTemplates,
  simulatePull,
  autoSimulate,
  type HardwareConfig,
  type PullData,
  type FinalizeRequest,
  type ImportVERequest,
  type ImportCorrectionsRequest,
  type VetoRequest,
  type SimulatePullRequest,
  type AutoSimulateRequest,
  type AutoSimulateResult,
  type SessionInitResult,
  type SessionStatus,
  type PullResult,
  type FinalResult,
  type PullRecommendation,
  type ConvergenceStatus,
  type UncertaintyMapResult,
  type OverlayStatus,
  type TemplateListResult,
} from "@/api/v3Session";

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useV3Session(sessionId?: string) {
  const queryClient = useQueryClient();

  // ---- Queries ----

  const {
    data: sessionStatus,
    isLoading: isLoadingStatus,
    error: statusError,
  } = useQuery({
    queryKey: ["v3", "session", sessionId],
    queryFn: () => getSession(sessionId!),
    enabled: !!sessionId,
    refetchInterval: (query) => {
      // Poll every 2s while in_progress, stop once complete
      const state = query.state.data?.state;
      return state === "in_progress" || state === "ready" ? 2_000 : false;
    },
    staleTime: 1_000,
  });

  const {
    data: convergence,
    isLoading: isLoadingConvergence,
  } = useQuery({
    queryKey: ["v3", "convergence", sessionId],
    queryFn: () => checkConvergence(sessionId!),
    enabled: !!sessionId && sessionStatus?.state === "in_progress",
    staleTime: 3_000,
  });

  const {
    data: uncertaintyMap,
    isLoading: isLoadingUncertainty,
  } = useQuery({
    queryKey: ["v3", "uncertainty", sessionId],
    queryFn: () => getUncertaintyMap(sessionId!),
    enabled: !!sessionId && (sessionStatus?.state === "ready" || sessionStatus?.state === "in_progress"),
    staleTime: 5_000,
  });

  const {
    data: nextPull,
    isLoading: isLoadingNextPull,
  } = useQuery({
    queryKey: ["v3", "next-pull", sessionId],
    queryFn: () => suggestNextPull(sessionId!),
    enabled: !!sessionId && (sessionStatus?.state === "ready" || sessionStatus?.state === "in_progress"),
    staleTime: 5_000,
  });

  const {
    data: overlay,
  } = useQuery({
    queryKey: ["v3", "overlay", sessionId],
    queryFn: () => getOverlayStatus(sessionId!),
    enabled: !!sessionId,
    staleTime: 10_000,
  });

  const {
    data: templates,
  } = useQuery({
    queryKey: ["v3", "templates"],
    queryFn: () => listTemplates(),
    staleTime: 30_000,
  });

  // ---- Mutations ----

  const createMutation = useMutation({
    mutationFn: (config: HardwareConfig) => createSession(config),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["v3"] });
    },
  });

  const ingestMutation = useMutation({
    mutationFn: (data: PullData) => ingestPull(sessionId!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["v3", "session", sessionId] });
      queryClient.invalidateQueries({ queryKey: ["v3", "convergence", sessionId] });
      queryClient.invalidateQueries({ queryKey: ["v3", "uncertainty", sessionId] });
      queryClient.invalidateQueries({ queryKey: ["v3", "next-pull", sessionId] });
    },
  });

  const importVEMutation = useMutation({
    mutationFn: (data: ImportVERequest) => importBaseVE(sessionId!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["v3", "session", sessionId] });
      queryClient.invalidateQueries({ queryKey: ["v3", "convergence", sessionId] });
      queryClient.invalidateQueries({ queryKey: ["v3", "uncertainty", sessionId] });
    },
  });

  const finalizeMutation = useMutation({
    mutationFn: (data: FinalizeRequest) => finalizeSession(sessionId!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["v3"] });
    },
  });

  const vetoMutation = useMutation({
    mutationFn: (data: VetoRequest) => operatorVeto(sessionId!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["v3", "next-pull", sessionId] });
    },
  });

  const killSwitchMutation = useMutation({
    mutationFn: () => activateKillSwitch(sessionId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["v3", "overlay", sessionId] });
    },
  });

  const simulateMutation = useMutation({
    mutationFn: (data?: SimulatePullRequest) => simulatePull(sessionId!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["v3", "session", sessionId] });
      queryClient.invalidateQueries({ queryKey: ["v3", "convergence", sessionId] });
      queryClient.invalidateQueries({ queryKey: ["v3", "uncertainty", sessionId] });
      queryClient.invalidateQueries({ queryKey: ["v3", "next-pull", sessionId] });
    },
  });

  const autoSimulateMutation = useMutation({
    mutationFn: (data?: AutoSimulateRequest) => autoSimulate(sessionId!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["v3", "session", sessionId] });
      queryClient.invalidateQueries({ queryKey: ["v3", "convergence", sessionId] });
      queryClient.invalidateQueries({ queryKey: ["v3", "uncertainty", sessionId] });
      queryClient.invalidateQueries({ queryKey: ["v3", "next-pull", sessionId] });
    },
  });

  const importCorrectionsMutation = useMutation({
    mutationFn: (data: ImportCorrectionsRequest) =>
      importCorrections(sessionId!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["v3", "session", sessionId] });
      queryClient.invalidateQueries({ queryKey: ["v3", "convergence", sessionId] });
      queryClient.invalidateQueries({ queryKey: ["v3", "uncertainty", sessionId] });
      queryClient.invalidateQueries({ queryKey: ["v3", "next-pull", sessionId] });
    },
  });

  // ---- Wrapped actions ----

  const startSession = useCallback(
    (config: HardwareConfig) => createMutation.mutateAsync(config),
    [createMutation]
  );

  const submitPull = useCallback(
    (data: PullData) => ingestMutation.mutateAsync(data),
    [ingestMutation]
  );

  const importVE = useCallback(
    (data: ImportVERequest) => importVEMutation.mutateAsync(data),
    [importVEMutation]
  );

  const finalize = useCallback(
    (data: FinalizeRequest) => finalizeMutation.mutateAsync(data),
    [finalizeMutation]
  );

  const veto = useCallback(
    (data: VetoRequest) => vetoMutation.mutateAsync(data),
    [vetoMutation]
  );

  const killSwitch = useCallback(
    () => killSwitchMutation.mutateAsync(),
    [killSwitchMutation]
  );

  const simulate = useCallback(
    (data?: SimulatePullRequest) => simulateMutation.mutateAsync(data),
    [simulateMutation]
  );

  const runAutoSimulate = useCallback(
    (data?: AutoSimulateRequest) => autoSimulateMutation.mutateAsync(data),
    [autoSimulateMutation]
  );

  const importSessionCorrections = useCallback(
    (data: ImportCorrectionsRequest) =>
      importCorrectionsMutation.mutateAsync(data),
    [importCorrectionsMutation]
  );

  // ---- Derived state ----

  const sessionPhase = useMemo<"idle" | "ready" | "tuning" | "complete">(() => {
    if (!sessionId || !sessionStatus) return "idle";
    switch (sessionStatus.state) {
      case "ready": return "ready";
      case "in_progress": return "tuning";
      case "complete": return "complete";
      default: return "idle";
    }
  }, [sessionId, sessionStatus]);

  const isConverged = useMemo(
    () => convergence?.converged ?? false,
    [convergence]
  );

  const pullCount = useMemo(
    () => sessionStatus?.pull_count ?? 0,
    [sessionStatus]
  );

  // ---- Return ----

  return {
    // Data
    sessionStatus,
    convergence,
    uncertaintyMap,
    nextPull,
    overlay,
    templates,

    // Derived
    sessionPhase,
    isConverged,
    pullCount,

    // Loading
    isLoadingStatus,
    isLoadingConvergence,
    isLoadingUncertainty,
    isLoadingNextPull,
    isCreating: createMutation.isPending,
    isIngesting: ingestMutation.isPending,
    isImportingVE: importVEMutation.isPending,
    isImportingCorrections: importCorrectionsMutation.isPending,
    isFinalizing: finalizeMutation.isPending,
    isSimulating: simulateMutation.isPending,
    isAutoSimulating: autoSimulateMutation.isPending,

    // Errors
    statusError,
    createError: createMutation.error,
    ingestError: ingestMutation.error,

    // Results (for init data after create)
    initResult: createMutation.data as SessionInitResult | undefined,

    // Actions
    startSession,
    submitPull,
    importVE,
    finalize,
    veto,
    killSwitch,
    simulate,
    runAutoSimulate,
    importSessionCorrections,
  };
}
