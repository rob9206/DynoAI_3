/**
 * Jetstream API client for DynoAI frontend
 */

import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:5001';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Types
export interface JetstreamStatus {
  connected: boolean;
  last_poll: string | null;
  next_poll: string | null;
  pending_runs: number;
  processing_run: string | null;
  error: string | null;
}

export interface JetstreamConfig {
  api_url: string;
  api_key: string;
  poll_interval_seconds: number;
  auto_process: boolean;
  enabled: boolean;
}

export type RunStatus =
  | 'pending'
  | 'downloading'
  | 'converting'
  | 'validating'
  | 'processing'
  | 'complete'
  | 'error';

export interface RunError {
  stage: string;
  code: string;
  message: string;
}

export interface JetstreamRun {
  run_id: string;
  status: RunStatus;
  source: 'jetstream' | 'manual_upload';
  jetstream_id?: string;
  created_at: string;
  updated_at: string;
  current_stage?: string;
  progress_percent?: number;
  error?: RunError;
  results_summary?: Record<string, unknown>;
  files?: string[];
  output_files?: OutputFile[];
  jetstream_metadata?: JetstreamMetadata;
  manifest?: Record<string, unknown>;
}

export interface OutputFile {
  name: string;
  size: number;
  url: string;
}

export interface JetstreamMetadata {
  vehicle?: string;
  dyno_type?: string;
  engine_type?: string;
  ambient_temp_f?: number;
  ambient_pressure_inhg?: number;
  humidity_percent?: number;
  duration_seconds?: number;
  data_points?: number;
  peak_hp?: number;
  peak_torque?: number;
}

export interface ListRunsResponse {
  runs: JetstreamRun[];
  total: number;
}

export interface ListRunsFilter {
  status?: RunStatus;
  source?: 'jetstream' | 'manual_upload';
  limit?: number;
  offset?: number;
}

export interface SyncResponse {
  new_runs_found: number;
  run_ids: string[];
  error?: string;
}

// API Functions

/**
 * Get the current Jetstream poller status
 */
export async function getJetstreamStatus(): Promise<JetstreamStatus> {
  const response = await api.get<JetstreamStatus>('/api/jetstream/status');
  return response.data;
}

/**
 * Get the current Jetstream configuration
 */
export async function getJetstreamConfig(): Promise<JetstreamConfig> {
  const response = await api.get<JetstreamConfig>('/api/jetstream/config');
  return response.data;
}

/**
 * Update the Jetstream configuration
 */
export async function updateJetstreamConfig(
  config: Partial<JetstreamConfig>
): Promise<{ message: string; config: JetstreamConfig }> {
  const response = await api.put<{ message: string; config: JetstreamConfig }>(
    '/api/jetstream/config',
    config
  );
  return response.data;
}

/**
 * List Jetstream runs with optional filtering
 */
export async function listJetstreamRuns(
  filter?: ListRunsFilter
): Promise<ListRunsResponse> {
  const params = new URLSearchParams();
  if (filter?.status) params.append('status', filter.status);
  if (filter?.source) params.append('source', filter.source);
  if (filter?.limit) params.append('limit', filter.limit.toString());
  if (filter?.offset) params.append('offset', filter.offset.toString());

  const response = await api.get<ListRunsResponse>('/api/jetstream/runs', {
    params,
  });
  return response.data;
}

/**
 * Get details for a specific run
 */
export async function getJetstreamRun(runId: string): Promise<JetstreamRun> {
  const response = await api.get<JetstreamRun>(`/api/jetstream/runs/${runId}`);
  return response.data;
}

/**
 * Trigger an immediate sync with Jetstream
 */
export async function triggerJetstreamSync(): Promise<SyncResponse> {
  const response = await api.post<SyncResponse>('/api/jetstream/sync');
  return response.data;
}

/**
 * Download a file from a run
 */
export async function downloadRunFile(
  runId: string,
  filename: string
): Promise<Blob> {
  const response = await api.get(`/api/jetstream/runs/${runId}/files/${filename}`, {
    responseType: 'blob',
  });
  return response.data as Blob;
}

/**
 * Fetch file content as text for preview
 */
export async function getFileContent(
  runId: string,
  filename: string
): Promise<string> {
  const response = await api.get<string>(`/api/jetstream/runs/${runId}/files/${filename}`, {
    responseType: 'text',
  });
  return response.data;
}

// Export the API object for direct use
export const jetstreamApi = {
  getStatus: getJetstreamStatus,
  getConfig: getJetstreamConfig,
  updateConfig: updateJetstreamConfig,
  listRuns: listJetstreamRuns,
  getRun: getJetstreamRun,
  triggerSync: triggerJetstreamSync,
  downloadFile: downloadRunFile,
  getFileContent: getFileContent,
};

export default jetstreamApi;
