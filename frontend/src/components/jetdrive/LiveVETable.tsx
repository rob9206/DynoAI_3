/**
 * LiveVETable - Real-time VE table with cell tracing
 * 
 * Shows the VE correction grid with:
 * - Current cell highlighted based on live RPM/MAP
 * - Interpolation weights shown
 * - Hit count accumulation
 * - Color coding for lean/rich/ok cells
 * 
 * Based on Power Vision table format with configurable bins for different engine types.
 */

import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { Target, Activity, Flame, Crosshair, RotateCcw, ChevronDown, Download } from 'lucide-react';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { ENGINE_GRID_CONFIGS, type EnginePreset, type EngineConfig } from '../../utils/enginePresets';

// Export data interface for external consumers
export interface LiveVEExportData {
    frontCorrections: number[][];   // LC1 wideband → Front Cylinder
    rearCorrections: number[][];    // LC2 wideband → Rear Cylinder
    hitCounts: number[][];          // Legacy combined hitCounts (for backward compat)
    frontHitCounts: number[][];     // Per-cylinder hit counts (Front)
    rearHitCounts: number[][];      // Per-cylinder hit counts (Rear)
    rpmBins: number[];
    mapBins: number[];
    afrTargets: Record<number, number>;
    enginePreset: string;
    totalHits: number;
    exportedAt: string;
}

interface LiveVETableProps {
    // Current live values
    currentRpm: number;
    currentMap: number;
    
    // Dual-cylinder AFR tracking (LC1 = Front, LC2 = Rear)
    currentAfrFront?: number;   // LC1 wideband → Front cylinder
    currentAfrRear?: number;    // LC2 wideband → Rear cylinder
    currentAfr?: number;        // @deprecated - use currentAfrFront/Rear instead (falls back to single value)

    // AFR targets - can be a single value (legacy) or a table keyed by MAP
    afrTargets?: Record<number, number>;
    targetAfr?: number;  // @deprecated - use afrTargets instead

    // Mode
    isLive: boolean;

    // Engine preset (default: harley_m8)
    enginePreset?: EnginePreset;
    onEnginePresetChange?: (preset: EnginePreset) => void;

    // Custom bins - override preset bins (used when importing a PVV with different grid)
    customRpmBins?: number[];
    customMapBins?: number[];

    // Optional: Pre-loaded VE corrections from analysis
    veCorrections?: number[][];  // [rpm_idx][map_idx] - multipliers
    hitCounts?: number[][];

    // Callback when cell is clicked
    onCellClick?: (rpmIdx: number, mapIdx: number) => void;
    
    // Export callback - called when user clicks Export button
    onExport?: (data: LiveVEExportData) => void;
    
    // Live data callback - called continuously during data collection for real-time coverage updates
    onLiveDataUpdate?: (data: LiveVEExportData) => void;
}

// Calculate which cells are active and interpolation weights
function calculateCellTrace(
    rpm: number,
    map: number,
    rpmBins: number[],
    mapBins: number[]
): {
    rpmIdx: number;
    mapIdx: number;
    rpmWeight: number;  // 0-1, weight towards higher bin
    mapWeight: number;  // 0-1, weight towards higher bin
    activeCells: { rpmIdx: number; mapIdx: number; weight: number }[];
} {
    // Find RPM bin index
    let rpmIdx = 0;
    for (let i = 0; i < rpmBins.length - 1; i++) {
        if (rpm >= rpmBins[i] && rpm < rpmBins[i + 1]) {
            rpmIdx = i;
            break;
        }
        if (rpm >= rpmBins[rpmBins.length - 1]) {
            rpmIdx = rpmBins.length - 1;
        }
    }

    // Find MAP bin index
    let mapIdx = 0;
    for (let i = 0; i < mapBins.length - 1; i++) {
        if (map >= mapBins[i] && map < mapBins[i + 1]) {
            mapIdx = i;
            break;
        }
        if (map >= mapBins[mapBins.length - 1]) {
            mapIdx = mapBins.length - 1;
        }
    }

    // Calculate interpolation weights
    const rpmLow = rpmBins[Math.min(rpmIdx, rpmBins.length - 1)];
    const rpmHigh = rpmBins[Math.min(rpmIdx + 1, rpmBins.length - 1)];
    const mapLow = mapBins[Math.min(mapIdx, mapBins.length - 1)];
    const mapHigh = mapBins[Math.min(mapIdx + 1, mapBins.length - 1)];

    const rpmWeight = rpmHigh !== rpmLow
        ? Math.min(1, Math.max(0, (rpm - rpmLow) / (rpmHigh - rpmLow)))
        : 0;
    const mapWeight = mapHigh !== mapLow
        ? Math.min(1, Math.max(0, (map - mapLow) / (mapHigh - mapLow)))
        : 0;

    // Calculate active cells with bilinear interpolation weights
    const activeCells: { rpmIdx: number; mapIdx: number; weight: number }[] = [];

    // Four corners for bilinear interpolation
    const w00 = (1 - rpmWeight) * (1 - mapWeight);  // Lower-left
    const w01 = (1 - rpmWeight) * mapWeight;         // Lower-right
    const w10 = rpmWeight * (1 - mapWeight);         // Upper-left
    const w11 = rpmWeight * mapWeight;               // Upper-right

    if (w00 > 0.01) {
        activeCells.push({ rpmIdx, mapIdx, weight: w00 });
    }
    if (w01 > 0.01 && mapIdx + 1 < mapBins.length) {
        activeCells.push({ rpmIdx, mapIdx: mapIdx + 1, weight: w01 });
    }
    if (w10 > 0.01 && rpmIdx + 1 < rpmBins.length) {
        activeCells.push({ rpmIdx: rpmIdx + 1, mapIdx, weight: w10 });
    }
    if (w11 > 0.01 && rpmIdx + 1 < rpmBins.length && mapIdx + 1 < mapBins.length) {
        activeCells.push({ rpmIdx: rpmIdx + 1, mapIdx: mapIdx + 1, weight: w11 });
    }

    return { rpmIdx, mapIdx, rpmWeight, mapWeight, activeCells };
}

