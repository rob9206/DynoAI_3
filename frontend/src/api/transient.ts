/**
 * Transient Fuel Compensation API Client
 * 
 * Provides functions to interact with the transient fuel analysis endpoints
 */

import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:5001';

const api = axios.create({
    baseURL: API_BASE_URL,
    timeout: 60000, // 60 seconds - analysis can take time
    headers: {
        'Content-Type': 'application/json',
    },
});

// ============================================================================
// Types
// ============================================================================

export interface TransientEvent {
    type: 'accel' | 'decel';
    severity: 'mild' | 'moderate' | 'aggressive';
    start_time: number;
    end_time: number;
    peak_map_rate: number;
    peak_tps_rate: number;
    avg_rpm: number;
    afr_error_avg: number;
    afr_error_peak: number;
}

export interface MapRateEnrichment {
    map_rate_kpa_per_sec: number;
    enrichment_percent: number;
}

export interface TpsRateEnrichment {
    tps_rate_percent_per_sec: number;
    enrichment_percent: number;
}

export interface WallWettingFactors {
    idle: number;
    low: number;
    mid: number;
    high: number;
    redline: number;
}

export interface TransientAnalysisResult {
    success: boolean;
    run_id: string;
    events_detected: number;
    analysis: {
        accel_events: number;
        decel_events: number;
        events: TransientEvent[];
        recommendations: string[];
        map_rate_table: MapRateEnrichment[];
        tps_rate_table: TpsRateEnrichment[];
        wall_wetting_factors: WallWettingFactors;
    };
    download_url: string;
}

export interface TransientConfig {
    defaults: {
        target_afr: number;
        map_rate_threshold: number;
        tps_rate_threshold: number;
        afr_tolerance: number;
    };
    ranges: {
        target_afr: { min: number; max: number; step: number };
        map_rate_threshold: { min: number; max: number; step: number };
        tps_rate_threshold: { min: number; max: number; step: number };
    };
    severity_descriptions: {
        mild: string;
        moderate: string;
        aggressive: string;
    };
}

export interface TransientAnalyzeParams {
    csv_data: string;
    target_afr?: number;
    map_rate_threshold?: number;
    tps_rate_threshold?: number;
    run_id?: string;
}

export interface TransientAnalyzeFromRunParams {
    target_afr?: number;
    map_rate_threshold?: number;
    tps_rate_threshold?: number;
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Get transient analysis configuration options
 */
export const getTransientConfig = async (): Promise<TransientConfig> => {
    const response = await api.get('/api/transient/config');
    return response.data;
};

/**
 * Analyze transient events in uploaded CSV data
 */
export const analyzeTransients = async (
    params: TransientAnalyzeParams
): Promise<TransientAnalysisResult> => {
    const response = await api.post('/api/transient/analyze', params);
    return response.data;
};

/**
 * Analyze transient events from a previously captured run
 */
export const analyzeTransientsFromRun = async (
    runId: string,
    params?: TransientAnalyzeFromRunParams
): Promise<TransientAnalysisResult> => {
    const response = await api.post(`/api/transient/analyze-from-run/${runId}`, params ?? {});
    return response.data;
};

/**
 * Get download URL for transient compensation export
 */
export const getTransientExportUrl = (outputId: string): string => {
    return `${API_BASE_URL}/api/transient/export/${outputId}`;
};

export default api;

