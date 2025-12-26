/**
 * VE Table Time Machine - Timeline Hook
 * 
 * React hook for managing timeline state and playback.
 */

import { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getTimeline,
  replayStep,
  getDiff,
  type TimelineResponse,
  type ReplayStepResponse,
  type DiffResponse,
} from '@/api/timeline';

interface UseTimelineOptions {
  runId: string;
  autoPlayInterval?: number; // milliseconds between steps during autoplay
  enabled?: boolean;
}

interface UseTimelineReturn {
  // Data
  timeline: TimelineResponse | null;
  currentStep: number;
  totalSteps: number;
  currentReplay: ReplayStepResponse | null;
  diff: DiffResponse | null;
  timelineHasMore: boolean;
  timelineLoadedEvents: number;
  
  // Loading states
  isLoading: boolean;
  isLoadingReplay: boolean;
  isLoadingDiff: boolean;
  isLoadingMoreTimeline: boolean;
  
  // Error states
  error: Error | null;
  
  // Actions
  goToStep: (step: number) => void;
  nextStep: () => void;
  prevStep: () => void;
  firstStep: () => void;
  lastStep: () => void;
  
  // Playback
  isPlaying: boolean;
  play: () => void;
  pause: () => void;
  togglePlayback: () => void;
  
  // Diff
  compareToCurrent: (snapshotId: string) => Promise<void>;
  compareSteps: (fromStep: number, toStep: number) => Promise<void>;
  clearDiff: () => void;
  
  // Refresh
  refresh: () => void;

  // Pagination
  loadMoreTimeline: () => Promise<void>;
}