// Get cell color based on VE correction
function getCellColor(veCorrection: number, hitCount: number): string {
    if (hitCount === 0) return 'bg-zinc-800/30';

    const delta = (veCorrection - 1) * 100;  // Convert to percentage

    if (Math.abs(delta) < 0.5) return 'bg-green-500/60 text-green-100';
    if (delta > 5) return 'bg-red-500/50 text-red-200';
    if (delta > 2) return 'bg-orange-500/40 text-orange-200';
    if (delta < -5) return 'bg-blue-500/50 text-blue-200';
    if (delta < -2) return 'bg-cyan-500/40 text-cyan-200';
    return 'bg-yellow-500/30 text-yellow-200';
}

// Format VE correction for display
function formatVE(veCorrection: number, hitCount: number): string {
    // Show value even with 0 hits if it's not the default 1.0
    if (hitCount === 0 && veCorrection === 1.0) return '—';
    const delta = (veCorrection - 1) * 100;
    return `${delta >= 0 ? '+' : ''}${delta.toFixed(1)}%`;
}

// Default AFR targets if none provided (matches backend)
const DEFAULT_AFR_TARGETS: Record<number, number> = {
    20: 14.7, 30: 14.7, 40: 14.5, 50: 14.0, 60: 13.5,
    70: 13.0, 80: 12.8, 90: 12.5, 100: 12.2,
};

// Get target AFR for a given MAP value
function getTargetAfrForMap(mapKpa: number, targets: Record<number, number>): number {
    const mapKeys = Object.keys(targets).map(Number).sort((a, b) => a - b);
    if (mapKeys.length === 0) return 14.0;
    let closest = mapKeys[0];
    for (const key of mapKeys) {
        if (Math.abs(key - mapKpa) < Math.abs(closest - mapKpa)) {
            closest = key;
        }
    }
    return targets[closest] ?? 14.0;
}

