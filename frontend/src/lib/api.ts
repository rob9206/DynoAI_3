import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { encodePathSegment } from './sanitize';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5001';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000, // 5 minutes for long-running analyses
  headers: {
    'Content-Type': 'application/json',
  },
});

// Rate limit handling with exponential backoff
let rateLimitBackoff = 0;
const MAX_RETRIES = 3;
const MAX_BACKOFF_MS = 8000;

const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

api.interceptors.response.use(
  (response) => {
    // Reset backoff on success
    rateLimitBackoff = 0;
    return response;
  },
  async (error: AxiosError) => {
    const config = error.config as InternalAxiosRequestConfig & { _retryCount?: number };
    
    // Handle 429 rate limiting with exponential backoff
    if (error.response?.status === 429 && config) {
      config._retryCount = config._retryCount ?? 0;
      
      if (config._retryCount < MAX_RETRIES) {
        config._retryCount += 1;
        
        // Calculate backoff from Retry-After header or exponentially
        const retryAfter = error.response.headers['retry-after'];
        const backoffMs = retryAfter 
          ? parseInt(retryAfter, 10) * 1000 
          : Math.min(rateLimitBackoff === 0 ? 500 : rateLimitBackoff * 2, MAX_BACKOFF_MS);
        
        rateLimitBackoff = backoffMs;
        
        console.warn(`[API] Rate limited, retrying in ${backoffMs}ms (attempt ${config._retryCount}/${MAX_RETRIES})`);
        await sleep(backoffMs);
        
        return api.request(config);
      }
    }
    
    return Promise.reject(error);
  }
);

// Types
export interface AnalysisParams {
  smoothPasses?: number;
  clamp?: number;
  rearBias?: number;
  rearRuleDeg?: number;
  hotExtra?: number;
  decelManagement?: boolean;
  decelSeverity?: 'low' | 'medium' | 'high';
  decelRpmMin?: number;
  decelRpmMax?: number;
  balanceCylinders?: boolean;
  balanceMode?: 'equalize' | 'match_front' | 'match_rear';
  balanceMaxCorrection?: number;
}

export interface AnalysisResponse {
  runId: string;
  status: string;
  message: string;
}

export interface JobStatus {
  runId: string;
  status: 'queued' | 'running' | 'completed' | 'error';
  progress: number;
  message: string;
  filename: string;
  error?: string;
  manifest?: AnalysisManifest;
}

export interface AnalysisManifest {
  timestamp: string;
  inputFile: string;
  rowsProcessed: number;
  correctionsApplied: number;
  outputFiles: OutputFile[];
  analysisMetrics: {
    avgCorrection: number;
    maxCorrection: number;
    targetAFR: number;
    iterations: number;
  };
}

export interface OutputFile {
  name: string;
  type: string;
  url: string;
}

export interface VEData {
  rpm: number[];
  load: number[];
  before: number[][];
  after: number[][];
}

export interface CoverageData {
  front?: {
    rpm: number[];
    load: number[];
    data: number[][];
  };
  rear?: {
    rpm: number[];
    load: number[];
    data: number[][];
  };
}

// =============================================================================
// Session Replay (tuning decisions)
// =============================================================================

export interface SessionReplayDecision {
  timestamp: string;
  action: string;
  reason: string;
  values: Record<string, unknown>;
  cell?: {
    rpm?: number;
    kpa?: number;
    cylinder?: string;
  };
}

export interface SessionReplayData {
  schema_version?: string;
  run_id: string;
  generated_at: string;
  total_decisions: number;
  decisions: SessionReplayDecision[];
}

export interface Anomaly {
  type: string;
  score: number;
  cell?: { rpm: number; kpa: number };
  cell_band?: { rpm: number[]; kpa: number[] };
  cells?: Array<{ rpm: number; kpa: number; hot?: boolean }>;
  explanation: string;
  next_checks: string[];
}

export interface DiagnosticsData {
  report?: string;
  anomalies?: {
    anomalies: Anomaly[];
    correction_diagnostics: {
      front?: Record<string, any>;
      rear?: Record<string, any>;
    };
  };
}

export interface AnalysisRun {
  runId: string;
  timestamp: string;
  inputFile: string;
}

// API Functions
export const healthCheck = async (): Promise<{ status: string; version: string }> => {
  const response = await api.get('/api/health');
  return response.data;
};

