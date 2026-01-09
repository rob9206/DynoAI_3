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
