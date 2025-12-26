/**
 * AFRTargetTable - Editable 2D AFR target grid (RPM x MAP)
 * 
 * Shows the full AFR target table used by the tuning math,
 * allowing users to adjust targets for each RPM/load cell.
 * 
 * Grid structure:
 * - RPM: 1000-6500 (12 columns)
 * - MAP: 20-100 kPa (9 rows)
 * 
 * Includes presets for common applications:
 * - NA Street: 14.7 idle → 12.8 WOT
 * - NA Performance: 14.5 idle → 12.5 WOT  
 * - Turbo/SC: 14.0 idle → 11.5 WOT
 * - E85: 14.0 idle → 10.5 WOT
 */

import { useState, useCallback, useMemo } from 'react';
import { RotateCcw, ChevronDown, Flame, Droplets, Zap, Fuel } from 'lucide-react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
    DropdownMenuSeparator,
    DropdownMenuLabel,
} from '../ui/dropdown-menu';
import { cn } from '../../lib/utils';

// RPM bins (1000-6500 in 500 RPM increments)
export const RPM_BINS = [1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500];

// MAP bins (load zones)
export const MAP_BINS = [20, 30, 40, 50, 60, 70, 80, 90, 100];

// 2D AFR target grid type: [rpm][map] = afr
export type AFRGrid = number[][];

// Default AFR targets matching backend (api/services/autotune_workflow.py)
// Legacy format for backwards compatibility
export const DEFAULT_AFR_TARGETS: Record<number, number> = {
    20: 14.7,  // Deep vacuum / decel
    30: 14.7,  // Idle
    40: 14.5,  // Light cruise
    50: 14.0,  // Cruise
    60: 13.5,  // Part throttle
    70: 13.0,  // Mid load
    80: 12.8,  // Heavy load
    90: 12.5,  // High load
    100: 12.2, // WOT / boost
};

// Create default 2D grid from MAP-based targets
function createDefaultGrid(): AFRGrid {
    return RPM_BINS.map(() => 
        MAP_BINS.map(mapKpa => DEFAULT_AFR_TARGETS[mapKpa] || 14.0)
    );
}

export const DEFAULT_AFR_GRID = createDefaultGrid();

// Presets for common applications
const PRESET_MAP_TARGETS = {
    na_street: {
        20: 14.7, 30: 14.7, 40: 14.5, 50: 14.0, 60: 13.5, 70: 13.0, 80: 12.8, 90: 12.5, 100: 12.2,
    },
    na_performance: {
        20: 14.7, 30: 14.5, 40: 14.2, 50: 13.8, 60: 13.2, 70: 12.8, 80: 12.5, 90: 12.3, 100: 12.0,
    },
    turbo: {
        20: 14.5, 30: 14.2, 40: 13.8, 50: 13.2, 60: 12.8, 70: 12.3, 80: 11.8, 90: 11.5, 100: 11.2,
    },
    e85: {
        20: 14.0, 30: 13.5, 40: 12.8, 50: 12.0, 60: 11.5, 70: 11.0, 80: 10.8, 90: 10.5, 100: 10.2,
    },
};

export const AFR_PRESETS = {
    na_street: {
        name: 'NA Street',
        description: 'Conservative for pump gas daily driver',
        icon: Droplets,
        targets: PRESET_MAP_TARGETS.na_street,
        grid: RPM_BINS.map(() => MAP_BINS.map(m => PRESET_MAP_TARGETS.na_street[m])),
    },
    na_performance: {
        name: 'NA Performance',
        description: 'Aggressive for NA high-performance builds',
        icon: Zap,
        targets: PRESET_MAP_TARGETS.na_performance,
        grid: RPM_BINS.map(() => MAP_BINS.map(m => PRESET_MAP_TARGETS.na_performance[m])),
    },
    turbo: {
        name: 'Turbo/SC',
        description: 'Richer targets for forced induction',
        icon: Flame,
        targets: PRESET_MAP_TARGETS.turbo,
        grid: RPM_BINS.map(() => MAP_BINS.map(m => PRESET_MAP_TARGETS.turbo[m])),
    },
    e85: {
        name: 'E85',
        description: 'Optimized for E85 fuel (~9.8 stoich)',
        icon: Fuel,
        targets: PRESET_MAP_TARGETS.e85,
        grid: RPM_BINS.map(() => MAP_BINS.map(m => PRESET_MAP_TARGETS.e85[m])),
    },
} as const;

