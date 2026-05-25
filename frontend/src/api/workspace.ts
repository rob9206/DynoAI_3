/**
 * Tuning Workspace API client.
 *
 * Thin wrapper over /api/workspace/* endpoints. The workspace organizes
 * files around vehicles / sessions / iterations so the UI no longer has
 * to think about filenames or disk paths.
 */

import axios from 'axios';
import { encodePathSegment, sanitizeDownloadName } from '@/lib/sanitize';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:5001';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  config.headers = config.headers ?? {};
  const jwtToken =
    localStorage.getItem('portal_token') || localStorage.getItem('jwt_token');
  if (jwtToken) {
    config.headers['Authorization'] = `Bearer ${jwtToken}`;
  }
  const apiKey = import.meta.env.VITE_API_KEY;
  if (apiKey) {
    config.headers['X-API-Key'] = apiKey;
  }
  return config;
});

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------

export interface Vehicle {
  id: string;
  name: string;
  year?: number | null;
  make: string;
  model: string;
  displacement_ci?: number | null;
  ecu_signature?: string | null;
  watch_folder?: string | null;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface TuningSession {
  id: string;
  vehicle_id: string;
  base_tune_sha256?: string | null;
  status: string;
  notes: string;
  created_at: string;
  updated_at: string;
  active_iteration_id?: string | null;
}

export interface Iteration {
  id: string;
  session_id: string;
  index: number;
  patch_filename?: string | null;
  flashed_at?: string | null;
  notes: string;
  created_at: string;
}

export interface ChecklistItem {
  id: string;
  ok: boolean;
  label: string;
  detail: string;
}

export interface SessionStatus {
  session_id: string;
  iteration_id: string | null;
  has_vehicle: boolean;
  has_base_tune: boolean;
  pull_count: number;
  has_afr_data: boolean;
  ready_to_analyze: boolean;
  checklist: ChecklistItem[];
}

export interface RoutedFile {
  name: string;
  type: string;
  slot: 'base_tune' | 'patches' | 'pulls';
  path: string;
  iteration_id?: string;
  sha256?: string;
  detail: Record<string, unknown>;
}

export interface RejectedFile {
  name: string;
  reason: string;
}

export interface UploadResponse {
  routed: RoutedFile[];
  rejected: RejectedFile[];
  status: SessionStatus;
  active_iteration_id: string;
}

export interface FileSummary {
  name: string;
  size: number;
  mtime: number;
  path: string;
}

export type WorkspaceArtifactSlot = 'pulls' | 'patches' | 'analyses';

// -----------------------------------------------------------------------------
// Vehicles
// -----------------------------------------------------------------------------

export async function listVehicles(): Promise<Vehicle[]> {
  const { data } = await api.get<Vehicle[]>('/api/workspace/vehicles');
  return data;
}

export async function createVehicle(payload: {
  name: string;
  year?: number;
  make?: string;
  model?: string;
  displacement_ci?: number;
  id?: string;
  watch_folder?: string;
  notes?: string;
}): Promise<Vehicle> {
  const { data } = await api.post<Vehicle>('/api/workspace/vehicles', payload);
  return data;
}

export async function getVehicle(vehicleId: string): Promise<Vehicle> {
  const { data } = await api.get<Vehicle>(
    `/api/workspace/vehicles/${encodePathSegment(vehicleId)}`
  );
  return data;
}

export async function updateVehicle(
  vehicleId: string,
  patch: Partial<Vehicle>
): Promise<Vehicle> {
  const { data } = await api.patch<Vehicle>(
    `/api/workspace/vehicles/${encodePathSegment(vehicleId)}`,
    patch
  );
  return data;
}

// -----------------------------------------------------------------------------
// Sessions
// -----------------------------------------------------------------------------

export async function listSessions(vehicleId: string): Promise<TuningSession[]> {
  const { data } = await api.get<TuningSession[]>(
    `/api/workspace/vehicles/${encodePathSegment(vehicleId)}/sessions`
  );
  return data;
}

export async function createSession(
  vehicleId: string,
  payload: { id?: string; notes?: string } = {}
): Promise<TuningSession> {
  const { data } = await api.post<TuningSession>(
    `/api/workspace/vehicles/${encodePathSegment(vehicleId)}/sessions`,
    payload
  );
  return data;
}

export async function getSession(
  vehicleId: string,
  sessionId: string
): Promise<TuningSession> {
  const { data } = await api.get<TuningSession>(
    `/api/workspace/vehicles/${encodePathSegment(vehicleId)}/sessions/${encodePathSegment(sessionId)}`
  );
  return data;
}

export async function getSessionStatus(
  vehicleId: string,
  sessionId: string
): Promise<SessionStatus> {
  const { data } = await api.get<SessionStatus>(
    `/api/workspace/vehicles/${encodePathSegment(vehicleId)}/sessions/${encodePathSegment(sessionId)}/status`
  );
  return data;
}

// -----------------------------------------------------------------------------
// Iterations
// -----------------------------------------------------------------------------

export async function listIterations(
  vehicleId: string,
  sessionId: string
): Promise<Iteration[]> {
  const { data } = await api.get<Iteration[]>(
    `/api/workspace/vehicles/${encodePathSegment(vehicleId)}/sessions/${encodePathSegment(sessionId)}/iterations`
  );
  return data;
}

export async function createIteration(
  vehicleId: string,
  sessionId: string,
  patchFilename?: string
): Promise<Iteration> {
  const { data } = await api.post<Iteration>(
    `/api/workspace/vehicles/${encodePathSegment(vehicleId)}/sessions/${encodePathSegment(sessionId)}/iterations`,
    { patch_filename: patchFilename }
  );
  return data;
}

export async function listPulls(
  vehicleId: string,
  sessionId: string,
  iterationId: string
): Promise<FileSummary[]> {
  const { data } = await api.get<FileSummary[]>(
    `/api/workspace/vehicles/${encodePathSegment(vehicleId)}/sessions/${encodePathSegment(sessionId)}/iterations/${encodePathSegment(iterationId)}/pulls`
  );
  return data;
}

export async function listPatches(
  vehicleId: string,
  sessionId: string,
  iterationId: string
): Promise<FileSummary[]> {
  const { data } = await api.get<FileSummary[]>(
    `/api/workspace/vehicles/${encodePathSegment(vehicleId)}/sessions/${encodePathSegment(sessionId)}/iterations/${encodePathSegment(iterationId)}/patches`
  );
  return data;
}

export async function listAnalyses(
  vehicleId: string,
  sessionId: string,
  iterationId: string
): Promise<FileSummary[]> {
  const { data } = await api.get<FileSummary[]>(
    `/api/workspace/vehicles/${encodePathSegment(vehicleId)}/sessions/${encodePathSegment(sessionId)}/iterations/${encodePathSegment(iterationId)}/analyses`
  );
  return data;
}

function workspaceArtifactDownloadPath(
  vehicleId: string,
  sessionId: string,
  iterationId: string,
  slot: WorkspaceArtifactSlot,
  filename: string
): string {
  return `/api/workspace/vehicles/${encodePathSegment(vehicleId)}/sessions/${encodePathSegment(sessionId)}/iterations/${encodePathSegment(iterationId)}/download/${encodePathSegment(slot)}/${encodePathSegment(filename)}`;
}

export async function downloadWorkspaceArtifact(
  vehicleId: string,
  sessionId: string,
  iterationId: string,
  slot: WorkspaceArtifactSlot,
  filename: string
): Promise<void> {
  const url = workspaceArtifactDownloadPath(
    vehicleId,
    sessionId,
    iterationId,
    slot,
    filename
  );
  const response = await api.get<Blob>(url, { responseType: 'blob' });
  const objectUrl = window.URL.createObjectURL(response.data);
  const link = document.createElement('a');
  link.href = objectUrl;
  link.download = sanitizeDownloadName(filename, 'download');
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(objectUrl);
}

// -----------------------------------------------------------------------------
// Analyze
// -----------------------------------------------------------------------------

export interface AnalysisResult {
  vehicle_id: string;
  session_id: string;
  iteration_id: string;
  success: boolean;
  pulls_considered: number;
  pulls_used: number;
  primary_pull?: string | null;
  data_source?: string | null;
  afr_mean_error_pct?: number | null;
  zones_adjusted?: number | null;
  peak_hp?: number | null;
  peak_hp_rpm?: number | null;
  peak_tq?: number | null;
  peak_tq_rpm?: number | null;
  correction_pvv_path?: string | null;
  correction_pvv_filename?: string | null;
  correction_pvv_sha256?: string | null;
  correction_pvv_n_changed_cells?: number | null;
  correction_manifest_path?: string | null;
  analysis_json_path?: string | null;
  errors: string[];
  generated_at: string;
}

export async function analyzeIteration(
  vehicleId: string,
  sessionId: string,
  iterationId?: string
): Promise<AnalysisResult> {
  const url = iterationId
    ? `/api/workspace/vehicles/${encodePathSegment(vehicleId)}/sessions/${encodePathSegment(sessionId)}/iterations/${encodePathSegment(iterationId)}/analyze`
    : `/api/workspace/vehicles/${encodePathSegment(vehicleId)}/sessions/${encodePathSegment(sessionId)}/analyze`;
  const { data } = await api.post<AnalysisResult>(url, {});
  return data;
}

// -----------------------------------------------------------------------------
// Smart upload
// -----------------------------------------------------------------------------

export async function uploadToSession(
  vehicleId: string,
  sessionId: string,
  files: File[],
  opts?: { iterationId?: string; treatAs?: 'base_tune' | 'patches' | 'pulls' }
): Promise<UploadResponse> {
  const form = new FormData();
  for (const f of files) {
    form.append('files', f, f.name);
  }
  if (opts?.iterationId) form.append('iteration_id', opts.iterationId);
  if (opts?.treatAs) form.append('treat_as', opts.treatAs);

  const { data } = await api.post<UploadResponse>(
    `/api/workspace/vehicles/${encodePathSegment(vehicleId)}/sessions/${encodePathSegment(sessionId)}/upload`,
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  );
  return data;
}
