import type { ManifestData, VEData } from './types';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:5001/api';

interface ApiErrorPayload {
    error?: string;
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
    typeof value === 'object' && value !== null;

const parseJson = async <T>(response: Response): Promise<T> => {
    const data = (await response.json()) as unknown;
    return data as T;
};

const getErrorMessage = (payload: unknown, fallback: string): string => {
    if (isRecord(payload)) {
        const maybeError = payload.error;
        if (typeof maybeError === 'string' && typeof maybeError.trim === 'function' && maybeError.trim().length > 0) {
            return maybeError;
        }
    }
    return fallback;
};

export interface AnalysisProgress {
    progress: number;
    message: string;
}

const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

/**
 * Upload CSV file and run analysis using the Python backend
 */
export async function runRealAnalysis(
    file: File,
    onProgress: (progress: number, message: string) => void
): Promise<ManifestData> {
    const formData = new FormData();
    formData.append('file', file);

    onProgress(10, 'Uploading file...');

    try {
        const response = await fetch(`${API_BASE_URL}/analyze`, {
            method: 'POST',
            body: formData,
        });

        // Backend can return either:
        // - 200/201 with final manifest (synchronous)
        // - 202 Accepted with { runId, status, message } (asynchronous background job)
        if (!response.ok && response.status !== 202) {
            const errorBody = await parseJson<ApiErrorPayload>(response);
            throw new Error(getErrorMessage(errorBody, 'Analysis failed'));
        }

        // If this is the async path (202), poll status until completed
        if (response.status === 202) {
            type Queued = { runId?: string; status?: string; message?: string };
            const queued = await parseJson<Queued>(response);
            const runId = queued.runId;
            if (!runId) {
                throw new Error('Analysis queued but no runId returned');
            }

            onProgress(20, 'Queued...');

            const maxAttempts = 180; // ~3 minutes at 1s
            for (let attempt = 0; attempt < maxAttempts; attempt++) {
                const statusResp = await fetch(`${API_BASE_URL}/status/${runId}`);
                if (!statusResp.ok) {
                    // brief backoff and continue
                    await sleep(1000);
                    continue;
                }
                const statusData = await statusResp.json() as {
                    status?: string;
                    progress?: number;
                    message?: string;
                    manifest?: ManifestData;
                };

                const p = typeof statusData.progress === 'number' ? statusData.progress : undefined;
                if (p !== undefined) {
                    onProgress(Math.min(95, Math.max(25, p)), statusData.message || 'Processing...');
                } else {
                    onProgress(50, statusData.message || 'Processing...');
                }

                if (statusData.status === 'completed' && statusData.manifest) {
                    onProgress(100, 'Analysis complete');
                    return statusData.manifest;
                }

                if (statusData.status === 'error') {
                    throw new Error(statusData.message || 'Analysis failed');
                }

                await sleep(1000);
            }

            throw new Error('Analysis timeout - please try again');
        }

        onProgress(50, 'Processing data...');

        const manifest = await parseJson<ManifestData>(response);

        onProgress(100, 'Analysis complete');

        return manifest;
    } catch (error) {
        console.error('Analysis error:', error);
        throw error;
    }
}

/**
 * Fetch VE data for visualization from completed analysis
 */
export async function fetchVEData(runId: string): Promise<VEData> {
    try {
        const response = await fetch(`${API_BASE_URL}/ve-data/${runId}`);

        if (!response.ok) {
            const errorBody = await parseJson<ApiErrorPayload>(response);
            throw new Error(getErrorMessage(errorBody, 'Failed to fetch VE data'));
        }

        return parseJson<VEData>(response);
    } catch (error) {
        console.error('VE data fetch error:', error);
        throw error;
    }
}

/**
 * Download a specific output file
 */
export function downloadOutputFile(runId: string, filename: string): void {
    const url = `${API_BASE_URL}/download/${runId}/${filename}`;
    window.open(url, '_blank');
}

/**
 * Check API health
 */
export async function checkAPIHealth(): Promise<boolean> {
    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        const data = await parseJson<{ status?: string }>(response);
        return data.status === 'ok';
    } catch (error) {
        console.error('API health check failed:', error);
        return false;
    }
}

/**
 * List all available analysis runs
 */
export interface RunSummary {
    runId: string;
    timestamp: string;
    inputFile: string;
}

export async function listRuns(): Promise<RunSummary[]> {
    try {
        const response = await fetch(`${API_BASE_URL}/runs`);
        const data = await parseJson<{ runs?: RunSummary[] }>(response);
        return data.runs ?? [];
    } catch (error) {
        console.error('Failed to list runs:', error);
        return [];
    }
}
