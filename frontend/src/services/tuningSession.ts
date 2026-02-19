/**
 * Tuning Session Service - localStorage session management
 *
 * Provides persistent storage for tuning sessions with:
 * - Current session state
 * - Session history
 * - Rollback support with SHA-256 hashes
 */

import {
  TuningSession,
  DualCylinderVE,
  DualCylinderHits,
  DualCylinderCorrections,
  VEBoundsPreset,
} from '../types/veApplyTypes';

// Storage keys
const STORAGE_KEYS = {
  currentSession: 'dynoai_tuning_session',
  sessionHistory: 'dynoai_session_history',
  lastExport: 'dynoai_last_export',
} as const;

// Maximum history entries to keep
const MAX_HISTORY_ENTRIES = 10;

/**
 * Generate a unique session ID
 */
function generateSessionId(): string {
  return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Calculate SHA-256 hash of a grid (for rollback verification)
 */
async function hashGrid(grid: number[][]): Promise<string> {
  const data = JSON.stringify(grid);
  const encoder = new TextEncoder();
  const buffer = await crypto.subtle.digest('SHA-256', encoder.encode(data));
  const hashArray = Array.from(new Uint8Array(buffer));
  return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Create a new tuning session
 */
export function createSession(
  baseVE: DualCylinderVE,
  afrTargets: Record<number, number>,
  rpmAxis: number[],
  mapAxis: number[],
  enginePreset: string,
  veBoundsPreset: VEBoundsPreset = 'na_harley',
  sourceFile?: string
): TuningSession {
  const now = new Date().toISOString();

  // Initialize empty corrections and hit counts
  const emptyGrid = rpmAxis.map(() => mapAxis.map(() => 0));
  const unityGrid = rpmAxis.map(() => mapAxis.map(() => 1.0));

  return {
    id: generateSessionId(),
    createdAt: now,
    lastModified: now,
    enginePreset,
    veBoundsPreset,
    sourceFile,
    baseVE,
    corrections: { front: unityGrid, rear: unityGrid.map((r) => [...r]) },
    hitCounts: {
      front: emptyGrid,
      rear: emptyGrid.map((r) => [...r]),
    },
    afrTargets,
    rpmAxis,
    mapAxis,
    status: 'collecting',
  };
}

/**
 * Save session to localStorage
 */
export function saveSession(session: TuningSession): void {
  try {
    session.lastModified = new Date().toISOString();
    localStorage.setItem(STORAGE_KEYS.currentSession, JSON.stringify(session));
  } catch (error) {
    console.error('Failed to save session:', error);
    throw new Error('Failed to save tuning session');
  }
}

/**
 * Load session from localStorage
 */
export function loadSession(): TuningSession | null {
  try {
    const data = localStorage.getItem(STORAGE_KEYS.currentSession);
    if (!data) return null;
    return JSON.parse(data) as TuningSession;
  } catch (error) {
    console.error('Failed to load session:', error);
    return null;
  }
}

/**
 * Clear current session
 */
export function clearSession(): void {
  localStorage.removeItem(STORAGE_KEYS.currentSession);
}

/**
 * Update session with live data
 */
export function updateSessionWithLiveData(
  session: TuningSession,
  corrections: DualCylinderCorrections,
  hitCounts: DualCylinderHits
): TuningSession {
  return {
    ...session,
    corrections,
    hitCounts,
    lastModified: new Date().toISOString(),
    status: 'collecting',
  };
}

/**
 * Mark session as ready to apply
 */
export function markSessionReadyToApply(session: TuningSession): TuningSession {
  return {
    ...session,
    status: 'ready_to_apply',
    lastModified: new Date().toISOString(),
  };
}

/**
 * Mark session as applied and add hashes for rollback
 */
export async function markSessionApplied(
  session: TuningSession,
  appliedVE: DualCylinderVE
): Promise<TuningSession> {
  const baseHash = await hashGrid([
    ...session.baseVE.front,
    ...session.baseVE.rear,
  ]);
  const appliedHash = await hashGrid([
    ...appliedVE.front,
    ...appliedVE.rear,
  ]);

  return {
    ...session,
    status: 'applied',
    lastModified: new Date().toISOString(),
    hashes: {
      base: baseHash,
      applied: appliedHash,
    },
  };
}

// Session history management

interface SessionHistoryEntry {
  id: string;
  createdAt: string;
  appliedAt: string;
  enginePreset: string;
  sourceFile?: string;
  cellsModified: number;
  baseHash: string;
  appliedHash: string;
}

/**
 * Add session to history
 */
export function addSessionToHistory(
  session: TuningSession,
  cellsModified: number
): void {
  if (!session.hashes) return;

  try {
    const history = getSessionHistory();

    const entry: SessionHistoryEntry = {
      id: session.id,
      createdAt: session.createdAt,
      appliedAt: new Date().toISOString(),
      enginePreset: session.enginePreset,
      sourceFile: session.sourceFile,
      cellsModified,
      baseHash: session.hashes.base,
      appliedHash: session.hashes.applied,
    };

    // Add to beginning, keep only MAX_HISTORY_ENTRIES
    history.unshift(entry);
    if (history.length > MAX_HISTORY_ENTRIES) {
      history.pop();
    }

    localStorage.setItem(STORAGE_KEYS.sessionHistory, JSON.stringify(history));
  } catch (error) {
    console.error('Failed to add session to history:', error);
  }
}

/**
 * Get session history
 */
export function getSessionHistory(): SessionHistoryEntry[] {
  try {
    const data = localStorage.getItem(STORAGE_KEYS.sessionHistory);
    if (!data) return [];
    return JSON.parse(data) as SessionHistoryEntry[];
  } catch (error) {
    console.error('Failed to load session history:', error);
    return [];
  }
}

/**
 * Clear session history
 */
export function clearSessionHistory(): void {
  localStorage.removeItem(STORAGE_KEYS.sessionHistory);
}

// Last export tracking

interface LastExportInfo {
  timestamp: string;
  sessionId: string;
  format: string;
  filename: string;
}

/**
 * Record last export
 */
export function recordLastExport(
  sessionId: string,
  format: string,
  filename: string
): void {
  try {
    const info: LastExportInfo = {
      timestamp: new Date().toISOString(),
      sessionId,
      format,
      filename,
    };
    localStorage.setItem(STORAGE_KEYS.lastExport, JSON.stringify(info));
  } catch (error) {
    console.error('Failed to record last export:', error);
  }
}

/**
 * Get last export info
 */
export function getLastExportInfo(): LastExportInfo | null {
  try {
    const data = localStorage.getItem(STORAGE_KEYS.lastExport);
    if (!data) return null;
    return JSON.parse(data) as LastExportInfo;
  } catch (error) {
    console.error('Failed to load last export info:', error);
    return null;
  }
}
