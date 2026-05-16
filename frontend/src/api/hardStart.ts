import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:5001';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000,
});

export type HardStartResult = 'NORMAL_START' | 'MARGINAL_START' | 'HARD_START' | 'NO_START';
export type HardStartSeverity = 'ok' | 'warning' | 'critical';
export type CrankSegmentType = 'NO_START' | 'CATCH' | 'RUN';
export type ActionPriority = 'immediate' | 'soon' | 'monitor';

export interface HardStartSummary {
  result: HardStartResult;
  result_label: string;
  result_severity: HardStartSeverity;
  min_voltage_v: number;
  peak_rpm: number;
  time_to_catch_s: number | null;
  crank_duration_s: number;
}

export interface CrankSegment {
  type: CrankSegmentType;
  label: string;
  start_s: number;
  end_s: number;
  duration_s: number;
  notes: string | null;
}

export interface CrankTimeSample {
  t_s: number;
  rpm: number | null;
  vbatt: number | null;
  map_kpa: number | null;
  spark_f: number | null;
  spark_r: number | null;
  inj_pw_f_ms: number | null;
  inj_pw_r_ms: number | null;
  segment_type: CrankSegmentType | null;
}

export interface HardStartHypothesis {
  rank: number;
  code: string;
  label: string;
  confidence: number;
  evidence: string;
  action: string;
}

export interface RecommendedAction {
  title: string;
  description: string;
  priority: ActionPriority;
}

export interface HardStartAnalysisResponse {
  success: boolean;
  run_id: string;
  filename: string;
  analyzed_at: string;
  summary: HardStartSummary;
  segments: CrankSegment[];
  time_series: CrankTimeSample[];
  hypotheses: HardStartHypothesis[];
  recommended_action: RecommendedAction;
}

