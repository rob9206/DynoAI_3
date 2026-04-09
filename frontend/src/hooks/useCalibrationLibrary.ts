import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { HardwareConfig } from "@/api/v3Session";
import {
  blendCalibrationLibrary,
  deleteCalibrationLibraryEntry,
  getCalibrationLibraryStats,
  ingestCalibrationLibrary,
  listCalibrationLibraryEntries,
  type CalibrationLibraryBlendResponse,
  type CalibrationLibraryIngestResponse,
  type CalibrationLibraryListResponse,
  type CalibrationLibraryStatsResponse,
} from "@/api/calibrationLibrary";

interface IngestArgs {
  file: File;
  config: HardwareConfig;
  operator?: string;
  notes?: string;
}

interface BlendArgs {
  config: HardwareConfig;
  topN?: number;
  minSimilarity?: number;
}

export function useCalibrationLibrary(engineFamily?: string) {
  const queryClient = useQueryClient();

  const listQuery = useQuery<CalibrationLibraryListResponse>({
    queryKey: ["v3", "calibration-library", "list", engineFamily],
    queryFn: () =>
      listCalibrationLibraryEntries({
        engine_family: engineFamily,
        limit: 100,
        offset: 0,
      }),
    staleTime: 15_000,
  });

  const statsQuery = useQuery<CalibrationLibraryStatsResponse>({
    queryKey: ["v3", "calibration-library", "stats"],
    queryFn: getCalibrationLibraryStats,
    staleTime: 15_000,
  });

  const ingestMutation = useMutation<CalibrationLibraryIngestResponse, Error, IngestArgs>({
    mutationFn: ({ file, config, operator, notes }) =>
      ingestCalibrationLibrary(file, config, operator, notes),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["v3", "calibration-library", "list"],
      });
      void queryClient.invalidateQueries({
        queryKey: ["v3", "calibration-library", "stats"],
      });
    },
  });

  const blendMutation = useMutation<CalibrationLibraryBlendResponse, Error, BlendArgs>({
    mutationFn: ({ config, topN, minSimilarity }) =>
      blendCalibrationLibrary(config, topN ?? 5, minSimilarity ?? 0.0),
  });

  const deleteMutation = useMutation<
    { deleted: boolean; calibration_id: string },
    Error,
    string
  >({
    mutationFn: (calibrationId) => deleteCalibrationLibraryEntry(calibrationId),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["v3", "calibration-library", "list"],
      });
      void queryClient.invalidateQueries({
        queryKey: ["v3", "calibration-library", "stats"],
      });
    },
  });

  return {
    list: listQuery.data,
    stats: statsQuery.data,
    blendPreview: blendMutation.data,

    isLoadingList: listQuery.isLoading,
    isLoadingStats: statsQuery.isLoading,
    isIngesting: ingestMutation.isPending,
    isBlending: blendMutation.isPending,
    isDeleting: deleteMutation.isPending,

    listError: listQuery.error,
    statsError: statsQuery.error,
    ingestError: ingestMutation.error,
    blendError: blendMutation.error,
    deleteError: deleteMutation.error,

    ingestCalibration: (args: IngestArgs) => ingestMutation.mutateAsync(args),
    previewBlend: (args: BlendArgs) => blendMutation.mutateAsync(args),
    deleteCalibration: (calibrationId: string) =>
      deleteMutation.mutateAsync(calibrationId),
    refetchList: listQuery.refetch,
    refetchStats: statsQuery.refetch,
  };
}
