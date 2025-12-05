import { useQuery } from '@tanstack/react-query';
import { getVEData, type VEData } from '@/lib/api';

export function useVEData(runId: string | undefined) {
    return useQuery({
        queryKey: ['ve-data', runId],
        queryFn: async () => {
            if (!runId) throw new Error('Run ID is required');
            return await getVEData(runId);
        },
        enabled: !!runId,
        staleTime: 5 * 60 * 1000, // 5 minutes
    });
}