export function LiveVETable({
    currentRpm,
    currentMap,
    currentAfrFront,
    currentAfrRear,
    currentAfr,  // Legacy single AFR prop
    afrTargets,
    targetAfr,  // Legacy prop
    isLive,
    enginePreset = 'harley_m8',
    onEnginePresetChange,
    customRpmBins,
    customMapBins,
    veCorrections,
    hitCounts: externalHitCounts,
    onCellClick,
    onExport,
    onLiveDataUpdate,
}: LiveVETableProps) {
    // Resolve AFR values - prefer dual-cylinder, fall back to single
    const resolvedAfrFront = currentAfrFront ?? currentAfr ?? 0;
    const resolvedAfrRear = currentAfrRear ?? currentAfr ?? resolvedAfrFront;
    // Use afrTargets if provided, otherwise fall back to legacy targetAfr or defaults
    const resolvedAfrTargets = useMemo(() => {
        if (afrTargets) return afrTargets;
        if (targetAfr !== undefined) {
            // Legacy: use flat targetAfr for WOT, scale others proportionally
            const ratio = targetAfr / DEFAULT_AFR_TARGETS[100];
            return Object.fromEntries(
                Object.entries(DEFAULT_AFR_TARGETS).map(([k, v]) => [Number(k), v * ratio])
            );
        }
        return DEFAULT_AFR_TARGETS;
    }, [afrTargets, targetAfr]);
    // Engine type selector state (local if no external handler)
    const [localPreset, setLocalPreset] = useState<EnginePreset>(enginePreset);
    const [showPresetMenu, setShowPresetMenu] = useState(false);

    const activePreset = onEnginePresetChange ? enginePreset : localPreset;
    const config = ENGINE_GRID_CONFIGS[activePreset];
    
    // Use custom bins if provided (from imported tune), otherwise use preset bins
    // Deduplicate to prevent duplicate rows/columns in the grid
    const rpmBins = useMemo(() => {
        const raw = customRpmBins ?? config.rpmBins;
        const rounded = raw.map(b => Math.round(b));
        const unique = [...new Set(rounded)].sort((a, b) => a - b);
        return unique;
    }, [customRpmBins, config.rpmBins]);
    const mapBins = useMemo(() => {
        const raw = customMapBins ?? config.mapBins;
        const rounded = raw.map(b => Math.round(b));
        const unique = [...new Set(rounded)].sort((a, b) => a - b);
        return unique;
    }, [customMapBins, config.mapBins]);

    const handlePresetChange = useCallback((preset: EnginePreset) => {
        if (onEnginePresetChange) {
            onEnginePresetChange(preset);
        } else {
            setLocalPreset(preset);
        }
        setShowPresetMenu(false);
    }, [onEnginePresetChange]);

    // Internal hit count tracking (accumulates during live session)
    // Combined legacy hitCounts (for backward compat and display)
    const [liveHitCounts, setLiveHitCounts] = useState<number[][]>(() =>
        rpmBins.map(() => mapBins.map(() => 0))
    );
    // Per-cylinder hit counts (Front = LC1, Rear = LC2)
    const [frontHitCounts, setFrontHitCounts] = useState<number[][]>(() =>
        rpmBins.map(() => mapBins.map(() => 0))
    );
    const [rearHitCounts, setRearHitCounts] = useState<number[][]>(() =>
        rpmBins.map(() => mapBins.map(() => 0))
    );

    // AFR accumulators for live corrections - DUAL CYLINDER
    // Front cylinder (LC1 wideband)
    const [frontAfrAccumulator, setFrontAfrAccumulator] = useState<{ sum: number; count: number }[][]>(() =>
        rpmBins.map(() => mapBins.map(() => ({ sum: 0, count: 0 })))
    );
    // Rear cylinder (LC2 wideband)
    const [rearAfrAccumulator, setRearAfrAccumulator] = useState<{ sum: number; count: number }[][]>(() =>
        rpmBins.map(() => mapBins.map(() => ({ sum: 0, count: 0 })))
    );

    // Legacy single-cylinder accumulator for backward compatibility
    const [afrAccumulator, setAfrAccumulator] = useState<{ sum: number; count: number }[][]>(() =>
        rpmBins.map(() => mapBins.map(() => ({ sum: 0, count: 0 })))
    );

    // Calculated live VE corrections - DUAL CYLINDER
    const [frontVeCorrections, setFrontVeCorrections] = useState<number[][]>(() =>
        rpmBins.map(() => mapBins.map(() => 1.0))
    );
    const [rearVeCorrections, setRearVeCorrections] = useState<number[][]>(() =>
        rpmBins.map(() => mapBins.map(() => 1.0))
    );
    
    // Combined/display corrections (average of front and rear for UI)
    const [liveVeCorrections, setLiveVeCorrections] = useState<number[][]>(() =>
        rpmBins.map(() => mapBins.map(() => 1.0))
    );

    // Refs for throttled accumulation: mutate at 50Hz, flush to state every FLUSH_MS
    const FLUSH_MS = 80;  // ~12 updates/sec for responsive corrections without 50Hz overload
    const liveHitCountsRef = useRef<number[][]>([]);
    const frontHitCountsRef = useRef<number[][]>([]);
    const rearHitCountsRef = useRef<number[][]>([]);
    const frontAfrAccumulatorRef = useRef<{ sum: number; count: number }[][]>([]);
    const rearAfrAccumulatorRef = useRef<{ sum: number; count: number }[][]>([]);
    const afrAccumulatorRef = useRef<{ sum: number; count: number }[][]>([]);

    const initRefs = useCallback(() => {
        const emptyHits = rpmBins.map(() => mapBins.map(() => 0));
        const emptyAcc = rpmBins.map(() => mapBins.map(() => ({ sum: 0, count: 0 })));
        liveHitCountsRef.current = emptyHits.map(row => row.slice());
        frontHitCountsRef.current = emptyHits.map(row => row.slice());
        rearHitCountsRef.current = emptyHits.map(row => row.slice());
        frontAfrAccumulatorRef.current = emptyAcc.map(row => row.map(c => ({ ...c })));
        rearAfrAccumulatorRef.current = emptyAcc.map(row => row.map(c => ({ ...c })));
        afrAccumulatorRef.current = emptyAcc.map(row => row.map(c => ({ ...c })));
    }, [rpmBins, mapBins]);

    // Reset state and refs when engine preset changes
    useEffect(() => {
        const emptyHits = rpmBins.map(() => mapBins.map(() => 0));
        const emptyAcc = rpmBins.map(() => mapBins.map(() => ({ sum: 0, count: 0 })));
        const emptyCorr = rpmBins.map(() => mapBins.map(() => 1.0));
        
        setLiveHitCounts(emptyHits);
        setFrontHitCounts(emptyHits);
        setRearHitCounts(emptyHits);
        setAfrAccumulator(emptyAcc);
        setFrontAfrAccumulator(emptyAcc);
        setRearAfrAccumulator(emptyAcc);
        setLiveVeCorrections(emptyCorr);
        setFrontVeCorrections(emptyCorr);
        setRearVeCorrections(emptyCorr);
        initRefs();
    }, [activePreset, rpmBins, mapBins, initRefs]);

    // Track which cells are currently active (using kPa directly)
    const cellTrace = useMemo(() => {
        if (!isLive || currentRpm < 500) return null;
        return calculateCellTrace(currentRpm, currentMap, rpmBins, mapBins);
    }, [currentRpm, currentMap, isLive, rpmBins, mapBins]);

    // Ensure refs are initialized (e.g. before first accumulation)
    useEffect(() => {
        if (liveHitCountsRef.current.length !== rpmBins.length) initRefs();
    }, [rpmBins.length, mapBins.length, initRefs]);

    // Update hit counts and AFR accumulators in REFS only (50Hz) - no setState here
    // Flush to state is done by the interval below to avoid 50 state updates/sec
    useEffect(() => {
        if (!isLive || !cellTrace || currentRpm < 800) return;
        const hits = liveHitCountsRef.current;
        const fHits = frontHitCountsRef.current;
        const rHits = rearHitCountsRef.current;
        const fAcc = frontAfrAccumulatorRef.current;
        const rAcc = rearAfrAccumulatorRef.current;
        const acc = afrAccumulatorRef.current;
        if (hits.length !== rpmBins.length) return;

        for (const cell of cellTrace.activeCells) {
            if (cell.weight <= 0.2) continue;
            const i = cell.rpmIdx;
            const j = cell.mapIdx;
            hits[i][j]++;
            fHits[i][j]++;
            rHits[i][j]++;
        }

        if (resolvedAfrFront > 8 && resolvedAfrFront < 20) {
            for (const cell of cellTrace.activeCells) {
                if (cell.weight <= 0.2) continue;
                const i = cell.rpmIdx;
                const j = cell.mapIdx;
                fAcc[i][j].sum += resolvedAfrFront * cell.weight;
                fAcc[i][j].count += cell.weight;
            }
        }
        if (resolvedAfrRear > 8 && resolvedAfrRear < 20) {
            for (const cell of cellTrace.activeCells) {
                if (cell.weight <= 0.2) continue;
                const i = cell.rpmIdx;
                const j = cell.mapIdx;
                rAcc[i][j].sum += resolvedAfrRear * cell.weight;
                rAcc[i][j].count += cell.weight;
            }
        }
        const avgAfr = (resolvedAfrFront + resolvedAfrRear) / 2;
        if (avgAfr > 8 && avgAfr < 20) {
            for (const cell of cellTrace.activeCells) {
                if (cell.weight <= 0.2) continue;
                const i = cell.rpmIdx;
                const j = cell.mapIdx;
                acc[i][j].sum += avgAfr * cell.weight;
                acc[i][j].count += cell.weight;
            }
        }
    }, [cellTrace, resolvedAfrFront, resolvedAfrRear, isLive, currentRpm, rpmBins.length]);

    // Flush refs to state every FLUSH_MS and recompute corrections (reduces 50 state updates/sec to ~6–7)
    useEffect(() => {
        if (!isLive) return;
        const interval = setInterval(() => {
            const hits = liveHitCountsRef.current;
            const fHits = frontHitCountsRef.current;
            const rHits = rearHitCountsRef.current;
            const fAcc = frontAfrAccumulatorRef.current;
            const rAcc = rearAfrAccumulatorRef.current;
            const acc = afrAccumulatorRef.current;
            if (hits.length !== rpmBins.length) return;

            setLiveHitCounts(hits.map(row => [...row]));
            setFrontHitCounts(fHits.map(row => [...row]));
            setRearHitCounts(rHits.map(row => [...row]));
            setAfrAccumulator(acc.map(row => row.map(c => ({ ...c }))));
            setFrontAfrAccumulator(fAcc.map(row => row.map(c => ({ ...c }))));
            setRearAfrAccumulator(rAcc.map(row => row.map(c => ({ ...c }))));

            const calcCorrections = (accumulator: { sum: number; count: number }[][]) => {
                const result: number[][] = rpmBins.map(() => mapBins.map(() => 1.0));
                for (let i = 0; i < rpmBins.length; i++) {
                    for (let j = 0; j < mapBins.length; j++) {
                        const ac = accumulator[i]?.[j];
                        if (ac && ac.count >= 3) {
                            const meanAfr = ac.sum / ac.count;
                            const cellTargetAfr = getTargetAfrForMap(mapBins[j], resolvedAfrTargets);
                            result[i][j] = Math.max(0.85, Math.min(1.15, meanAfr / cellTargetAfr));
                        }
                    }
                }
                return result;
            };
            setFrontVeCorrections(calcCorrections(fAcc));
            setRearVeCorrections(calcCorrections(rAcc));
            setLiveVeCorrections(calcCorrections(acc));
        }, FLUSH_MS);
        return () => clearInterval(interval);
    }, [isLive, rpmBins, mapBins, resolvedAfrTargets]);

    // Use external corrections if provided, otherwise use live
    const displayCorrections = veCorrections ?? liveVeCorrections;
    const displayHitCounts = externalHitCounts ?? liveHitCounts;

    // Reset live tracking (state + refs so flush doesn't overwrite with stale ref data)
    const handleReset = useCallback(() => {
        const emptyHits = rpmBins.map(() => mapBins.map(() => 0));
        const emptyAcc = rpmBins.map(() => mapBins.map(() => ({ sum: 0, count: 0 })));
        const emptyCorr = rpmBins.map(() => mapBins.map(() => 1.0));
        
        setLiveHitCounts(emptyHits);
        setFrontHitCounts(emptyHits);
        setRearHitCounts(emptyHits);
        setAfrAccumulator(emptyAcc);
        setFrontAfrAccumulator(emptyAcc);
        setRearAfrAccumulator(emptyAcc);
        setLiveVeCorrections(emptyCorr);
        setFrontVeCorrections(emptyCorr);
        setRearVeCorrections(emptyCorr);
        initRefs();
        
        // Clear localStorage session data
        const STORAGE_KEY = `jetdrive-ve-hits-${activePreset}`;
        localStorage.removeItem(STORAGE_KEY);
        
        console.log('[VE Table] Reset and cleared session data');
    }, [rpmBins, mapBins, initRefs, activePreset]);

    // Check if a cell is currently active
    const isCellActive = useCallback((rpmIdx: number, mapIdx: number): number => {
        if (!cellTrace) return 0;
        const active = cellTrace.activeCells.find(c => c.rpmIdx === rpmIdx && c.mapIdx === mapIdx);
        return active?.weight ?? 0;
    }, [cellTrace]);

    // Total hits
    const totalHits = useMemo(() =>
        displayHitCounts.flat().reduce((a, b) => a + b, 0),
        [displayHitCounts]
    );
    
    // Ref for throttling live data updates
    const lastLiveUpdateRef = useRef<number>(0);
    
    // Live data update effect - push data to parent for real-time coverage tracking
    // Throttled to avoid excessive updates (every ~200ms when data changes for better persistence)
    useEffect(() => {
        if (!onLiveDataUpdate || !isLive) return;
        
        const now = Date.now();
        // Throttle updates to every 200ms (reduced from 500ms for better hit count persistence)
        if (now - lastLiveUpdateRef.current < 200) return;
        lastLiveUpdateRef.current = now;
        
        const liveData: LiveVEExportData = {
            frontCorrections: frontVeCorrections,
            rearCorrections: rearVeCorrections,
            hitCounts: displayHitCounts,
            frontHitCounts: frontHitCounts,
            rearHitCounts: rearHitCounts,
            rpmBins,
            mapBins,
            afrTargets: resolvedAfrTargets,
            enginePreset: activePreset,
            totalHits,
            exportedAt: new Date().toISOString(),
        };
        
        onLiveDataUpdate(liveData);
    }, [onLiveDataUpdate, isLive, totalHits, frontVeCorrections, rearVeCorrections, displayHitCounts, frontHitCounts, rearHitCounts, rpmBins, mapBins, resolvedAfrTargets, activePreset]);
    
    // Persist hit counts to localStorage for session recovery
    const STORAGE_KEY = `jetdrive-ve-hits-${activePreset}`;
    
    // Save hit counts to localStorage when they change
    useEffect(() => {
        if (totalHits > 0) {
            const sessionData = {
                liveHitCounts,
                frontHitCounts,
                rearHitCounts,
                frontVeCorrections,
                rearVeCorrections,
                liveVeCorrections,
                frontAfrAccumulator,
                rearAfrAccumulator,
                afrAccumulator,
                timestamp: Date.now(),
                enginePreset: activePreset
            };
            localStorage.setItem(STORAGE_KEY, JSON.stringify(sessionData));
        }
    }, [totalHits, liveHitCounts, frontHitCounts, rearHitCounts, frontVeCorrections, rearVeCorrections, liveVeCorrections, frontAfrAccumulator, rearAfrAccumulator, afrAccumulator, activePreset, STORAGE_KEY]);
    
    // Restore hit counts from localStorage on component mount
    useEffect(() => {
        const savedData = localStorage.getItem(STORAGE_KEY);
        if (savedData) {
            try {
                const sessionData = JSON.parse(savedData);
                // Only restore if data is recent (within 1 hour) and matches current preset
                const isRecent = Date.now() - sessionData.timestamp < 3600000; // 1 hour
                const isMatchingPreset = sessionData.enginePreset === activePreset;
                
                if (isRecent && isMatchingPreset) {
                    setLiveHitCounts(sessionData.liveHitCounts || []);
                    setFrontHitCounts(sessionData.frontHitCounts || []);
                    setRearHitCounts(sessionData.rearHitCounts || []);
                    setFrontVeCorrections(sessionData.frontVeCorrections || []);
                    setRearVeCorrections(sessionData.rearVeCorrections || []);
                    setLiveVeCorrections(sessionData.liveVeCorrections || []);
                    setFrontAfrAccumulator(sessionData.frontAfrAccumulator || []);
                    setRearAfrAccumulator(sessionData.rearAfrAccumulator || []);
                    setAfrAccumulator(sessionData.afrAccumulator || []);
                    
                    // Also restore to refs
                    if (sessionData.liveHitCounts) {
                        liveHitCountsRef.current = sessionData.liveHitCounts.map((row: number[]) => [...row]);
                        frontHitCountsRef.current = sessionData.frontHitCounts?.map((row: number[]) => [...row]) || [];
                        rearHitCountsRef.current = sessionData.rearHitCounts?.map((row: number[]) => [...row]) || [];
                        frontAfrAccumulatorRef.current = sessionData.frontAfrAccumulator?.map((row: any[]) => row.map((c: any) => ({ ...c }))) || [];
                        rearAfrAccumulatorRef.current = sessionData.rearAfrAccumulator?.map((row: any[]) => row.map((c: any) => ({ ...c }))) || [];
                        afrAccumulatorRef.current = sessionData.afrAccumulator?.map((row: any[]) => row.map((c: any) => ({ ...c }))) || [];
                    }
                    
                    console.log(`[VE Table] Restored ${sessionData.liveHitCounts?.flat().reduce((a: number, b: number) => a + b, 0) || 0} hits from session`);
                }
            } catch (error) {
                console.warn('[VE Table] Failed to restore session data:', error);
                localStorage.removeItem(STORAGE_KEY);
            }
        }
    }, [activePreset, STORAGE_KEY]); // Only run when preset changes
    
    // Export handler - provides data for external export utilities
    const handleExport = useCallback(() => {
        if (!onExport) return;
        
        const exportData: LiveVEExportData = {
            frontCorrections: frontVeCorrections,
            rearCorrections: rearVeCorrections,
            hitCounts: displayHitCounts,
            frontHitCounts: frontHitCounts,
            rearHitCounts: rearHitCounts,
            rpmBins,
            mapBins,
            afrTargets: resolvedAfrTargets,
            enginePreset: activePreset,
            totalHits,
            exportedAt: new Date().toISOString(),
        };
        
        onExport(exportData);
    }, [onExport, frontVeCorrections, rearVeCorrections, displayHitCounts, frontHitCounts, rearHitCounts, rpmBins, mapBins, resolvedAfrTargets, activePreset, totalHits]);

    return (
        <div className="space-y-3">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-lg bg-purple-500/20 flex items-center justify-center">
                        <Target className="w-4 h-4 text-purple-400" />
                    </div>
                    <div>
                        <h3 className="text-sm font-semibold text-white">Live VE Table</h3>
                        <p className="text-[10px] text-zinc-500">Cell tracing • Real-time corrections</p>
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    {isLive && (
                        <Badge variant="outline" className="text-[10px] border-green-500/30 text-green-400 bg-green-500/10">
                            <Activity className="w-3 h-3 mr-1 animate-pulse" />
                            LIVE
                        </Badge>
                    )}
                    <Badge variant="outline" className="text-[10px] border-zinc-700 text-zinc-400">
                        {totalHits} hits
                    </Badge>
                    {onExport && totalHits > 0 && (
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={handleExport}
                            className="h-7 px-2 text-xs text-green-400 hover:text-green-300 hover:bg-green-500/10"
                        >
                            <Download className="w-3 h-3 mr-1" />
                            Export
                        </Button>
                    )}
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={handleReset}
                        className="h-7 px-2 text-xs"
                    >
                        <RotateCcw className="w-3 h-3 mr-1" />
                        Reset
                    </Button>
                </div>
            </div>

            {/* Current Operating Point */}
            {isLive && currentRpm > 500 && (
                <div className="flex items-center gap-3 px-3 py-1.5 rounded-lg bg-zinc-900/50 border border-zinc-800 text-xs">
                    <div className="flex items-center gap-1.5">
                        <Crosshair className="w-3 h-3 text-orange-400" />
                        <span className="text-zinc-500">Operating:</span>
                    </div>
                    <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-green-400 font-mono font-bold">{currentRpm.toFixed(0)}</span>
                        <span className="text-zinc-600">RPM</span>
                        <span className="text-zinc-700">•</span>
                        <span className="text-blue-400 font-mono font-bold">{currentMap.toFixed(0)}</span>
                        <span className="text-zinc-600">kPa</span>
                        <span className="text-zinc-700">→</span>
                        {/* Dual-cylinder AFR display */}
                        <span className="text-orange-400 font-mono font-bold">{resolvedAfrFront.toFixed(1)}</span>
                        <span className="text-zinc-600 text-[10px]">F</span>
                        {resolvedAfrRear !== resolvedAfrFront && (
                            <>
                                <span className="text-zinc-700">/</span>
                                <span className="text-amber-400 font-mono font-bold">{resolvedAfrRear.toFixed(1)}</span>
                                <span className="text-zinc-600 text-[10px]">R</span>
                            </>
                        )}
                        <span className="text-zinc-500">(target: {getTargetAfrForMap(currentMap, resolvedAfrTargets).toFixed(1)})</span>
                    </div>
                </div>
            )}

            {/* VE Table Grid */}
            <div className="overflow-x-auto rounded-lg border border-zinc-800 bg-zinc-900/50">
                <table className="border-collapse w-full text-xs">
                    <thead>
                        <tr className="bg-zinc-900/80">
                            <th className="sticky left-0 z-10 min-w-[75px] w-[75px] h-10 px-3 py-2 text-left font-medium text-zinc-400 bg-zinc-900/80 border-r border-zinc-800/80">
                                <div className="flex flex-col items-start">
                                    <span>RPM →</span>
                                    <span className="text-[9px] text-zinc-500">MAP ↓</span>
                                </div>
                            </th>
                            {rpmBins.map((rpm, rpmIdx) => (
                                <th
                                    key={`rpm-${rpmIdx}`}
                                    className="min-w-[48px] w-[48px] h-10 px-1.5 py-2 text-center font-bold text-zinc-300 border-l border-zinc-800/50 whitespace-nowrap"
                                >
                                    {rpm >= 10000 ? `${(rpm / 1000).toFixed(0)}k` : rpm}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {mapBins.map((mapKpa, mapIdx) => (
                            <tr
                                key={`map-${mapIdx}`}
                                className={`${mapIdx % 2 === 0 ? 'bg-zinc-900/30' : 'bg-zinc-900/10'} border-t border-zinc-800/50`}
                            >
                                <td
                                    className={`
                                        sticky left-0 z-10 min-w-[75px] w-[75px] px-3 py-2 font-mono font-bold text-zinc-300 border-r border-zinc-800/80
                                        ${mapIdx % 2 === 0 ? 'bg-zinc-900/30' : 'bg-zinc-900/10'}
                                    `}
                                >
                                    <div className="flex flex-col items-start">
                                        <span>{mapKpa}</span>
                                        <span className="text-[9px] text-zinc-500 font-normal">kPa</span>
                                    </div>
                                </td>

                                {rpmBins.map((rpm, rpmIdx) => {
                                    const veCorr = displayCorrections[rpmIdx]?.[mapIdx] ?? 1.0;
                                    const hits = displayHitCounts[rpmIdx]?.[mapIdx] ?? 0;
                                    const activeWeight = isCellActive(rpmIdx, mapIdx);
                                    const isActive = activeWeight > 0;

                                    return (
                                        <td
                                            key={`cell-${mapIdx}-${rpmIdx}`}
                                            className={`
                                                min-w-[48px] w-[48px] h-12 px-1 py-1.5 text-center font-mono transition-all duration-75 cursor-pointer border-l border-zinc-800/30 align-middle
                                                ${getCellColor(veCorr, hits)}
                                                ${isActive ? 'ring-2 ring-orange-500 ring-inset bg-orange-500/40 scale-105 z-20 relative' : ''}
                                            `}
                                            onClick={() => onCellClick?.(rpmIdx, mapIdx)}
                                            title={`${rpm} RPM @ ${mapKpa} kPa\n${hits} hits${hits > 0 ? `\nVE: ${((veCorr - 1) * 100).toFixed(1)}%` : ''}`}
                                        >
                                            {hits > 0 || isActive ? (
                                                <div className={`flex flex-col items-center justify-center leading-tight ${isActive ? 'font-bold' : ''}`}>
                                                    <div className="text-xs whitespace-nowrap">{formatVE(veCorr, hits)}</div>
                                                    <div className="text-[9px] text-zinc-500/80 mt-0.5">{hits > 0 ? hits : '•'}</div>
                                                </div>
                                            ) : (
                                                <div className="flex items-center justify-center h-full text-zinc-700/30 text-base">·</div>
                                            )}
                                        </td>
                                    );
                                })}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Legend with Engine Selector */}
            <div className="flex items-center justify-between text-xs text-zinc-500 px-1 mt-2">
                <div className="flex items-center gap-3">
                    <span className="flex items-center gap-1">
                        <div className="w-3 h-3 rounded bg-red-500/50" />
                        <span>Lean</span>
                    </span>
                    <span className="flex items-center gap-1">
                        <div className="w-3 h-3 rounded bg-green-500/40" />
                        <span>OK</span>
                    </span>
                    <span className="flex items-center gap-1">
                        <div className="w-3 h-3 rounded bg-blue-500/50" />
                        <span>Rich</span>
                    </span>
                    <span className="text-zinc-700">|</span>
                    <span className="flex items-center gap-1 text-orange-400">
                        <Flame className="w-3 h-3" />
                        <span>Active</span>
                    </span>
                </div>

                {/* Engine Type Selector */}
                <div className="relative">
                    <button
                        onClick={() => setShowPresetMenu(!showPresetMenu)}
                        className="flex items-center gap-1 px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 transition-colors text-zinc-400"
                    >
                        <span>{config.name}</span>
                        <span className="text-zinc-600">({rpmBins.length}×{mapBins.length})</span>
                        <ChevronDown className="w-3 h-3" />
                    </button>

                    {showPresetMenu && (
                        <div className="absolute right-0 bottom-full mb-1 bg-zinc-800 border border-zinc-700 rounded-lg shadow-xl py-1 min-w-[160px] z-50">
                            {Object.entries(ENGINE_GRID_CONFIGS).map(([key, preset]) => (
                                <button
                                    key={key}
                                    onClick={() => handlePresetChange(key as EnginePreset)}
                                    className={`w-full text-left px-3 py-1.5 hover:bg-zinc-700 transition-colors flex items-center justify-between ${activePreset === key ? 'text-orange-400' : 'text-zinc-300'
                                        }`}
                                >
                                    <span>{preset.name}</span>
                                    <span className="text-zinc-600 text-[10px]">{preset.maxRpm.toLocaleString()}</span>
                                </button>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

export default LiveVETable;

