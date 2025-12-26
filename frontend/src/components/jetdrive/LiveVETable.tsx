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

import { useState, useEffect, useMemo, useCallback } from 'react';
import { Target, Activity, Flame, Crosshair, RotateCcw, ChevronDown } from 'lucide-react';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';

// Engine type presets with appropriate RPM ranges
export type EnginePreset = 'harley_m8' | 'harley_tc' | 'sportbike_600' | 'sportbike_1000' | 'custom';

export interface EngineConfig {
    name: string;
    rpmBins: number[];
    mapBins: number[];
    maxRpm: number;
}

export const ENGINE_PRESETS: Record<EnginePreset, EngineConfig> = {
    harley_m8: {
        name: 'Harley M8',
        rpmBins: [1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500],
        mapBins: [20, 30, 40, 50, 60, 70, 80, 90, 100, 110],
        maxRpm: 6500,
    },
    harley_tc: {
        name: 'Harley Twin Cam',
        rpmBins: [1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000],
        mapBins: [20, 30, 40, 50, 60, 70, 80, 90, 100, 110],
        maxRpm: 6000,
    },
    sportbike_600: {
        name: 'Sportbike 600cc',
        rpmBins: [2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000, 11000, 12000, 13000, 14000, 15000],
        mapBins: [20, 30, 40, 50, 60, 70, 80, 90, 100, 110],
        maxRpm: 15000,
    },
    sportbike_1000: {
        name: 'Sportbike 1000cc',
        rpmBins: [2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000, 11000, 12000, 13000],
        mapBins: [20, 30, 40, 50, 60, 70, 80, 90, 100, 110],
        maxRpm: 13000,
    },
    custom: {
        name: 'Custom',
        rpmBins: [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000],
        mapBins: [20, 30, 40, 50, 60, 70, 80, 90, 100, 110],
        maxRpm: 10000,
    },
};

interface LiveVETableProps {
    // Current live values
    currentRpm: number;
    currentMap: number;
    currentAfr: number;

    // AFR targets - can be a single value (legacy) or a table keyed by MAP
    afrTargets?: Record<number, number>;
    targetAfr?: number;  // @deprecated - use afrTargets instead

    // Mode
    isLive: boolean;

    // Engine preset (default: harley_m8)
    enginePreset?: EnginePreset;
    onEnginePresetChange?: (preset: EnginePreset) => void;

    // Optional: Pre-loaded VE corrections from analysis
    veCorrections?: number[][];  // [rpm_idx][map_idx] - multipliers
    hitCounts?: number[][];

