/**
 * DynoAI v3.0 Accelerated Calibration — API Client
 *
 * Typed functions for every /api/v3 endpoint.
 * Uses the shared axios instance from @/lib/api.
 */

import api from "@/lib/api";
import { encodePathSegment } from "@/lib/sanitize";

// ---------------------------------------------------------------------------
// Types — mirroring Python dataclasses
// ---------------------------------------------------------------------------

export type PullType = "wot_sweep" | "part_throttle" | "cruise" | "targeted";

export type PullMode = "acceleration" | "steady_state";

export interface HardwareConfig {
  engine_family: string;
  displacement_ci: number;
  cam_spec?: string;
  exhaust_type?: string;
  exhaust_brand?: string;
  air_cleaner?: string;
  throttle_body_mm?: number;
  compression_ratio?: number;
  head_work?: string;
  injector_size?: string;
  fuel_type?: string;
  altitude_ft?: number;
  tune_platform?: string;
  /** Grid override from PVV import or wizard */
  rpm_bins?: number[];
  map_bins?: number[];
}

/** Payload for creating a session; may include imported VE table to seed the GP. */
export interface CreateSessionPayload extends HardwareConfig {
  /** Optional 2D VE table from PVV import; seeds Uncertainty Map so it shows imported tune. */
  initial_ve_table?: number[][];
}

export interface PullRecommendation {
  rpm: number;
  map_kpa: number;
  gear: number;
  pull_number: number;
  pull_type: PullType;
  pull_mode?: PullMode;
  reason: string;
  expected_info_gain: number;
  remaining_uncertainty: number;
  throttle_pct: number;
  alternatives: PullRecommendation[];
}

export interface ConvergenceStatus {
  converged: boolean;
  max_uncertainty: number;
  mean_uncertainty: number;
  cells_above_threshold: number;
  total_cells: number;
  estimated_pulls_remaining: number;
}

export interface TemplateMatchInfo {
  template_id: string;
  similarity_score: number;
  is_usable: boolean;
  engine_family: string;
}

export interface SessionInitResult {
  session_id: string;
  engine_family: string;
  estimated_pulls: number;
  template_match: TemplateMatchInfo | null;
  initial_plan: PullRecommendation[];
}

export interface SessionStatus {
  session_id: string;
  state: "created" | "ready" | "in_progress" | "complete";
  engine_family: string;
  pull_count: number;
  converged: boolean;
  elapsed_s: number;
  template_match: string | null;
}

export interface PullResult {
  pull_number: number;
  observations_added: number;
  convergence: ConvergenceStatus | null;
  next_suggestion: PullRecommendation | null;
}

export interface FinalResult {
  template_id: string;
  total_pulls: number;
  session_id: string;
  session_duration_s: number;
}

export interface UncertaintyMapResult {
  ve_map: number[][];
  uncertainty_map: number[][];
  confidence_map: number[][];
  predict_time_ms: number;
  rpm_bins: number[];
  map_bins: number[];
}

export interface OverlayStatus {
  enabled: boolean;
  fuel_corrections_active: number;
  timing_corrections_active: number;
  max_fuel_correction_pct: number;
  max_timing_correction_deg: number;
  engine_family: string;
  ect_enrichment_trigger_f: number;
}

export interface TemplateListResult {
  total_templates: number;
  family: string | null;
  family_count: number;
}

export interface PullData {
  rpm: number[];
  map_kpa: number[];
  ve: number[];
}

export interface ImportVERequest {
  ve_table: number[][];
  rpm_bins: number[];
  map_bins: number[];
}

export interface ImportCorrectionsRequest {
  corrections: number[][];
  rpm_bins: number[];
  map_bins: number[];
  format: "multiplier" | "percentage";
}

export interface FinalizeRequest {
  ve_table_front: number[][];
  operator?: string;
}

export interface VetoRequest {
  rpm: number;
  map_kpa: number;
  reason?: string;
}

export interface SimulatePullRequest {
  rpm?: number;
  map_kpa?: number;
  n_points?: number;
  mode?: "quick" | "realistic";
}

export interface AFRMetrics {
  max_afr_error: number;
  mean_afr_error: number;
  data_points: number;
  zones_corrected: number;
  max_ve_correction_pct: number;
}

export interface SimulatePullResult extends PullResult {
  target_rpm: number;
  target_map_kpa: number;
  mode?: "quick" | "realistic";
  afr_metrics?: AFRMetrics | null;
}

export interface AutoSimulateRequest {
  mode?: "quick" | "realistic";
  max_pulls?: number;
}

export interface AutoSimulatePullSummary {
  pull_number: number;
  observations_added: number;
  mean_uncertainty: number | null;
}

export interface AutoSimulateResult {
  pulls_completed: number;
  converged: boolean;
  final_result: SimulatePullResult | null;
  pull_summary: AutoSimulatePullSummary[];
}

