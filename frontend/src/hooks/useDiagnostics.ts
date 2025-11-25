import { useState, useEffect, useCallback } from 'react';
import api from '@/lib/api';
import type { DiagnosticsData } from '@/components/results/DiagnosticsDetail';

export interface UseDiagnosticsOptions {
  runId: string;
  enabled?: boolean;
}

export interface UseDiagnosticsReturn {
  data: DiagnosticsData | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
}

interface ApiDiagnosticsResponse {
  diagnostics?: {
    cellsCorrected?: number;
    totalCells?: number;
    maxCorrection?: number;
    minCorrection?: number;
    avgCorrection?: number;
    cellsClamped?: number;
    clampLimit?: number;
    coveragePercent?: number;
    processingTimeMs?: number;
    dataPoints?: number;
    kernelsApplied?: string[];
  };
}

function transformApiResponse(response: ApiDiagnosticsResponse): DiagnosticsData | null {
  const diag = response.diagnostics;
  if (!diag) {
    return null;
  }

  return {
    cellsCorrected: diag.cellsCorrected ?? 0,
    totalCells: diag.totalCells ?? 0,
    maxCorrection: diag.maxCorrection ?? 0,
    minCorrection: diag.minCorrection ?? 0,
    avgCorrection: diag.avgCorrection ?? 0,
    cellsClamped: diag.cellsClamped ?? 0,
    clampLimit: diag.clampLimit ?? 7,
    coveragePercent: diag.coveragePercent ?? 0,
    processingTimeMs: diag.processingTimeMs ?? 0,
    dataPoints: diag.dataPoints ?? 0,
    kernelsApplied: diag.kernelsApplied ?? [],
  };
}

export function useDiagnostics({
  runId,
  enabled = true,
}: UseDiagnosticsOptions): UseDiagnosticsReturn {
  const [data, setData] = useState<DiagnosticsData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const fetchDiagnostics = useCallback(async () => {
    if (!runId || !enabled) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await api.get<ApiDiagnosticsResponse>(`/api/results/${runId}`);
      const transformedData = transformApiResponse(response.data);
      setData(transformedData);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch diagnostics';
      setError(new Error(errorMessage));
      setData(null);
    } finally {
      setIsLoading(false);
    }
  }, [runId, enabled]);

  useEffect(() => {
    void fetchDiagnostics();
  }, [fetchDiagnostics]);

  const refetch = useCallback(() => {
    void fetchDiagnostics();
  }, [fetchDiagnostics]);

  return {
    data,
    isLoading,
    error,
    refetch,
  };
}

export default useDiagnostics;
