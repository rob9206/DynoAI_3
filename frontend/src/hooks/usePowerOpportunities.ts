/**
 * Hook for fetching power opportunities analysis
 */

import { useQuery } from '@tanstack/react-query';

interface PowerOpportunity {
    type: string;
    rpm: number;
    kpa: number;
    suggestion: string;
    estimated_gain_hp: number;
    confidence: number;
    coverage: number;
    current_hp?: number;
    details: {
        afr_error_pct?: number;
        suggested_change_pct?: number;
        suggested_afr_change_pct?: number;
        advance_deg?: number;
        current_suggestion_deg?: number;
        knock_front: number;
        knock_rear: number;
    };
}

interface PowerOpportunitiesData {
    summary: {
        total_opportunities: number;
        total_estimated_gain_hp: number;
        analysis_date: string;
    };
    opportunities: PowerOpportunity[];
    safety_notes: string[];
}

interface PowerOpportunitiesResponse {
    success: boolean;
    run_id: string;
    data: PowerOpportunitiesData;
    error?: string;
}

export function usePowerOpportunities(runId: string | null, apiUrl: string = 'http://127.0.0.1:5001') {
    return useQuery<PowerOpportunitiesData | null>({
        queryKey: ['power-opportunities', runId],
        queryFn: async () => {
            if (!runId) return null;

            const response = await fetch(`${apiUrl}/api/jetdrive/power-opportunities/${runId}`);
            
            if (!response.ok) {
                // If 404, power opportunities not available for this run
                if (response.status === 404) {
                    return null;
                }
                throw new Error('Failed to fetch power opportunities');
            }

            const result: PowerOpportunitiesResponse = await response.json();
            
            if (!result.success) {
                throw new Error(result.error || 'Failed to fetch power opportunities');
            }

            return result.data;
        },
        enabled: !!runId,
        staleTime: 5 * 60 * 1000, // 5 minutes
        retry: false, // Don't retry on 404
    });
}