export interface MaterializeRunResult {
  success: boolean;
  run_id: string;
  session_id: string;
  materialized_at: string;
}

export interface ImportBaseVEResult {
  status: string;
  observations_added: number;
}

export interface ImportCorrectionsResult {
  status: string;
  observations_added: number;
  convergence: ConvergenceStatus | null;
  next_suggestion?: PullRecommendation | null;
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export async function createSession(
  payload: CreateSessionPayload
): Promise<SessionInitResult> {
  const response = await api.post<SessionInitResult>("/api/v3/session", payload);
  return response.data;
}

export async function getSession(
  sessionId: string
): Promise<SessionStatus> {
  const response = await api.get<SessionStatus>(
    `/api/v3/session/${encodePathSegment(sessionId)}`
  );
  return response.data;
}

export async function listSessions(): Promise<{ sessions: SessionStatus[] }> {
  const response = await api.get<{ sessions: SessionStatus[] }>("/api/v3/sessions");
  return response.data;
}

export async function ingestPull(
  sessionId: string,
  data: PullData
): Promise<PullResult> {
  const response = await api.post<PullResult>(
    `/api/v3/session/${encodePathSegment(sessionId)}/pull`,
    data
  );
  return response.data;
}

export async function importBaseVE(
  sessionId: string,
  data: ImportVERequest
): Promise<ImportBaseVEResult> {
  const response = await api.post<ImportBaseVEResult>(
    `/api/v3/session/${encodePathSegment(sessionId)}/import-ve`,
    data
  );
  return response.data;
}

export async function finalizeSession(
  sessionId: string,
  data: FinalizeRequest
): Promise<FinalResult> {
  const response = await api.post<FinalResult>(
    `/api/v3/session/${encodePathSegment(sessionId)}/finalize`,
    data
  );
  return response.data;
}

export async function importCorrections(
  sessionId: string,
  data: ImportCorrectionsRequest
): Promise<ImportCorrectionsResult> {
  const response = await api.post<ImportCorrectionsResult>(
    `/api/v3/session/${encodePathSegment(sessionId)}/import-corrections`,
    data
  );
  return response.data;
}

export async function suggestNextPull(
  sessionId: string
): Promise<PullRecommendation> {
  const response = await api.get<PullRecommendation>(
    `/api/v3/session/${encodePathSegment(sessionId)}/next-pull`
  );
  return response.data;
}

export async function checkConvergence(
  sessionId: string
): Promise<ConvergenceStatus> {
  const response = await api.get<ConvergenceStatus>(
    `/api/v3/session/${encodePathSegment(sessionId)}/convergence`
  );
  return response.data;
}

export async function operatorVeto(
  sessionId: string,
  data: VetoRequest
): Promise<{ status: string; rpm: number; map_kpa: number }> {
  const response = await api.post(
    `/api/v3/session/${encodePathSegment(sessionId)}/veto`,
    data
  );
  return response.data;
}

export async function getUncertaintyMap(
  sessionId: string
): Promise<UncertaintyMapResult> {
  const response = await api.get<UncertaintyMapResult>(
    `/api/v3/session/${encodePathSegment(sessionId)}/uncertainty`
  );
  return response.data;
}

export async function getOverlayStatus(
  sessionId: string
): Promise<OverlayStatus> {
  const response = await api.get<OverlayStatus>(
    `/api/v3/session/${encodePathSegment(sessionId)}/overlay`
  );
  return response.data;
}

export async function activateKillSwitch(
  sessionId: string
): Promise<{ status: string; session_id: string }> {
  const response = await api.post(
    `/api/v3/session/${encodePathSegment(sessionId)}/kill-switch`
  );
  return response.data;
}

export async function listTemplates(
  family?: string
): Promise<TemplateListResult> {
  const params = family ? { family } : {};
  const response = await api.get<TemplateListResult>("/api/v3/templates", {
    params,
  });
  return response.data;
}

export async function simulatePull(
  sessionId: string,
  data?: SimulatePullRequest
): Promise<SimulatePullResult> {
  const response = await api.post<SimulatePullResult>(
    `/api/v3/session/${encodePathSegment(sessionId)}/simulate-pull`,
    data || {}
  );
  return response.data;
}

export async function autoSimulate(
  sessionId: string,
  data?: AutoSimulateRequest
): Promise<AutoSimulateResult> {
  const response = await api.post<AutoSimulateResult>(
    `/api/v3/session/${encodePathSegment(sessionId)}/auto-simulate`,
    data || {}
  );
  return response.data;
}

export async function materializeRun(
  sessionId: string
): Promise<MaterializeRunResult> {
  const response = await api.post<MaterializeRunResult>(
    `/api/v3/session/${encodePathSegment(sessionId)}/materialize-run`
  );
  return response.data;
}
