/**
 * Tuning Wizards API - One-click solutions for V-twin tuning
 */

import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:5001';

const api = axios.create({
    baseURL: API_BASE_URL,
    timeout: 30000,
    headers: {
        'Content-Type': 'application/json',
    },
});

// ============================================================================
// Types
// ============================================================================

export interface StagePreset {
    level: string;
    display_name: string;
    description: string;
    ve_scaling: {
        multiplier_min: number;
        multiplier_max: number;
        percentage_range: string;
    };
    afr_targets: {
        cruise: number;
        wot: number;
        idle: number;
    };
    tuning_params: {
        suggested_clamp: number;
        idle_rpm_target: number;
    };
    notes: string[];
}

export interface CamPreset {
    family: string;
    display_name: string;
    description: string;
    lift_range: string;
    idle_characteristics: {
        vacuum_expected_hg: number;
        rpm_min: number;
        rpm_target: number;
        ve_offset_pct: number;
    };
    afr_targets: {
        idle: number;
        cruise: number;
        wot: number;
    };
    decel_enrichment_multiplier: number;
    notes: string[];
}

export interface DecelSeverityOption {
    value: 'low' | 'medium' | 'high';
    label: string;
    description: string;
    fuel_economy_impact: string;
}

export interface WizardConfig {
    stages: StagePreset[];
    cams: CamPreset[];
    decel_severities: DecelSeverityOption[];
}

export interface DecelPreviewResult {
    success: boolean;
    severity_applied: string;
    cells_modified: number;
    rpm_range: [number, number];
    enrichment_preview: {
        by_rpm_zone: Record<string, number>;
        max_enrichment: number;
        avg_enrichment: number;
    };
    warnings: string[];
    recommendations: string[];
}

export interface DecelApplyResult extends DecelPreviewResult {
    overlay_path: string;
    metadata_path: string;
    download_url: string;
    result: DecelPreviewResult;
}

export interface HeatSoakPull {
    pull_number: number;
    peak_hp: number;
    peak_torque: number;
    peak_rpm: number;
    iat_start: number;
    iat_end: number;
    iat_peak: number;
    ambient_temp?: number;
}

export interface HeatSoakAnalysis {
    summary: {
        total_pulls: number;
        hp_degradation_pct: number;
        is_heat_soaked: boolean;
        confidence: number;
        baseline_pull: number;
    };
    recommendation: string;
    warnings: string[];
    pulls: HeatSoakPull[];
}

export interface QuickHeatCheckResult {
    status: 'ok' | 'heat_soaked' | 'insufficient_data';
    hp_degradation_pct?: number;
    recommendation: string;
    warnings: string[];
    use_baseline_pull?: number;
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Get all wizard configuration options
 */
export const getWizardConfig = async (): Promise<WizardConfig> => {
    const response = await api.get('/api/wizards/config');
    return response.data;
};

/**
 * Get all stage presets
 */
export const getStagePresets = async (): Promise<{ presets: StagePreset[] }> => {
    const response = await api.get('/api/wizards/stages');
    return response.data;
};

/**
 * Get a specific stage preset
 */
export const getStagePreset = async (level: string): Promise<StagePreset> => {
    const response = await api.get(`/api/wizards/stages/${level}`);
    return response.data;
};

/**
 * Get all cam presets
 */
export const getCamPresets = async (): Promise<{ presets: CamPreset[] }> => {
    const response = await api.get('/api/wizards/cams');
    return response.data;
};

/**
 * Get a specific cam preset
 */
export const getCamPreset = async (family: string): Promise<CamPreset> => {
    const response = await api.get(`/api/wizards/cams/${family}`);
    return response.data;
};

/**
 * Preview decel pop fix without applying
 */
export const previewDecelFix = async (params: {
    severity?: 'low' | 'medium' | 'high';
    rpm_min?: number;
    rpm_max?: number;
    cam_family?: string;
}): Promise<DecelPreviewResult> => {
    const response = await api.post('/api/wizards/decel/preview', params);
    return response.data;
};

/**
 * Apply decel pop fix and generate overlay
 */
export const applyDecelFix = async (params: {
    severity?: 'low' | 'medium' | 'high';
    rpm_min?: number;
    rpm_max?: number;
    cam_family?: string;
    run_id?: string;
}): Promise<DecelApplyResult> => {
    const response = await api.post('/api/wizards/decel/apply', params);
    return response.data;
};

/**
 * Analyze heat soak across multiple pulls
 */
export const analyzeHeatSoak = async (pulls: HeatSoakPull[]): Promise<HeatSoakAnalysis> => {
    const response = await api.post('/api/wizards/heat-soak/analyze', { pulls });
    return response.data;
};

/**
 * Quick heat soak check with just HP values
 */
export const quickHeatCheck = async (
    hp_values: number[],
    iat_values?: number[]
): Promise<QuickHeatCheckResult> => {
    const response = await api.post('/api/wizards/heat-soak/quick-check', {
        hp_values,
        iat_values,
    });
    return response.data;
};

/**
 * Get download URL for decel overlay
 */
export const getDecelOverlayDownloadUrl = (outputId: string): string => {
    return `${API_BASE_URL}/api/wizards/decel/download/${outputId}`;
};

export default api;