type PresetKey = keyof typeof AFR_PRESETS;

// Load zone labels for display (short versions for compact view)
const LOAD_ZONES: Record<number, string> = {
    20: 'Decel',
    30: 'Idle',
    40: 'Lt Cruise',
    50: 'Cruise',
    60: 'Part',
    70: 'Mid',
    80: 'Heavy',
    90: 'High',
    100: 'WOT',
};

// Full zone labels for expanded view
const LOAD_ZONES_FULL: Record<number, string> = {
    20: 'Decel',
    30: 'Idle',
    40: 'Cruise (Light)',
    50: 'Cruise',
    60: 'Part Throttle',
    70: 'Mid Load',
    80: 'Heavy Load',
    90: 'High Load',
    100: 'WOT',
};

// Color coding based on AFR value
function getAfrColor(afr: number): string {
    if (afr >= 14.5) return 'text-blue-400';       // Lean / stoich
    if (afr >= 13.5) return 'text-green-400';      // Cruise
    if (afr >= 12.5) return 'text-yellow-400';     // Rich cruise
    if (afr >= 11.5) return 'text-orange-400';     // WOT zone
    return 'text-red-400';                          // Very rich (E85/turbo)
}

function getAfrBgColor(afr: number): string {
    if (afr >= 14.5) return 'bg-blue-500/10';
    if (afr >= 13.5) return 'bg-green-500/10';
    if (afr >= 12.5) return 'bg-yellow-500/10';
    if (afr >= 11.5) return 'bg-orange-500/10';
    return 'bg-red-500/10';
}

interface AFRTargetTableProps {
    // Legacy support: single-axis MAP targets
    targets?: Record<number, number>;
    onChange?: (targets: Record<number, number>) => void;
    
    // New 2D grid support
    grid?: AFRGrid;
    onGridChange?: (grid: AFRGrid) => void;
    
    compact?: boolean;
    currentMap?: number;
    currentRpm?: number;
}

