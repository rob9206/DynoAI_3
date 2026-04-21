import api from "@/lib/api";
import { encodePathSegment } from "@/lib/sanitize";
import type { HardwareConfig } from "@/api/v3Session";

export interface CalibrationLibraryIngestResponse {
  calibration_id: string;
  engine_family: string;
  displacement_ci: number;
  source_pvv: string;
  source_identity: string;
  grid: {
    rpm_bins: number[];
    map_bins: number[];
    rows: number;
    cols: number;
  };
  has_rear: boolean;
  afr_targets_count: number;
  ingest_count: number;
}

export interface CalibrationLibraryEntrySummary {
  calibration_id: string;
  engine_family: string;
  displacement_ci: number;
  config: HardwareConfig;
  path: string;
  source_file_name?: string;
  source_name?: string;
  source_path?: string;
  source_identity?: string;
  source_calibration_id?: string | null;
  ingested_at?: number;
  has_rear?: boolean;
  afr_targets_count?: number;
  rows?: number;
  cols?: number;
  ingest_count?: number;
}

export interface CalibrationLibraryListResponse {
  total: number;
  offset: number;
  limit: number;
  entries: CalibrationLibraryEntrySummary[];
}

export interface CalibrationLibraryEntryDetail {
  calibration_id: string;
  config: HardwareConfig;
  ve_front: number[][];
  ve_rear?: number[][] | null;
  afr_targets: Record<string, number>;
  rpm_bins: number[];
  map_bins: number[];
  source_pvv: string;
  metadata?: Record<string, unknown>;
}

export interface CalibrationLibraryStatsResponse {
  total_entries: number;
  by_family: Record<string, number>;
}

export interface CalibrationLibraryBlendMatch {
  calibration_id: string;
  similarity_score: number;
  source_file_name: string;
  operator: string;
  source_identity: string;
}

export interface CalibrationLibraryBlendResponse {
  engine_family: string;
  match_count: number;
  min_similarity: number;
  matches: CalibrationLibraryBlendMatch[];
  ve_front: number[][];
  ve_rear?: number[][] | null;
  afr_targets: Record<string, number>;
  rpm_bins: number[];
  map_bins: number[];
  confidence_map: number[][];
  source_matches: {
    calibration_id: string;
    similarity_score: number;
    weight: number;
  }[];
  grid_coverage_pct: number;
  native_resolution_count: number;
}

export async function ingestCalibrationLibrary(
  file: File,
  config: HardwareConfig,
  operator = "unknown",
  notes = ""
): Promise<CalibrationLibraryIngestResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("config", JSON.stringify(config));
  formData.append("operator", operator);
  formData.append("notes", notes);

  const response = await api.post<CalibrationLibraryIngestResponse>(
    "/api/v3/calibration-library/ingest",
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    }
  );
  return response.data;
}

export async function listCalibrationLibraryEntries(params?: {
  engine_family?: string;
  limit?: number;
  offset?: number;
}): Promise<CalibrationLibraryListResponse> {
  const response = await api.get<CalibrationLibraryListResponse>(
    "/api/v3/calibration-library",
    { params }
  );
  return response.data;
}

export async function getCalibrationLibraryEntry(
  calibrationId: string
): Promise<CalibrationLibraryEntryDetail> {
  const response = await api.get<CalibrationLibraryEntryDetail>(
    `/api/v3/calibration-library/${encodePathSegment(calibrationId)}`
  );
  return response.data;
}

export async function deleteCalibrationLibraryEntry(
  calibrationId: string
): Promise<{ deleted: boolean; calibration_id: string }> {
  const response = await api.delete<{ deleted: boolean; calibration_id: string }>(
    `/api/v3/calibration-library/${encodePathSegment(calibrationId)}`
  );
  return response.data;
}

export async function blendCalibrationLibrary(
  config: HardwareConfig,
  topN = 5,
  minSimilarity = 0.0
): Promise<CalibrationLibraryBlendResponse> {
  const response = await api.post<CalibrationLibraryBlendResponse>(
    "/api/v3/calibration-library/blend",
    {
      config,
      top_n: topN,
      min_similarity: minSimilarity,
    }
  );
  return response.data;
}

export async function getCalibrationLibraryStats(): Promise<CalibrationLibraryStatsResponse> {
  const response = await api.get<CalibrationLibraryStatsResponse>(
    "/api/v3/calibration-library/stats"
  );
  return response.data;
}
