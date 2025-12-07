/**
 * VE Table Time Machine - Timeline API Client
 * 
 * Fetches session timeline, snapshots, and diffs from the backend.
 */

import api from '@/lib/api';

// ============================================================================
// Types
// ============================================================================

export interface VESnapshot {
  id: string;
  timestamp: string;
  source_file: string;
  sha256: string;
  rows: number;
  cols: number;
}

export interface TimelineEvent {
  id: string;
  sequence: number;
  type: 'analysis' | 'apply' | 'rollback' | 'baseline';
  timestamp: string;
  description: string;
  snapshot_before: VESnapshot | null;
  snapshot_after: VESnapshot | null;
  metadata: Record<string, unknown>;
}

export interface SessionSummary {
  run_id: string;
  created_at: string;
  updated_at: string;
  total_events: number;
  event_counts: {
    baseline: number;
    analysis: number;
    apply: number;
    rollback: number;
  };
  active_snapshot_id: string | null;
}

export interface TimelineResponse {
  run_id: string;
  summary: SessionSummary;
  events: TimelineEvent[];
}

export interface SnapshotData {
  snapshot_id: string;
  rpm: number[];
  load: number[];
  data: number[][];
}

export interface DiffSummary {
  cells_changed: number;
  total_cells: number;
  avg_change: number;
  max_change: number;
  min_change: number;
}

export interface CellChange {
  rpm: number;
  load: number;
  from: number;
  to: number;
  delta: number;
}

export interface DiffResponse {
  rpm: number[];
  load: number[];
  diff: number[][];
  from_snapshot_id: string;
  to_snapshot_id: string;
  summary: DiffSummary;
  changes: CellChange[];
}

export interface ReplayStepResponse {
  step: number;
  total_steps: number;
  event: TimelineEvent;
  snapshot: {
    rpm: number[];
    load: number[];
    data: number[][];
  } | null;
  has_previous: boolean;
  has_next: boolean;
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Get the complete timeline for a run.
 */
export async function getTimeline(runId: string): Promise<TimelineResponse> {
  const response = await api.get(`/api/timeline/${runId}`);
  return response.data;
}

/**
 * Get details for a specific timeline event.
 */
export async function getEvent(runId: string, eventId: string): Promise<TimelineEvent> {
  const response = await api.get(`/api/timeline/${runId}/events/${eventId}`);
  return response.data;
}

/**
 * Get parsed data for a snapshot.
 */
export async function getSnapshot(runId: string, snapshotId: string): Promise<SnapshotData> {
  const response = await api.get(`/api/timeline/${runId}/snapshots/${snapshotId}`);
  return response.data;
}

/**
 * Download a snapshot as CSV.
 */
export async function downloadSnapshot(runId: string, snapshotId: string): Promise<Blob> {
  const response = await api.get(`/api/timeline/${runId}/snapshots/${snapshotId}?format=csv`, {
    responseType: 'blob',
  });
  return response.data;
}

/**
 * Compute difference between two snapshots.
 */
export async function getDiff(
  runId: string,
  fromSnapshotId: string,
  toSnapshotId: string
): Promise<DiffResponse> {
  const response = await api.get(`/api/timeline/${runId}/diff`, {
    params: { from: fromSnapshotId, to: toSnapshotId },
  });
  return response.data;
}

/**
 * Compare VE state between two events.
 */
export async function compareEvents(
  runId: string,
  fromEventId: string,
  toEventId: string
): Promise<DiffResponse & { from_event: TimelineEvent; to_event: TimelineEvent }> {
  const response = await api.get(`/api/timeline/${runId}/compare-events`, {
    params: { from_event: fromEventId, to_event: toEventId },
  });
  return response.data;
}

/**
 * Get the VE state at a specific step in the timeline.
 */
export async function replayStep(runId: string, step: number): Promise<ReplayStepResponse> {
  const response = await api.get(`/api/timeline/${runId}/replay/${step}`);
  return response.data;
}

/**
 * Export timeline as JSON for archiving or sharing.
 */
export function exportTimelineAsJSON(timeline: TimelineResponse, runId: string): void {
  const exportData = {
    exported_at: new Date().toISOString(),
    schema_version: "1.0.0",
    run_id: runId,
    ...timeline,
  };
  
  const json = JSON.stringify(exportData, null, 2);
  const blob = new Blob([json], { type: 'application/json' });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `timeline_${runId}_${new Date().toISOString().split('T')[0]}.json`;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Get a human-readable label for an event type.
 */
export function getEventTypeLabel(type: TimelineEvent['type']): string {
  const labels: Record<TimelineEvent['type'], string> = {
    baseline: 'Baseline',
    analysis: 'Analysis',
    apply: 'Apply',
    rollback: 'Rollback',
  };
  return labels[type] || type;
}

/**
 * Get icon name for an event type (for use with Lucide icons).
 */
export function getEventTypeIcon(type: TimelineEvent['type']): string {
  const icons: Record<TimelineEvent['type'], string> = {
    baseline: 'FileText',
    analysis: 'Search',
    apply: 'Check',
    rollback: 'Undo2',
  };
  return icons[type] || 'Circle';
}

/**
 * Format a timestamp for display.
 */
export function formatTimestamp(timestamp: string): string {
  return new Date(timestamp).toLocaleString();
}

/**
 * Format a relative time (e.g., "2 minutes ago").
 */
export function formatRelativeTime(timestamp: string): string {
  const now = new Date();
  const then = new Date(timestamp);
  const diffMs = now.getTime() - then.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return then.toLocaleDateString();
}