export function AFRTargetTable({
    targets,
    onChange,
    grid: externalGrid,
    onGridChange,
    compact = false,
    currentMap,
    currentRpm,
}: AFRTargetTableProps) {
    // Use grid if provided, otherwise create from targets or use default
    const [internalGrid, setInternalGrid] = useState<AFRGrid>(() => {
        if (externalGrid) return externalGrid;
        if (targets) {
            return RPM_BINS.map(() => MAP_BINS.map(m => targets[m] || 14.0));
        }
        return DEFAULT_AFR_GRID;
    });

    const grid = externalGrid || internalGrid;
    
    const [editingCell, setEditingCell] = useState<{ rpmIdx: number; mapIdx: number } | null>(null);
    const [editValue, setEditValue] = useState<string>('');

    const handleCellClick = useCallback((rpmIdx: number, mapIdx: number) => {
        setEditingCell({ rpmIdx, mapIdx });
        setEditValue(grid[rpmIdx][mapIdx].toFixed(1));
    }, [grid]);

    const handleCellBlur = useCallback(() => {
        if (editingCell !== null) {
            const newValue = parseFloat(editValue);
            if (!isNaN(newValue) && newValue >= 9.0 && newValue <= 16.0) {
                const newGrid = grid.map((row, ri) => 
                    row.map((val, mi) => 
                        ri === editingCell.rpmIdx && mi === editingCell.mapIdx 
                            ? Math.round(newValue * 10) / 10 
                            : val
                    )
                );
                
                if (onGridChange) {
                    onGridChange(newGrid);
                } else {
                    setInternalGrid(newGrid);
                    // Legacy support: update targets if onChange provided
                    if (onChange) {
                        const newTargets: Record<number, number> = {};
                        MAP_BINS.forEach((mapKpa, idx) => {
                            // Average across all RPM for this MAP
                            const avg = newGrid.reduce((sum, row) => sum + row[idx], 0) / newGrid.length;
                            newTargets[mapKpa] = Math.round(avg * 10) / 10;
                        });
                        onChange(newTargets);
                    }
                }
            }
            setEditingCell(null);
        }
    }, [editingCell, editValue, grid, onGridChange, onChange]);

    const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
        if (e.key === 'Enter') {
            handleCellBlur();
        } else if (e.key === 'Escape') {
            setEditingCell(null);
        }
    }, [handleCellBlur]);

    const applyPreset = useCallback((presetKey: PresetKey) => {
        const preset = AFR_PRESETS[presetKey];
        if (onGridChange) {
            onGridChange(preset.grid);
        } else {
            setInternalGrid(preset.grid);
            if (onChange) {
                onChange({ ...preset.targets });
            }
        }
    }, [onGridChange, onChange]);

    const resetToDefault = useCallback(() => {
        if (onGridChange) {
            onGridChange(DEFAULT_AFR_GRID);
        } else {
            setInternalGrid(DEFAULT_AFR_GRID);
            if (onChange) {
                onChange({ ...DEFAULT_AFR_TARGETS });
            }
        }
    }, [onGridChange, onChange]);

    // Find active cell based on current RPM and MAP
    const activeCell = useMemo(() => {
        if (currentRpm === undefined || currentMap === undefined) return null;
        
        // Find closest RPM bin
        let closestRpmIdx = 0;
        let minRpmDiff = Math.abs(RPM_BINS[0] - currentRpm);
        RPM_BINS.forEach((rpm, idx) => {
            const diff = Math.abs(rpm - currentRpm);
            if (diff < minRpmDiff) {
                minRpmDiff = diff;
                closestRpmIdx = idx;
            }
        });
        
        // Find closest MAP bin
        let closestMapIdx = 0;
        let minMapDiff = Math.abs(MAP_BINS[0] - currentMap);
        MAP_BINS.forEach((map, idx) => {
            const diff = Math.abs(map - currentMap);
            if (diff < minMapDiff) {
                minMapDiff = diff;
                closestMapIdx = idx;
            }
        });
        
        return { rpmIdx: closestRpmIdx, mapIdx: closestMapIdx };
    }, [currentRpm, currentMap]);

    if (compact) {
        // Compact view: show simplified MAP-only row (averaged across RPM)
        const avgTargets = MAP_BINS.map((_, mapIdx) => {
            const sum = grid.reduce((acc, row) => acc + row[mapIdx], 0);
            return sum / grid.length;
        });
        
        return (
            <div className="space-y-3">
                <div className="flex items-center justify-between">
                    <Label className="text-sm font-medium text-zinc-300">AFR Targets by Load</Label>
                    <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                            <Button variant="outline" size="sm" className="h-8 px-3 gap-2 border-orange-500/50 hover:border-orange-500 hover:bg-orange-500/10">
                                <Flame className="h-4 w-4 text-orange-400" />
                                <span>Presets</span>
                                <ChevronDown className="h-3 w-3 opacity-60" />
                            </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-64">
                            <DropdownMenuLabel>AFR Preset</DropdownMenuLabel>
                            <DropdownMenuSeparator />
                            {Object.entries(AFR_PRESETS).map(([key, preset]) => {
                                const Icon = preset.icon;
                                return (
                                    <DropdownMenuItem
                                        key={key}
                                        onClick={() => applyPreset(key as PresetKey)}
                                        className="py-2"
                                    >
                                        <Icon className="mr-2 h-4 w-4" />
                                        <div className="flex flex-col">
                                            <span className="font-medium">{preset.name}</span>
                                            <span className="text-[11px] text-zinc-500">{preset.description}</span>
                                        </div>
                                    </DropdownMenuItem>
                                );
                            })}
                            <DropdownMenuSeparator />
                            <DropdownMenuItem onClick={resetToDefault} className="py-2">
                                <RotateCcw className="mr-2 h-4 w-4" />
                                Reset to Default
                            </DropdownMenuItem>
                        </DropdownMenuContent>
                    </DropdownMenu>
                </div>

                {/* Simplified view: MAP kPa, Zone label, Average AFR */}
                <div className="overflow-x-auto rounded-lg border border-zinc-800 bg-zinc-900/50">
                    <table className="w-full text-xs border-collapse">
                        <thead>
                            <tr className="bg-zinc-800/80">
                                {MAP_BINS.map((mapKpa) => (
                                    <th
                                        key={mapKpa}
                                        className={cn(
                                            "min-w-[60px] px-2 py-2 text-center font-bold text-zinc-300 border-b border-zinc-800/80",
                                            activeCell && MAP_BINS[activeCell.mapIdx] === mapKpa && "bg-orange-500/30 text-orange-300"
                                        )}
                                    >
                                        {mapKpa}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            <tr className="bg-zinc-800/40 border-t border-zinc-800/50">
                                {MAP_BINS.map((mapKpa) => (
                                    <td
                                        key={mapKpa}
                                        className={cn(
                                            "min-w-[60px] px-1 py-1.5 text-center text-[10px] text-zinc-500 border-b border-zinc-800/50",
                                            activeCell && MAP_BINS[activeCell.mapIdx] === mapKpa && "bg-orange-500/20 text-orange-400"
                                        )}
                                    >
                                        {LOAD_ZONES[mapKpa] || '—'}
                                    </td>
                                ))}
                            </tr>
                            <tr className="border-t border-zinc-800/50">
                                {avgTargets.map((afr, mapIdx) => {
                                    const isActive = activeCell && activeCell.mapIdx === mapIdx;
                                    return (
                                        <td
                                            key={mapIdx}
                                            className={cn(
                                                "min-w-[60px] h-12 px-2 py-2.5 text-center transition-colors align-middle",
                                                getAfrBgColor(afr),
                                                isActive && "ring-2 ring-inset ring-orange-500 z-20 relative"
                                            )}
                                        >
                                            <div className="flex items-center justify-center h-full">
                                                <span className={cn("font-mono font-bold text-base", getAfrColor(afr))}>
                                                    {afr.toFixed(1)}
                                                </span>
                                            </div>
                                        </td>
                                    );
                                })}
                            </tr>
                        </tbody>
                    </table>
                </div>

                <p className="text-[11px] text-zinc-500">
                    Averaged AFR targets · Open full view to edit individual cells
                </p>
            </div>
        );
    }

    // Full layout - 2D grid (RPM x MAP)
    return (
        <div className="space-y-3">
            <div className="flex items-center justify-between">
                <Label className="text-sm text-zinc-300">AFR Target Grid (RPM × MAP)</Label>
                <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                        <Button variant="outline" size="sm" className="h-8 px-3 gap-2">
                            <Flame className="h-4 w-4" />
                            <span>Presets</span>
                            <ChevronDown className="ml-1 h-3 w-3" />
                        </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-56">
                        <DropdownMenuLabel>AFR Preset</DropdownMenuLabel>
                        <DropdownMenuSeparator />
                        {Object.entries(AFR_PRESETS).map(([key, preset]) => {
                            const Icon = preset.icon;
                            return (
                                <DropdownMenuItem
                                    key={key}
                                    onClick={() => applyPreset(key as PresetKey)}
                                >
                                    <Icon className="mr-2 h-4 w-4" />
                                    <div className="flex flex-col">
                                        <span>{preset.name}</span>
                                        <span className="text-[10px] text-zinc-500">{preset.description}</span>
                                    </div>
                                </DropdownMenuItem>
                            );
                        })}
                        <DropdownMenuSeparator />
                        <DropdownMenuItem onClick={resetToDefault}>
                            <RotateCcw className="mr-2 h-4 w-4" />
                            Reset to Default
                        </DropdownMenuItem>
                    </DropdownMenuContent>
                </DropdownMenu>
            </div>

            <div className="overflow-x-auto rounded-lg border border-zinc-800 bg-zinc-900/50">
                <table className="w-full text-xs border-collapse">
                    <thead>
                        <tr className="bg-zinc-800/80">
                            <th className="sticky left-0 z-10 min-w-[75px] w-[75px] px-3 py-2 text-left font-medium text-zinc-400 bg-zinc-800/80 border-r border-zinc-800/80">
                                <div className="flex flex-col items-start">
                                    <span>RPM →</span>
                                    <span className="text-[9px] text-zinc-500">MAP ↓</span>
                                </div>
                            </th>
                            {RPM_BINS.map((rpm) => (
                                <th
                                    key={rpm}
                                    className={cn(
                                        "min-w-[48px] w-[48px] px-1.5 py-2 text-center font-bold text-zinc-300 border-l border-zinc-800/50",
                                        activeCell && RPM_BINS[activeCell.rpmIdx] === rpm && "bg-orange-500/20 text-orange-300"
                                    )}
                                >
                                    {rpm}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {MAP_BINS.map((mapKpa, mapIdx) => (
                            <tr key={mapKpa} className={cn(
                                "border-t border-zinc-800/50",
                                mapIdx % 2 === 0 ? "bg-zinc-900/30" : "bg-zinc-900/10"
                            )}>
                                <td className={cn(
                                    "sticky left-0 z-10 min-w-[75px] w-[75px] px-3 py-2 font-mono font-bold text-zinc-300 border-r border-zinc-800/80",
                                    mapIdx % 2 === 0 ? "bg-zinc-900/30" : "bg-zinc-900/10",
                                    activeCell && activeCell.mapIdx === mapIdx && "text-orange-400 bg-orange-500/10"
                                )}>
                                    <div className="flex flex-col items-start">
                                        <span>{mapKpa}</span>
                                        <span className="text-[9px] text-zinc-500 font-normal">
                                            {LOAD_ZONES[mapKpa]}
                                        </span>
                                    </div>
                                </td>
                                {RPM_BINS.map((rpm, rpmIdx) => {
                                    const afr = grid[rpmIdx][mapIdx];
                                    const isEditing = editingCell?.rpmIdx === rpmIdx && editingCell?.mapIdx === mapIdx;
                                    const isActive = activeCell?.rpmIdx === rpmIdx && activeCell?.mapIdx === mapIdx;

                                    return (
                                        <td
                                            key={`${rpm}-${mapKpa}`}
                                            className={cn(
                                                "min-w-[48px] w-[48px] h-12 px-1 py-1.5 text-center cursor-pointer transition-colors border-l border-zinc-800/30 align-middle",
                                                getAfrBgColor(afr),
                                                isActive && "ring-2 ring-inset ring-orange-500 z-20 relative",
                                                !isEditing && "hover:bg-zinc-700/50"
                                            )}
                                            onClick={() => !isEditing && handleCellClick(rpmIdx, mapIdx)}
                                        >
                                            {isEditing ? (
                                                <input
                                                    type="number"
                                                    value={editValue}
                                                    onChange={(e) => setEditValue(e.target.value)}
                                                    onBlur={handleCellBlur}
                                                    onKeyDown={handleKeyDown}
                                                    className="h-7 w-14 text-center text-xs font-mono font-bold bg-zinc-900 border-2 border-orange-500 rounded focus:outline-none [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                                                    autoFocus
                                                    step={0.1}
                                                    min={9.0}
                                                    max={16.0}
                                                />
                                            ) : (
                                                <div className="flex items-center justify-center h-full">
                                                    <span className={cn("font-mono font-bold text-sm", getAfrColor(afr))}>
                                                        {afr.toFixed(1)}
                                                    </span>
                                                </div>
                                            )}
                                        </td>
                                    );
                                })}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            <p className="text-xs text-zinc-500">
                Click any cell to edit · RPM: 1000-6500 · MAP: 20-100 kPa · Lower AFR = richer mixture
            </p>
        </div>
    );
}

export default AFRTargetTable;

// Helper function to convert legacy targets to grid
export function targetsToGrid(targets: Record<number, number>): AFRGrid {
    return RPM_BINS.map(() => MAP_BINS.map(m => targets[m] || 14.0));
}

// Helper function to convert grid to legacy targets (averages across RPM)
export function gridToTargets(grid: AFRGrid): Record<number, number> {
    const targets: Record<number, number> = {};
    MAP_BINS.forEach((mapKpa, idx) => {
        const sum = grid.reduce((acc, row) => acc + row[idx], 0);
        targets[mapKpa] = Math.round((sum / grid.length) * 10) / 10;
    });
    return targets;
}

