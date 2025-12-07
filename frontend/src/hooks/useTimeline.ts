/**
 * VE Table Time Machine - Timeline Hook
 * 
 * React hook for managing timeline state and playback.
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
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
  
  // Loading states
  isLoading: boolean;
  isLoadingReplay: boolean;
  isLoadingDiff: boolean;
  
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

  // Fetch timeline
  const {
    data: timeline,
    isLoading: isLoadingTimeline,
    error: timelineError,
    refetch: refetchTimeline,
  } = useQuery({
    queryKey: ['timeline', runId],
    queryFn: () => getTimeline(runId),
    enabled: enabled && !!runId,
    staleTime: 30000, // 30 seconds
  });

  // Fetch current step replay data
  const {
    data: currentReplay,
    isLoading: isLoadingReplay,
  } = useQuery({
    queryKey: ['timeline-replay', runId, currentStep],
    queryFn: () => replayStep(runId, currentStep),
    enabled: enabled && !!runId && currentStep > 0 && !!timeline?.events.length,
    staleTime: 60000, // 1 minute
  });

  // Total steps
  const totalSteps = timeline?.events.length ?? 0;

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
    if (!currentReplay?.snapshot) return;
    
    // Find current snapshot ID
    const currentEvent = timeline?.events[currentStep - 1];
    const currentSnapshotId = currentEvent?.snapshot_after?.id;
    
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
  }, [runId, timeline, currentStep, currentReplay]);

  const compareSteps = useCallback(async (fromStep: number, toStep: number) => {
    if (!timeline?.events.length) return;
    
    const fromEvent = timeline.events[fromStep - 1];
    const toEvent = timeline.events[toStep - 1];
    
    const fromSnapshotId = fromEvent?.snapshot_after?.id;
    const toSnapshotId = toEvent?.snapshot_after?.id;
    
    if (!fromSnapshotId || !toSnapshotId) return;
    
    setIsLoadingDiff(true);
    try {
      const diffResult = await getDiff(runId, fromSnapshotId, toSnapshotId);
      setDiff(diffResult);
    } catch (err) {
      console.error('Failed to compute diff:', err);
    } finally {
      setIsLoadingDiff(false);
    }
  }, [runId, timeline]);

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
    if (timeline && currentStep > timeline.events.length) {
      setCurrentStep(Math.max(1, timeline.events.length));
    }
  }, [timeline, currentStep]);

  return {
    // Data
    timeline: timeline ?? null,
    currentStep,
    totalSteps,
    currentReplay: currentReplay ?? null,
    diff,
    
    // Loading states
    isLoading: isLoadingTimeline,
    isLoadingReplay,
    isLoadingDiff,
    
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
  };
}

export default useTimeline;

