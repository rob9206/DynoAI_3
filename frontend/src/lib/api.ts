import axios, { AxiosError } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5001';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000, // 5 minutes for long-running analyses
  headers: {
    'Content-Type': 'application/json',
  },
});

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
  const response = await api.get(`/api/download/${runId}/${filename}`, {
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