export const uploadAndAnalyze = async (
  file: File,
  params?: AnalysisParams
): Promise<AnalysisResponse> => {
  const formData = new FormData();
  formData.append('file', file);

  if (params) {
    if (params.smoothPasses !== undefined) formData.append('smoothPasses', params.smoothPasses.toString());
    if (params.clamp !== undefined) formData.append('clamp', params.clamp.toString());
    if (params.rearBias !== undefined) formData.append('rearBias', params.rearBias.toString());
    if (params.rearRuleDeg !== undefined) formData.append('rearRuleDeg', params.rearRuleDeg.toString());
    if (params.hotExtra !== undefined) formData.append('hotExtra', params.hotExtra.toString());
    if (params.decelManagement !== undefined) formData.append('decelManagement', params.decelManagement.toString());
    if (params.decelSeverity !== undefined) formData.append('decelSeverity', params.decelSeverity);
    if (params.decelRpmMin !== undefined) formData.append('decelRpmMin', params.decelRpmMin.toString());
    if (params.decelRpmMax !== undefined) formData.append('decelRpmMax', params.decelRpmMax.toString());
    if (params.balanceCylinders !== undefined) formData.append('balanceCylinders', params.balanceCylinders.toString());
    if (params.balanceMode !== undefined) formData.append('balanceMode', params.balanceMode);
    if (params.balanceMaxCorrection !== undefined) formData.append('balanceMaxCorrection', params.balanceMaxCorrection.toString());
  }

  const response = await api.post('/api/analyze', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

export const getJobStatus = async (runId: string): Promise<JobStatus> => {
  const response = await api.get(`/api/status/${runId}`);
  return response.data;
};

export const downloadFile = async (runId: string, filename: string): Promise<Blob> => {
  const response = await api.get(`/api/download/${encodePathSegment(runId)}/${encodePathSegment(filename)}`, {
    responseType: 'blob',
  });
  return response.data;
};

export const getVEData = async (runId: string): Promise<VEData> => {
  const response = await api.get(`/api/ve-data/${runId}`);
  return response.data;
};

export const getCoverageData = async (runId: string): Promise<CoverageData> => {
  const response = await api.get(`/api/coverage/${runId}`);
  return response.data;
};

export const getDiagnostics = async (runId: string): Promise<DiagnosticsData> => {
  const response = await api.get(`/api/diagnostics/${runId}`);
  return response.data;
};

export const listRuns = async (): Promise<{ runs: AnalysisRun[] }> => {
  const response = await api.get('/api/runs');
  return response.data;
};

// Polling helper for job status
export const pollJobStatus = async (
  runId: string,
  onProgress: (status: JobStatus) => void,
  interval: number = 1000
): Promise<JobStatus> => {
  return new Promise((resolve, reject) => {
    const poll = async () => {
      try {
        const status = await getJobStatus(runId);
        onProgress(status);

        if (status.status === 'completed') {
          resolve(status);
        } else if (status.status === 'error') {
          reject(new Error(status.error || 'Analysis failed'));
        } else {
          setTimeout(poll, interval);
        }
      } catch (error) {
        reject(error);
      }
    };

    poll();
  });
};

// Session Replay API
export const getSessionReplay = async (runId: string): Promise<SessionReplayData> => {
  // Canonical backend route
  const response = await api.get(`/api/runs/${encodePathSegment(runId)}/session-replay`);
  return response.data as SessionReplayData;
};

// Confidence Report API
export const getConfidenceReport = async (runId: string) => {
  const response = await api.get(`/api/confidence-report/${runId}`);
  return response.data;
};

// =============================================================================
// PowerCore Integration API (file_id based - secure)
// =============================================================================

/** File information returned by discovery endpoints (no raw paths exposed) */
export interface PowerCoreFile {
  id: string;
  name: string;
  size_kb: number;
  mtime: number;
  type: 'log' | 'tune' | 'wp8';
  extension?: string;  // Only for tune files
}

export interface PowerCoreDiscoveryResponse {
  count: number;
  files: PowerCoreFile[];
}

export interface PowerCoreStatusResponse {
  powercore_running: boolean;
  data_dirs: string[];
}

export interface ParseLogResponse {
  success: boolean;
  format?: string;
  signals?: number;
  rows?: number;
  signal_list?: Array<{
    index: number;
    name: string;
    units: string;
    description: string;
  }>;
  dynoai_columns?: string[];
  preview?: Record<string, unknown>[];
  error?: string;
}

export interface ParseTuneResponse {
  success: boolean;
  tables?: number;
  scalars?: number;
  flags?: number;
  table_list?: Array<{
    name: string;
    units: string;
    rows: number;
    cols: number;
    row_units: string;
    col_units: string;
  }>;
  scalar_list?: Record<string, number>;
  flag_list?: Record<string, boolean>;
  error?: string;
}

export interface ParseWP8Response {
  success: boolean;
  channels?: number;
  metadata?: Record<string, string>;
  channel_list?: Array<{
    id: number;
    name: string;
    units: string;
    device: string;
    category: string;
  }>;
  error?: string;
}

/** Check Power Core integration status */
export const getPowerCoreStatus = async (): Promise<PowerCoreStatusResponse> => {
  const response = await api.get('/api/powercore/status');
  return response.data;
};

/** Discover available Power Vision log files */
export const discoverLogs = async (): Promise<PowerCoreDiscoveryResponse> => {
  const response = await api.get('/api/powercore/discover/logs');
  return response.data;
};

/** Discover available tune files (.pvv, .pvm) */
export const discoverTunes = async (): Promise<PowerCoreDiscoveryResponse> => {
  const response = await api.get('/api/powercore/discover/tunes');
  return response.data;
};

/** Discover available WP8 dyno run files */
export const discoverWP8 = async (): Promise<PowerCoreDiscoveryResponse> => {
  const response = await api.get('/api/powercore/discover/wp8');
  return response.data;
};

/** Parse a Power Vision log file using file_id */
export const parseLog = async (fileId: string): Promise<ParseLogResponse> => {
  const response = await api.post('/api/powercore/parse/log', { file_id: fileId });
  return response.data;
};

/** Parse a tune file (.pvv, .pvm) using file_id */
export const parseTune = async (fileId: string): Promise<ParseTuneResponse> => {
  const response = await api.post('/api/powercore/parse/tune', { file_id: fileId });
  return response.data;
};

/** Parse a WP8 dyno run file using file_id */
export const parseWP8 = async (fileId: string): Promise<ParseWP8Response> => {
  const response = await api.post('/api/powercore/parse/wp8', { file_id: fileId });
  return response.data;
};

// =============================================================================
// System Diagnostics API
// =============================================================================

export interface SystemDiagnostics {
  status: string;
  version: string;
  timestamp: string;
  uptime_seconds: number;
  active_jobs: number;
  virtual_tune_sessions: number;
  file_index_entries: number;
  database_status: string;
  health_status: string;
  components: Record<string, unknown>;
}

/** Get system diagnostics */
export const getSystemDiagnostics = async (): Promise<SystemDiagnostics> => {
  const response = await api.get('/api/health/diagnostics');
  return response.data;
};

// =============================================================================
// NextGen Analysis API (Physics-Informed ECU Reasoning)
// =============================================================================

/** Surface axis definition */
export interface NextGenSurfaceAxis {
  name: string;
  unit: string;
  bins: number[];
}

/** Surface statistics */
export interface NextGenSurfaceStats {
  min: number | null;
  max: number | null;
  mean: number | null;
  p05: number | null;
  p95: number | null;
  non_nan_cells: number;
  total_cells: number;
  total_samples: number;
  coverage_pct: number;
}

/** 2D surface data for heatmap display */
export interface NextGenSurface {
  surface_id: string;
  title: string;
  description: string;
  rpm_axis: NextGenSurfaceAxis;
  map_axis: NextGenSurfaceAxis;
  values: (number | null)[][];
  hit_count: number[][];
  stats: NextGenSurfaceStats;
  mask_info: string | null;
}

/** Spark valley finding */
export interface SparkValleyFinding {
  cylinder: 'front' | 'rear' | 'global';
  rpm_center: number;
  rpm_band: [number, number];
  depth_deg: number;
  valley_min_deg: number;
  pre_valley_deg: number;
  post_valley_deg: number;
  map_band_used: number;
  confidence: number;
  evidence: string[];
}

/** Causal hypothesis */
export interface NextGenHypothesis {
  hypothesis_id: string;
  title: string;
  confidence: number;
  category: 'transient' | 'load_signal' | 'knock_limit' | 'temp_trim' | 'fuel_model' | 'data_quality';
  evidence: string[];
  distinguishing_checks: string[];
}

/** Cause tree result */
export interface NextGenCauseTree {
  hypotheses: NextGenHypothesis[];
  summary: string;
  analysis_notes: string[];
}

/** Test step recommendation */
export interface NextGenTestStep {
  name: string;
  goal: string;
  rpm_range: [number, number] | null;
  map_range: [number, number] | null;
  test_type: string;
  constraints: string;
  required_channels: string[];
  success_criteria: string;
  risk_notes: string;
  priority: number;
  expected_coverage_gain?: number;
  efficiency_score?: number;
}

/** Coverage gap with detailed info for UI */
export interface NextGenCoverageGap {
  rpm_range: [number, number];
  map_range: [number, number];
  empty_cells: number;
  total_cells: number;
  coverage_pct: number;
  impact: 'high' | 'medium' | 'low';
  region_type: 'high_map_midrange' | 'idle_low_map' | 'tip_in' | 'general';
  description: string;
}

/** Next test plan */
export interface NextGenTestPlan {
  steps: NextGenTestStep[];
  priority_rationale: string;
  coverage_gaps: string[];
  coverage_gaps_detailed: NextGenCoverageGap[];
  total_estimated_pulls: number;
  dyno_step_count: number;
  street_step_count: number;
}

/** Channel status in checklist */
export interface NextGenChannelStatus {
  name: string;
  label: string;
  present: boolean;
  required: boolean;
  impact?: string;
  note?: string;
}

/** Structured warning with stable code */
export interface NextGenChannelWarning {
  code: string;
  message: string;
  severity: 'error' | 'warning' | 'info';
  feature_impact: string;
}

/** Channel readiness checklist */
export interface NextGenChannelReadiness {
  required_present: number;
  required_total: number;
  recommended_present: number;
  recommended_total: number;
  required_channels: NextGenChannelStatus[];
  recommended_channels: NextGenChannelStatus[];
  warnings: NextGenChannelWarning[];
  warning_codes: string[];
  features_available: string[];
  features_degraded: string[];
  features_disabled: string[];
  trust_summary: string;
  confidence_score: number;
  is_ready: boolean;
}

/** Full NextGen analysis payload */
export interface NextGenAnalysisPayload {
  schema_version: string;
  run_id: string;
  generated_at: string;
  inputs_present: Record<string, boolean>;
  channel_readiness: NextGenChannelReadiness;
  mode_summary: Record<string, number>;
  surfaces: Record<string, NextGenSurface>;
  spark_valley: SparkValleyFinding[];
  cause_tree: NextGenCauseTree;
  next_tests: NextGenTestPlan;
  notes_warnings: string[];
  warning_codes: string[];
  /** Short, factual notes explaining the ECU mental model */
  ecu_model_notes: string[];
}

/** Summary returned from generate endpoint */
export interface NextGenSummary {
  total_samples: number;
  surface_count: number;
  spark_valley_count: number;
  hypothesis_count: number;
  test_step_count: number;
  warning_count: number;
  top_hypothesis: {
    title: string;
    confidence: number;
    category: string;
  } | null;
  mode_distribution: {
    wot_percent: number;
    cruise_percent: number;
  };
}

/** Response from generate endpoint */
export interface NextGenGenerateResponse {
  success: boolean;
  run_id: string;
  generated_at: string;
  from_cache: boolean;
  summary: NextGenSummary;
  download_url: string;
  payload?: NextGenAnalysisPayload;
  error?: string;
}

/** Get cached NextGen analysis payload */
export const getNextGenAnalysis = async (runId: string): Promise<NextGenAnalysisPayload> => {
  const response = await api.get(`/api/nextgen/${encodePathSegment(runId)}`);
  return response.data;
};

/** Generate NextGen analysis for a run */
export const generateNextGenAnalysis = async (
  runId: string,
  options?: { force?: boolean; includeFull?: boolean }
): Promise<NextGenGenerateResponse> => {
  const params = new URLSearchParams();
  if (options?.force) params.append('force', 'true');
  if (options?.includeFull) params.append('include', 'full');
  
  const url = `/api/nextgen/${encodePathSegment(runId)}/generate${params.toString() ? '?' + params.toString() : ''}`;
  const response = await api.post(url);
  return response.data;
};

/** Get NextGen surfaces only */
export const getNextGenSurfaces = async (
  runId: string,
  surfaceId?: string
): Promise<{ surfaces: Record<string, NextGenSurface>; surface_ids: string[] }> => {
  const params = surfaceId ? `?surface_id=${surfaceId}` : '';
  const response = await api.get(`/api/nextgen/${encodePathSegment(runId)}/surfaces${params}`);
  return response.data;
};

/** Get NextGen hypotheses with optional filtering */
export const getNextGenHypotheses = async (
  runId: string,
  options?: { minConfidence?: number; category?: string }
): Promise<{
  hypotheses: NextGenHypothesis[];
  total_count: number;
  filtered_count: number;
  summary: string;
}> => {
  const params = new URLSearchParams();
  if (options?.minConfidence != null) params.append('min_confidence', options.minConfidence.toString());
  if (options?.category) params.append('category', options.category);
  
  const url = `/api/nextgen/${encodePathSegment(runId)}/hypotheses${params.toString() ? '?' + params.toString() : ''}`;
  const response = await api.get(url);
  return response.data;
};

// Error handler
export const handleApiError = (error: unknown): string => {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<{ error: string }>;
    if (axiosError.response?.data?.error) {
      return axiosError.response.data.error;
    }
    if (axiosError.message) {
      return axiosError.message;
    }
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'An unknown error occurred';
};

export default api;
