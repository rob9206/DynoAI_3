import {
    useJetDriveLive,
    type DrainedSample,
    type JetDriveChannel,
    type JetDriveDataSource,
    type JetDriveSnapshot,
    type UseJetDriveLiveOptions,
    type UseJetDriveLiveReturn,
} from './useJetDriveLive';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:5001';
const DEFAULT_YOURDYNO_API_URL = `${API_BASE_URL}/api/yourdyno`;

export type UseYourDynoLiveOptions = Omit<UseJetDriveLiveOptions, 'apiUrl'> & {
    apiUrl?: string;
};

export interface UseYourDynoLiveReturn extends UseJetDriveLiveReturn {
    // Keep return shape identical for drop-in compatibility with existing dashboard components.
    channels: Record<string, JetDriveChannel>;
    snapshot: JetDriveSnapshot | null;
    dataSource: JetDriveDataSource;
    consumeDrainedSamples: () => DrainedSample[];
}

/**
 * Thin wrapper around useJetDriveLive for the YourDyno backend.
 *
 * The backend exposes JetDrive-compatible endpoints under /api/yourdyno/hardware/*
 * so existing live dashboard components can be reused with no frontend rewrite.
 */
export function useYourDynoLive(options: UseYourDynoLiveOptions = {}): UseYourDynoLiveReturn {
    const apiUrl = options.apiUrl ?? DEFAULT_YOURDYNO_API_URL;
    return useJetDriveLive({
        ...options,
        apiUrl,
    });
}

export default useYourDynoLive;