    // Callback when cell is clicked
    onCellClick?: (rpmIdx: number, mapIdx: number) => void;
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
    currentAfr,
    afrTargets,
    targetAfr,  // Legacy prop
    isLive,
    enginePreset = 'harley_m8',
    onEnginePresetChange,
    veCorrections,
    hitCounts: externalHitCounts,
    onCellClick,
}: LiveVETableProps) {
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
    const config = ENGINE_PRESETS[activePreset];
    const { rpmBins, mapBins } = config;

    const handlePresetChange = useCallback((preset: EnginePreset) => {
        if (onEnginePresetChange) {
            onEnginePresetChange(preset);
        } else {
            setLocalPreset(preset);
        }
        setShowPresetMenu(false);
    }, [onEnginePresetChange]);

    // Internal hit count tracking (accumulates during live session)
    const [liveHitCounts, setLiveHitCounts] = useState<number[][]>(() =>
        rpmBins.map(() => mapBins.map(() => 0))
    );

    // AFR accumulator for live corrections
    const [afrAccumulator, setAfrAccumulator] = useState<{ sum: number; count: number }[][]>(() =>
        rpmBins.map(() => mapBins.map(() => ({ sum: 0, count: 0 })))
    );

    // Calculated live VE corrections
    const [liveVeCorrections, setLiveVeCorrections] = useState<number[][]>(() =>
        rpmBins.map(() => mapBins.map(() => 1.0))
    );

    // Reset state when engine preset changes
    useEffect(() => {
        setLiveHitCounts(rpmBins.map(() => mapBins.map(() => 0)));
        setAfrAccumulator(rpmBins.map(() => mapBins.map(() => ({ sum: 0, count: 0 }))));
        setLiveVeCorrections(rpmBins.map(() => mapBins.map(() => 1.0)));
    }, [activePreset, rpmBins, mapBins]);

    // Track which cells are currently active (using kPa directly)
    const cellTrace = useMemo(() => {
        if (!isLive || currentRpm < 500) return null;
        return calculateCellTrace(currentRpm, currentMap, rpmBins, mapBins);
    }, [currentRpm, currentMap, isLive, rpmBins, mapBins]);

    // Update hit counts and AFR accumulator when operating point changes
    useEffect(() => {
        if (!isLive || !cellTrace || currentRpm < 800) return;

        // Accumulate hits and AFR values for active cells
        setLiveHitCounts(prev => {
            const next = prev.map(row => [...row]);
            for (const cell of cellTrace.activeCells) {
                if (cell.weight > 0.2) {  // Only count significant contributions
                    next[cell.rpmIdx][cell.mapIdx]++;
                }
            }
            return next;
        });

        // Accumulate AFR for corrections
        if (currentAfr > 8 && currentAfr < 20) {  // Valid AFR range
            setAfrAccumulator(prev => {
                const next = prev.map(row => row.map(cell => ({ ...cell })));
                for (const cell of cellTrace.activeCells) {
                    if (cell.weight > 0.2) {
                        next[cell.rpmIdx][cell.mapIdx].sum += currentAfr * cell.weight;
                        next[cell.rpmIdx][cell.mapIdx].count += cell.weight;
                    }
                }
                return next;
            });
        }
    }, [cellTrace, currentAfr, isLive, currentRpm]);

    // Calculate live VE corrections from accumulated AFR data
    // Uses Math v2.0.0 ratio model: VE_correction = AFR_measured / AFR_target
    // This is physically accurate - the ratio directly represents the fuel error
    useEffect(() => {
        setLiveVeCorrections(prev => {
            const next = prev.map(row => [...row]);
            for (let i = 0; i < rpmBins.length; i++) {
                for (let j = 0; j < mapBins.length; j++) {
                    const acc = afrAccumulator[i]?.[j];
                    if (acc && acc.count >= 3) {  // Need at least 3 samples
                        const meanAfr = acc.sum / acc.count;
                        // Use the per-MAP target AFR for this column
                        const cellTargetAfr = getTargetAfrForMap(mapBins[j], resolvedAfrTargets);

                        // Math v2.0.0: Ratio model (physically accurate)
                        // VE_correction = AFR_measured / AFR_target
                        // Lean (measured > target) -> correction > 1 -> add fuel
                        // Rich (measured < target) -> correction < 1 -> remove fuel
                        const correction = meanAfr / cellTargetAfr;

                        // Clamp to ±15% for safety
                        next[i][j] = Math.max(0.85, Math.min(1.15, correction));
                    }
                }
            }
            return next;
        });
    }, [afrAccumulator, resolvedAfrTargets, rpmBins, mapBins]);

    // Use external corrections if provided, otherwise use live
    const displayCorrections = veCorrections ?? liveVeCorrections;
    const displayHitCounts = externalHitCounts ?? liveHitCounts;

    // Reset live tracking
    const handleReset = useCallback(() => {
        setLiveHitCounts(rpmBins.map(() => mapBins.map(() => 0)));
        setAfrAccumulator(rpmBins.map(() => mapBins.map(() => ({ sum: 0, count: 0 }))));
        setLiveVeCorrections(rpmBins.map(() => mapBins.map(() => 1.0)));
    }, [rpmBins, mapBins]);

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
                    <div className="flex items-center gap-2">
                        <span className="text-green-400 font-mono font-bold">{currentRpm.toFixed(0)}</span>
                        <span className="text-zinc-600">RPM</span>
                        <span className="text-zinc-700">•</span>
                        <span className="text-blue-400 font-mono font-bold">{currentMap.toFixed(0)}</span>
                        <span className="text-zinc-600">kPa</span>
                        <span className="text-zinc-700">→</span>
                        <span className="text-orange-400 font-mono font-bold">{currentAfr.toFixed(1)}</span>
                        <span className="text-zinc-500">AFR (target: {getTargetAfrForMap(currentMap, resolvedAfrTargets).toFixed(1)})</span>
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
                            {rpmBins.map((rpm) => (
                                <th
                                    key={rpm}
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
                                key={mapKpa}
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
                                            key={`${rpm}-${mapKpa}`}
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
                            {Object.entries(ENGINE_PRESETS).map(([key, preset]) => (
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

