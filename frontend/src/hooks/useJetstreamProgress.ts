/**
 * Hook for SSE progress streaming
 */

import { useState, useEffect, useCallback } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:5001';

export interface ProgressState {
  stage: string | null;
  substage: string | null;
  progress: number | null;
  error: { stage: string; code: string; message: string } | null;
  complete: boolean;
  connected: boolean;
}

/**
 * Hook to subscribe to SSE progress events for a run
 */
export function useJetstreamProgress(runId: string | undefined) {
  const [state, setState] = useState<ProgressState>({
    stage: null,
    substage: null,
    progress: null,
    error: null,
    complete: false,
    connected: false,
  });

  useEffect(() => {
    if (!runId) return;

    const eventSource = new EventSource(
      `${API_BASE_URL}/api/jetstream/progress/${runId}`
    );

    eventSource.addEventListener('connected', () => {
      setState((prev) => ({ ...prev, connected: true }));
    });

    eventSource.addEventListener('stage', (event: MessageEvent<string>) => {
      const data = JSON.parse(event.data) as {
        stage: string;
        substage: string | null;
        progress: number | null;
      };
      setState((prev) => ({
        ...prev,
        stage: data.stage,
        substage: data.substage,
        progress: data.progress,
      }));
    });

    eventSource.addEventListener('complete', (_event: MessageEvent<string>) => {
      setState((prev) => ({
        ...prev,
        complete: true,
        progress: 100,
      }));
      eventSource.close();
    });

    eventSource.addEventListener('error', (event: Event) => {
      // Check if this is an SSE error event with data
      if (event instanceof MessageEvent) {
        const messageEvent = event as MessageEvent<string>;
        const data = JSON.parse(messageEvent.data) as {
          error: { stage: string; code: string; message: string };
        };
        setState((prev) => ({
          ...prev,
          error: data.error,
        }));
      } else {
        // Connection error
        setState((prev) => ({
          ...prev,
          connected: false,
        }));
      }
      eventSource.close();
    });

    eventSource.onerror = () => {
      setState((prev) => ({ ...prev, connected: false }));
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [runId]);

  const reset = useCallback(() => {
    setState({
      stage: null,
      substage: null,
      progress: null,
      error: null,
      complete: false,
      connected: false,
    });
  }, []);

  return { ...state, reset };
}