export function useTimeline({
  runId,
  autoPlayInterval = 2000,
  enabled = true,
}: UseTimelineOptions): UseTimelineReturn {
  const queryClient = useQueryClient();
  
  // State
  const [currentStep, setCurrentStep] = useState(1);
  const [isPlaying, setIsPlaying] = useState(false);
  const [diff, setDiff] = useState<DiffResponse | null>(null);
  const [isLoadingDiff, setIsLoadingDiff] = useState(false);
  
  // Refs for playback interval
  const playbackRef = useRef<NodeJS.Timeout | null>(null);
  const ensureLoadingRef = useRef(false);

  // Fetch timeline (paginated)
  const {
    data: timelinePages,
    isLoading: isLoadingTimeline,
    error: timelineError,
    refetch: refetchTimeline,
    hasNextPage,
    fetchNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: ['timeline', runId],
    queryFn: ({ pageParam }) => getTimeline(runId, { limit: 50, offset: pageParam as number }),
    initialPageParam: 0,
    enabled: enabled && !!runId,
    staleTime: 30000, // 30 seconds
    getNextPageParam: (lastPage) => {
      const pagination = lastPage.pagination;
      if (!pagination || !pagination.has_more) return undefined;
      return pagination.offset + pagination.limit;
    },
  });

  const timeline: TimelineResponse | null = useMemo(() => {
    if (!timelinePages?.pages?.length) return null;
    const pages = timelinePages.pages;
    const last = pages[pages.length - 1];
    return {
      run_id: last.run_id,
      summary: last.summary,
      events: pages.flatMap((p) => p.events),
      pagination: last.pagination,
    };
  }, [timelinePages]);

  // Fetch current step replay data
  const {
    data: currentReplay,
    isLoading: isLoadingReplay,
  } = useQuery({
    queryKey: ['timeline-replay', runId, currentStep],
    queryFn: () => replayStep(runId, currentStep),
    enabled: enabled && !!runId && currentStep > 0 && !!timeline?.summary,
    staleTime: 60000, // 1 minute
  });

  // Total steps (prefer server total if provided)
  const totalSteps = useMemo(() => {
    if (!timeline) return 0;
    return (
      timeline.pagination?.total ??
      timeline.summary?.total_events ??
      timeline.events.length
    );
  }, [timeline]);

  const timelineLoadedEvents = timeline?.events.length ?? 0;
  const timelineHasMore = !!(hasNextPage ?? false);

  // ============================================================================
  // Navigation Actions
  // ============================================================================

  const goToStep = useCallback((step: number) => {
    const clampedStep = Math.max(1, Math.min(step, totalSteps));
    setCurrentStep(clampedStep);
    setDiff(null); // Clear diff when navigating
  }, [totalSteps]);

  const nextStep = useCallback(() => {
    if (currentStep < totalSteps) {
      goToStep(currentStep + 1);
    } else {
      // Stop playback at end
      setIsPlaying(false);
    }
  }, [currentStep, totalSteps, goToStep]);

  const prevStep = useCallback(() => {
    goToStep(currentStep - 1);
  }, [currentStep, goToStep]);

  const firstStep = useCallback(() => {
    goToStep(1);
  }, [goToStep]);

  const lastStep = useCallback(() => {
    goToStep(totalSteps);
  }, [totalSteps, goToStep]);

  // ============================================================================
  // Playback Controls
  // ============================================================================

  const play = useCallback(() => {
    if (currentStep >= totalSteps) {
      // Start from beginning if at end
      setCurrentStep(1);
    }
    setIsPlaying(true);
  }, [currentStep, totalSteps]);

  const pause = useCallback(() => {
    setIsPlaying(false);
  }, []);

  const togglePlayback = useCallback(() => {
    if (isPlaying) {
      pause();
    } else {
      play();
    }
  }, [isPlaying, play, pause]);

  // Playback effect
  useEffect(() => {
    if (isPlaying) {
      playbackRef.current = setInterval(() => {
        setCurrentStep((prev) => {
          if (prev >= totalSteps) {
            setIsPlaying(false);
            return prev;
          }
          return prev + 1;
        });
      }, autoPlayInterval);
    } else {
      if (playbackRef.current) {
        clearInterval(playbackRef.current);
        playbackRef.current = null;
      }
    }

    return () => {
      if (playbackRef.current) {
        clearInterval(playbackRef.current);
      }
    };
  }, [isPlaying, totalSteps, autoPlayInterval]);

  // ============================================================================
  // Diff Actions
  // ============================================================================

  const compareToCurrent = useCallback(async (snapshotId: string) => {
    const currentSnapshotId = currentReplay?.event?.snapshot_after?.id;
    if (!currentSnapshotId) return;
    
    setIsLoadingDiff(true);
    try {
      const diffResult = await getDiff(runId, snapshotId, currentSnapshotId);
      setDiff(diffResult);
    } catch (err) {
      console.error('Failed to compute diff:', err);
    } finally {
      setIsLoadingDiff(false);
    }
  }, [runId, currentReplay]);

  const compareSteps = useCallback(async (fromStep: number, toStep: number) => {
    if (!runId) return;
    
    setIsLoadingDiff(true);
    try {
      const [fromReplay, toReplay] = await Promise.all([
        replayStep(runId, fromStep),
        replayStep(runId, toStep),
      ]);

      const fromSnapshotId = fromReplay?.event?.snapshot_after?.id;
      const toSnapshotId = toReplay?.event?.snapshot_after?.id;

      if (!fromSnapshotId || !toSnapshotId) return;

      const diffResult = await getDiff(runId, fromSnapshotId, toSnapshotId);
      setDiff(diffResult);
    } catch (err) {
      console.error('Failed to compute diff:', err);
    } finally {
      setIsLoadingDiff(false);
    }
  }, [runId]);

  const clearDiff = useCallback(() => {
    setDiff(null);
  }, []);

  // ============================================================================
  // Refresh
  // ============================================================================

  const refresh = useCallback(() => {
    void refetchTimeline();
    void queryClient.invalidateQueries({ queryKey: ['timeline-replay', runId] });
  }, [refetchTimeline, queryClient, runId]);

  // Reset step when timeline changes
  useEffect(() => {
    if (timeline && totalSteps > 0 && currentStep > totalSteps) {
      setCurrentStep(Math.max(1, totalSteps));
    }
  }, [timeline, currentStep, totalSteps]);

  // Ensure we have enough events loaded to render the sidebar list for current step
  useEffect(() => {
    if (!enabled || !runId) return;
    if (!hasNextPage) return;
    if (ensureLoadingRef.current) return;
    if (currentStep <= timelineLoadedEvents) return;

    ensureLoadingRef.current = true;
    (async () => {
      try {
        while (currentStep > (timeline?.events.length ?? 0) && hasNextPage) {
          await fetchNextPage();
        }
      } finally {
        ensureLoadingRef.current = false;
      }
    })();
  }, [enabled, runId, currentStep, timelineLoadedEvents, hasNextPage, fetchNextPage, timeline]);

  const loadMoreTimeline = useCallback(async () => {
    if (!hasNextPage) return;
    await fetchNextPage();
  }, [hasNextPage, fetchNextPage]);

  return {
    // Data
    timeline: timeline ?? null,
    currentStep,
    totalSteps,
    currentReplay: currentReplay ?? null,
    diff,
    timelineHasMore,
    timelineLoadedEvents,
    
    // Loading states
    isLoading: isLoadingTimeline,
    isLoadingReplay,
    isLoadingDiff,
    isLoadingMoreTimeline: isFetchingNextPage,
    
    // Error states
    error: timelineError as Error | null,
    
    // Actions
    goToStep,
    nextStep,
    prevStep,
    firstStep,
    lastStep,
    
    // Playback
    isPlaying,
    play,
    pause,
    togglePlayback,
    
    // Diff
    compareToCurrent,
    compareSteps,
    clearDiff,
    
    // Refresh
    refresh,

    // Pagination
    loadMoreTimeline,
  };
}

export default useTimeline;

