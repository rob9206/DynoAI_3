import axios from 'axios';

const client = axios.create({ baseURL: '/api' });

// Types
export interface FDCAnalysis {
  overall: number;
  low_map: number;
  high_map: number;
  stability_score: number;
  is_stable: boolean;
}

export interface ValidationIssue {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface BaselineSummary {
  measured_cells: number;
  interpolated_cells: number;
  extrapolated_cells: number;
  total_cells: number;
  avg_confidence: number;
  min_confidence: number;
  fdc_value: number;
  fdc_stable: boolean;
}

export interface BaselinePreview {
  ve_corrections: number[][];
  confidence_map: number[][];
  cell_types: string[][];
  rpm_axis: number[];
  map_axis: number[];
}

export interface BaselineResult {
  status: 'ok' | 'error';
  baseline_id: string | null;
  summary: BaselineSummary;
  preview: BaselinePreview;
  fdc_analysis: FDCAnalysis;
  validation: {
    is_valid: boolean;
    errors: ValidationIssue[];
    warnings: ValidationIssue[];
  };
  warnings: string[];
  recommendations: string[];
  files: {
    ve_baseline?: string;
    confidence_map?: string;
    diagnostics?: string;
  } | null;
  error?: {
    code: string;
    message: string;
  };
}

// API Functions
export const baselineApi = {
  generate: async (runId: string): Promise<BaselineResult> => {
    const { data } = await client.post('/baseline/generate', { run_id: runId });
    return data;
  },

  generateFromFile: async (filePath: string): Promise<BaselineResult> => {
    const { data } = await client.post('/baseline/generate', { file_path: filePath });
    return data;
  },

  preview: async (runId: string): Promise<BaselineResult> => {
    const { data } = await client.post('/baseline/preview', { run_id: runId });
    return data;
  },
};