export async function analyzeHardStart(file: File): Promise<HardStartAnalysisResponse> {
  const payload = new FormData();
  payload.append('file', file);
  const response = await api.post<HardStartAnalysisResponse>('/api/hard_start/analyze', payload, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
}

export function getMockHardStartResult(filename: string): HardStartAnalysisResponse {
  // TODO: replace with real API call when POST /api/hard_start/analyze is available.
  return {
    success: true,
    run_id: 'hard_start_mock_20260515_001',
    filename,
    analyzed_at: '2026-05-15T20:51:00Z',
    summary: {
      result: 'HARD_START',
      result_label: 'Hard Start Detected',
      result_severity: 'critical',
      min_voltage_v: 9.4,
      peak_rpm: 1480,
      time_to_catch_s: 2.8,
      crank_duration_s: 4.1,
    },
    segments: [
      {
        type: 'NO_START',
        label: 'Initial Crank',
        start_s: 0.0,
        end_s: 2.7,
        duration_s: 2.7,
        notes: 'Cranking with no sustained combustion.',
      },
      {
        type: 'CATCH',
        label: 'First Catch',
        start_s: 2.7,
        end_s: 3.3,
        duration_s: 0.6,
        notes: 'Intermittent combustion and unstable speed.',
      },
      {
        type: 'RUN',
        label: 'Stabilized Idle',
        start_s: 3.3,
        end_s: 4.1,
        duration_s: 0.8,
        notes: 'Idle speed stabilizes.',
      },
    ],
    time_series: [
      { t_s: 0.0, rpm: 0, vbatt: 12.2, map_kpa: 99.0, spark_f: 0.0, spark_r: 0.0, inj_pw_f_ms: 0.0, inj_pw_r_ms: 0.0, segment_type: 'NO_START' },
      { t_s: 0.3, rpm: 180, vbatt: 11.4, map_kpa: 94.0, spark_f: 6.0, spark_r: 5.0, inj_pw_f_ms: 5.8, inj_pw_r_ms: 5.7, segment_type: 'NO_START' },
      { t_s: 0.6, rpm: 320, vbatt: 10.8, map_kpa: 89.0, spark_f: 7.0, spark_r: 6.0, inj_pw_f_ms: 6.1, inj_pw_r_ms: 6.0, segment_type: 'NO_START' },
      { t_s: 0.9, rpm: 410, vbatt: 10.2, map_kpa: 86.0, spark_f: 8.0, spark_r: 7.0, inj_pw_f_ms: 6.4, inj_pw_r_ms: 6.2, segment_type: 'NO_START' },
      { t_s: 1.2, rpm: 460, vbatt: 9.8, map_kpa: 84.0, spark_f: 9.0, spark_r: 8.0, inj_pw_f_ms: 6.5, inj_pw_r_ms: 6.4, segment_type: 'NO_START' },
      { t_s: 1.5, rpm: 500, vbatt: 9.5, map_kpa: 82.0, spark_f: 10.0, spark_r: 9.0, inj_pw_f_ms: 6.8, inj_pw_r_ms: 6.6, segment_type: 'NO_START' },
      { t_s: 1.8, rpm: 540, vbatt: 9.4, map_kpa: 80.0, spark_f: 11.0, spark_r: 10.0, inj_pw_f_ms: 7.0, inj_pw_r_ms: 6.9, segment_type: 'NO_START' },
      { t_s: 2.1, rpm: 590, vbatt: 9.6, map_kpa: 79.0, spark_f: 12.0, spark_r: 11.0, inj_pw_f_ms: 7.1, inj_pw_r_ms: 7.0, segment_type: 'NO_START' },
      { t_s: 2.4, rpm: 630, vbatt: 9.8, map_kpa: 78.0, spark_f: 13.0, spark_r: 12.0, inj_pw_f_ms: 7.2, inj_pw_r_ms: 7.1, segment_type: 'NO_START' },
      { t_s: 2.7, rpm: 700, vbatt: 10.1, map_kpa: 77.0, spark_f: 14.0, spark_r: 13.0, inj_pw_f_ms: 7.4, inj_pw_r_ms: 7.3, segment_type: 'CATCH' },
      { t_s: 2.9, rpm: 930, vbatt: 10.4, map_kpa: 72.0, spark_f: 15.0, spark_r: 14.0, inj_pw_f_ms: 7.0, inj_pw_r_ms: 6.9, segment_type: 'CATCH' },
      { t_s: 3.1, rpm: 1120, vbatt: 10.8, map_kpa: 68.0, spark_f: 16.0, spark_r: 15.0, inj_pw_f_ms: 6.7, inj_pw_r_ms: 6.6, segment_type: 'CATCH' },
      { t_s: 3.3, rpm: 1280, vbatt: 11.2, map_kpa: 62.0, spark_f: 17.0, spark_r: 16.0, inj_pw_f_ms: 6.4, inj_pw_r_ms: 6.3, segment_type: 'RUN' },
      { t_s: 3.5, rpm: 1480, vbatt: 11.5, map_kpa: 58.0, spark_f: 18.0, spark_r: 17.0, inj_pw_f_ms: 6.1, inj_pw_r_ms: 6.0, segment_type: 'RUN' },
      { t_s: 3.7, rpm: 1200, vbatt: 11.8, map_kpa: 56.0, spark_f: 19.0, spark_r: 18.0, inj_pw_f_ms: 5.7, inj_pw_r_ms: 5.6, segment_type: 'RUN' },
      { t_s: 3.9, rpm: 1020, vbatt: 12.0, map_kpa: 54.0, spark_f: 20.0, spark_r: 19.0, inj_pw_f_ms: 5.2, inj_pw_r_ms: 5.1, segment_type: 'RUN' },
      { t_s: 4.1, rpm: 960, vbatt: 12.2, map_kpa: 52.0, spark_f: 21.0, spark_r: 20.0, inj_pw_f_ms: 4.9, inj_pw_r_ms: 4.8, segment_type: 'RUN' },
    ],
    hypotheses: [
      {
        rank: 1,
        code: 'BATTERY_VDROP_DURING_CRANK',
        label: 'Battery voltage drop during crank',
        confidence: 0.88,
        evidence: 'Minimum battery voltage reached 9.4 V during NO_START segment.',
        action: 'Charge/test battery and inspect starter current draw.',
      },
      {
        rank: 2,
        code: 'CATCH_PHASE_UNSTABLE',
        label: 'Unstable first combustion catch',
        confidence: 0.72,
        evidence: 'RPM oscillates before sustained RUN segment.',
        action: 'Inspect idle air path and verify warm-up strategy settings.',
      },
      {
        rank: 3,
        code: 'INJECTION_ASYMMETRY_DURING_CRANK',
        label: 'Front/rear crank pulse width mismatch',
        confidence: 0.41,
        evidence: 'Small front/rear injector pulse differences during NO_START.',
        action: 'Verify injector health and cylinder-level fueling trims.',
      },
    ],
    recommended_action: {
      title: 'Validate electrical system before further tuning changes',
      description: 'Address crank-time voltage sag first, then repeat a controlled start capture.',
      priority: 'immediate',
    },
  };
}

