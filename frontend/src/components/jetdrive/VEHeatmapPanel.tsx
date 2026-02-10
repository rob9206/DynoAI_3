import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { MouseEvent } from 'react';
import { cn } from '../../lib/utils';
import { useThrottle } from '../../hooks/useDebounce';
import {
  useJetDriveLive,
  type JetDriveChannel,
  type UseJetDriveLiveReturn,
} from '../../hooks/useJetDriveLive';
import { ENGINE_GRID_CONFIGS, type EnginePreset } from '../../utils/enginePresets';
import { DEFAULT_AFR_TARGETS } from './AFRTargetTable';
import { VECell } from './VECell';

const MISSING_VALUE = '—';

const MIN_CELL_WIDTH = 36;   // fits "+2.1" in text-xs mono
const MIN_CELL_HEIGHT = 24;  // fits one line of text
const MAX_ASPECT_RATIO = 1.6; // width:height — closer to square = more like a real heatmap
const AXIS_LABEL_WIDTH = 48;
const AXIS_LABEL_HEIGHT = 28;
const MAX_CORRECTION = 0.15; // +/-15% preview clamp
const MIN_HITS_FOR_CORRECTION = 3;
// UI-only formatting precision for display labels/tooltips (does not affect correction math)
const DISPLAY_DECIMALS = 1;

const RPM_CANDIDATES = ['RPM', 'Engine RPM', 'Digital RPM 1', 'Digital RPM 2'];
const MAP_CANDIDATES = ['MAP', 'MAP kPa'];
const AFR_FRONT_CANDIDATES = ['AFR Front', 'Air/Fuel Ratio 1', 'User Analog 1', 'AFR 1', 'AFR'];
const AFR_REAR_CANDIDATES = ['AFR Rear', 'Air/Fuel Ratio 2', 'User Analog 2', 'AFR 2'];

type Cylinder = 'front' | 'rear';

interface ChannelMatch {
  name: string;
  value: number;
}

interface VEHeatmapPanelProps {
  apiUrl?: string;
  live?: UseJetDriveLiveReturn;
  afrTargets?: Record<number, number>;
  enginePreset?: EnginePreset;
  customRpmBins?: number[];
  customMapBins?: number[];
  activeCylinder?: Cylinder;
  onCylinderChange?: (cylinder: Cylinder) => void;
  onHitCountsChange?: (frontHits: number[][], rearHits: number[][], rpmBins: number[], mapBins: number[]) => void;
  uncertaintyMap?: number[][];
  className?: string;
}

interface TooltipState {
  text: string;
  x: number;
  y: number;
}

function findChannel(
  channels: Record<string, JetDriveChannel>,
  candidates: string[],
  fallbackIncludes: string[],
): ChannelMatch | null {
  for (const candidate of candidates) {
    const channel = channels[candidate];
    if (channel && Number.isFinite(channel.value)) {
      return { name: candidate, value: channel.value };
    }
  }

  const matchers = [...candidates, ...fallbackIncludes].map((entry) => entry.toLowerCase());
  for (const [name, channel] of Object.entries(channels)) {
    const lowerName = name.toLowerCase();
    if (matchers.some((entry) => lowerName.includes(entry))) {
      return { name, value: channel.value };
    }
  }

  return null;
}

function dedupeBins(raw: number[]): number[] {
  const rounded = raw.map((value) => Math.round(value));
  return [...new Set(rounded)].sort((a, b) => a - b);
}

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

function buildColorScale(steps: number) {
  const stops = [
    { value: -7, color: [37, 99, 235] },   // blue-600
    { value: -5, color: [96, 165, 250] },  // blue-400
    { value: -3, color: [147, 197, 253] }, // blue-300
    { value: -1, color: [191, 219, 254] }, // blue-200
    { value: 0, color: [63, 63, 70] },     // zinc-700
    { value: 1, color: [254, 215, 170] },  // orange-200
    { value: 3, color: [253, 186, 116] },  // orange-300
    { value: 5, color: [251, 146, 60] },   // orange-400
    { value: 7, color: [234, 88, 12] },    // orange-600
  ];

  const interpolate = (a: number[], b: number[], t: number) => {
    const r = Math.round(a[0] + (b[0] - a[0]) * t);
    const g = Math.round(a[1] + (b[1] - a[1]) * t);
    const bVal = Math.round(a[2] + (b[2] - a[2]) * t);
    return `rgb(${r}, ${g}, ${bVal})`;
  };

  const colors: string[] = [];
  for (let i = 0; i < steps; i++) {
    const value = -7 + (14 * i) / (steps - 1);
    let lower = stops[0];
    let upper = stops[stops.length - 1];
    for (let j = 0; j < stops.length - 1; j++) {
      if (value >= stops[j].value && value <= stops[j + 1].value) {
        lower = stops[j];
        upper = stops[j + 1];
        break;
      }
    }
    const range = upper.value - lower.value || 1;
    const t = (value - lower.value) / range;
    colors.push(interpolate(lower.color, upper.color, t));
  }
  return colors;
}

function getLuminanceFromRgb(rgb: string): number {
  const match = /rgb\((\d+),\s*(\d+),\s*(\d+)\)/.exec(rgb);
  if (!match) return 0;
  const r = parseInt(match[1], 10) / 255;
  const g = parseInt(match[2], 10) / 255;
  const b = parseInt(match[3], 10) / 255;
  return 0.299 * r + 0.587 * g + 0.114 * b;
}

function getCorrectionDisplay(value: number, hits: number): string {
  if (hits === 0) return MISSING_VALUE;
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(DISPLAY_DECIMALS)}%`;
}

function getConfidenceLabel(hits: number): 'Low' | 'Medium' | 'High' | 'None' {
  if (hits <= 0) return 'None';
  if (hits < 8) return 'Low';
  if (hits < 20) return 'Medium';
  return 'High';
}

function calculateCellTrace(
  rpm: number,
  map: number,
  rpmBins: number[],
  mapBins: number[],
): {
  rpmIdx: number;
  mapIdx: number;
  activeCells: { rpmIdx: number; mapIdx: number; weight: number }[];
} {
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

  const rpmLow = rpmBins[Math.min(rpmIdx, rpmBins.length - 1)];
  const rpmHigh = rpmBins[Math.min(rpmIdx + 1, rpmBins.length - 1)];
  const mapLow = mapBins[Math.min(mapIdx, mapBins.length - 1)];
  const mapHigh = mapBins[Math.min(mapIdx + 1, mapBins.length - 1)];

  const rpmWeight = rpmHigh !== rpmLow ? Math.min(1, Math.max(0, (rpm - rpmLow) / (rpmHigh - rpmLow))) : 0;
  const mapWeight = mapHigh !== mapLow ? Math.min(1, Math.max(0, (map - mapLow) / (mapHigh - mapLow))) : 0;

  const activeCells: { rpmIdx: number; mapIdx: number; weight: number }[] = [];
  const w00 = (1 - rpmWeight) * (1 - mapWeight);
  const w01 = (1 - rpmWeight) * mapWeight;
  const w10 = rpmWeight * (1 - mapWeight);
  const w11 = rpmWeight * mapWeight;

  if (w00 > 0.01) activeCells.push({ rpmIdx, mapIdx, weight: w00 });
  if (w01 > 0.01 && mapIdx + 1 < mapBins.length) activeCells.push({ rpmIdx, mapIdx: mapIdx + 1, weight: w01 });
  if (w10 > 0.01 && rpmIdx + 1 < rpmBins.length) activeCells.push({ rpmIdx: rpmIdx + 1, mapIdx, weight: w10 });
  if (w11 > 0.01 && rpmIdx + 1 < rpmBins.length && mapIdx + 1 < mapBins.length) {
    activeCells.push({ rpmIdx: rpmIdx + 1, mapIdx: mapIdx + 1, weight: w11 });
  }

  return { rpmIdx, mapIdx, activeCells };
}

/** Compute text size based on cell dimensions */
function getCellTextSize(cellWidth: number): string {
  if (cellWidth >= 80) return 'text-xs';
  if (cellWidth >= 50) return 'text-[10px]';
  return 'text-[9px]';
}

function VEHeatmapPanelContent({
  live,
  afrTargets,
  enginePreset = 'harley_m8',
  customRpmBins,
  customMapBins,
  activeCylinder,
  onCylinderChange,
  onHitCountsChange,
  uncertaintyMap,
  className,
}: {
  live: UseJetDriveLiveReturn;
  afrTargets: Record<number, number>;
  enginePreset?: EnginePreset;
  customRpmBins?: number[];
  customMapBins?: number[];
  activeCylinder?: Cylinder;
  onCylinderChange?: (cylinder: Cylinder) => void;
  onHitCountsChange?: (frontHits: number[][], rearHits: number[][], rpmBins: number[], mapBins: number[]) => void;
  uncertaintyMap?: number[][];
  className?: string;
}) {
  const debugHeatmap = useMemo(() => {
    if (!import.meta.env.DEV) return false;
    try {
      return globalThis.localStorage?.getItem('dynoai.debug.veHeatmap') === '1';
    } catch {
      return false;
    }
  }, []);

  const [localCylinder, setLocalCylinder] = useState<Cylinder>('front');
  const [showCoverage, setShowCoverage] = useState(false);
  const [showUncertainty, setShowUncertainty] = useState(false);
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);

  const cylinder = activeCylinder ?? localCylinder;
  const config = ENGINE_GRID_CONFIGS[enginePreset] ?? ENGINE_GRID_CONFIGS.harley_m8;
  const rpmBins = useMemo(
    () => (customRpmBins && customRpmBins.length ? dedupeBins(customRpmBins) : config.rpmBins),
    [customRpmBins, config.rpmBins],
  );
  const mapBins = useMemo(
    () => (customMapBins && customMapBins.length ? dedupeBins(customMapBins) : config.mapBins),
    [customMapBins, config.mapBins],
  );

  const rpmChannel = useMemo(
    () => findChannel(live.channels, RPM_CANDIDATES, ['rpm']),
    [live.channels],
  );
  const mapChannel = useMemo(
    () => findChannel(live.channels, MAP_CANDIDATES, ['map']),
    [live.channels],
  );
  const afrFrontChannel = useMemo(
    () => findChannel(live.channels, AFR_FRONT_CANDIDATES, ['afr front', 'afr 1']),
    [live.channels],
  );
  const afrRearChannel = useMemo(
    () => findChannel(live.channels, AFR_REAR_CANDIDATES, ['afr rear', 'afr 2']),
    [live.channels],
  );

  const rawLiveValues = useMemo(
    () => ({
      rpm: rpmChannel?.value ?? 0,
      map: mapChannel?.value ?? 0,
      afrFront: afrFrontChannel?.value ?? 0,
      afrRear: afrRearChannel?.value ?? 0,
    }),
    [rpmChannel?.value, mapChannel?.value, afrFrontChannel?.value, afrRearChannel?.value],
  );
  const liveValues = useThrottle(rawLiveValues, 100);

  const [frontHits, setFrontHits] = useState<number[][]>(() =>
    rpmBins.map(() => mapBins.map(() => 0)),
  );
  const [rearHits, setRearHits] = useState<number[][]>(() =>
    rpmBins.map(() => mapBins.map(() => 0)),
  );
  const [frontCorrections, setFrontCorrections] = useState<number[][]>(() =>
    rpmBins.map(() => mapBins.map(() => 0)),
  );
  const [rearCorrections, setRearCorrections] = useState<number[][]>(() =>
    rpmBins.map(() => mapBins.map(() => 0)),
  );

  const frontHitsRef = useRef<number[][]>([]);
  const rearHitsRef = useRef<number[][]>([]);
  const frontAccRef = useRef<{ sum: number; count: number }[][]>([]);
  const rearAccRef = useRef<{ sum: number; count: number }[][]>([]);

  const initRefs = useCallback(() => {
    frontHitsRef.current = rpmBins.map(() => mapBins.map(() => 0));
    rearHitsRef.current = rpmBins.map(() => mapBins.map(() => 0));
    frontAccRef.current = rpmBins.map(() => mapBins.map(() => ({ sum: 0, count: 0 })));
    rearAccRef.current = rpmBins.map(() => mapBins.map(() => ({ sum: 0, count: 0 })));
  }, [rpmBins, mapBins]);

  useEffect(() => {
    setFrontHits(rpmBins.map(() => mapBins.map(() => 0)));
    setRearHits(rpmBins.map(() => mapBins.map(() => 0)));
    setFrontCorrections(rpmBins.map(() => mapBins.map(() => 0)));
    setRearCorrections(rpmBins.map(() => mapBins.map(() => 0)));
    initRefs();
  }, [rpmBins, mapBins, initRefs]);

  const cellTrace = useMemo(() => {
    if (!live.isConnected || liveValues.rpm < 500) return null;
    return calculateCellTrace(liveValues.rpm, liveValues.map, rpmBins, mapBins);
  }, [live.isConnected, liveValues.rpm, liveValues.map, rpmBins, mapBins]);

  useEffect(() => {
    if (!cellTrace || liveValues.rpm < 800) {
      if (debugHeatmap) {
        // Debug: log why accumulation isn't happening
        if (!cellTrace) console.log('[VEHeatmap] No cellTrace');
        if (liveValues.rpm < 800) console.log('[VEHeatmap] RPM too low:', liveValues.rpm);
      }
      return;
    }
    const fHits = frontHitsRef.current;
    const rHits = rearHitsRef.current;
    const fAcc = frontAccRef.current;
    const rAcc = rearAccRef.current;

    if (debugHeatmap) {
      console.log(
        '[VEHeatmap] Accumulating hits. RPM:',
        liveValues.rpm,
        'MAP:',
        liveValues.map,
        'Active cells:',
        cellTrace.activeCells.length,
      );
    }

    for (const cell of cellTrace.activeCells) {
      if (cell.weight <= 0.2) continue;
      const i = cell.rpmIdx;
      const j = cell.mapIdx;
      fHits[i][j] += 1;
      rHits[i][j] += 1;
    }

    if (liveValues.afrFront > 8 && liveValues.afrFront < 20) {
      for (const cell of cellTrace.activeCells) {
        if (cell.weight <= 0.2) continue;
        const i = cell.rpmIdx;
        const j = cell.mapIdx;
        fAcc[i][j].sum += liveValues.afrFront * cell.weight;
        fAcc[i][j].count += cell.weight;
      }
    } else {
      if (debugHeatmap) console.log('[VEHeatmap] AFR Front out of range:', liveValues.afrFront);
    }

    if (liveValues.afrRear > 8 && liveValues.afrRear < 20) {
      for (const cell of cellTrace.activeCells) {
        if (cell.weight <= 0.2) continue;
        const i = cell.rpmIdx;
        const j = cell.mapIdx;
        rAcc[i][j].sum += liveValues.afrRear * cell.weight;
        rAcc[i][j].count += cell.weight;
      }
    } else {
      if (debugHeatmap) console.log('[VEHeatmap] AFR Rear out of range:', liveValues.afrRear);
    }
  }, [cellTrace, liveValues.afrFront, liveValues.afrRear, liveValues.rpm, liveValues.map, debugHeatmap]);

  useEffect(() => {
    const interval = setInterval(() => {
      const fHits = frontHitsRef.current;
      const rHits = rearHitsRef.current;
      const fAcc = frontAccRef.current;
      const rAcc = rearAccRef.current;

      if (debugHeatmap) {
        // Debug: check if refs have data
        const totalFrontHits = fHits.flat().reduce((sum, val) => sum + val, 0);
        const totalRearHits = rHits.flat().reduce((sum, val) => sum + val, 0);
        console.log('[VEHeatmap] State update - Total front hits:', totalFrontHits, 'Total rear hits:', totalRearHits);
      }

      setFrontHits(fHits.map((row) => [...row]));
      setRearHits(rHits.map((row) => [...row]));

      const calcCorrections = (acc: { sum: number; count: number }[][]) => {
        const result = rpmBins.map(() => mapBins.map(() => 0));
        for (let i = 0; i < rpmBins.length; i++) {
          for (let j = 0; j < mapBins.length; j++) {
            const cell = acc[i]?.[j];
            if (cell && cell.count >= MIN_HITS_FOR_CORRECTION) {
              const meanAfr = cell.sum / cell.count;
              const targetAfr = getTargetAfrForMap(mapBins[j], afrTargets);
              const ratio = meanAfr / targetAfr;
              const clamped = Math.max(1 - MAX_CORRECTION, Math.min(1 + MAX_CORRECTION, ratio));
              result[i][j] = (clamped - 1) * 100;
            }
          }
        }
        return result;
      };

      setFrontCorrections(calcCorrections(fAcc));
      setRearCorrections(calcCorrections(rAcc));

      // Notify parent of hit count changes
      if (onHitCountsChange) {
        onHitCountsChange(
          fHits.map((row) => [...row]),
          rHits.map((row) => [...row]),
          rpmBins,
          mapBins
        );
      }
    }, 250);

    return () => clearInterval(interval);
  }, [afrTargets, mapBins, rpmBins, onHitCountsChange, debugHeatmap]);

  const displayCorrections = cylinder === 'front' ? frontCorrections : rearCorrections;
  const displayHits = cylinder === 'front' ? frontHits : rearHits;

  const balanceDelta = useMemo(() => {
    let total = 0;
    let count = 0;
    for (let i = 0; i < rpmBins.length; i++) {
      for (let j = 0; j < mapBins.length; j++) {
        if (frontHits[i][j] > 0 && rearHits[i][j] > 0) {
          total += frontCorrections[i][j] - rearCorrections[i][j];
          count += 1;
        }
      }
    }
    if (count === 0) return 0;
    return total / count;
  }, [frontCorrections, rearCorrections, frontHits, rearHits, rpmBins.length, mapBins.length]);

  const balanceLabel = `${balanceDelta >= 0 ? '+' : ''}${balanceDelta.toFixed(DISPLAY_DECIMALS)}%`;
  const balanceClass =
    Math.abs(balanceDelta) > 3
      ? 'text-red-400'
      : Math.abs(balanceDelta) > 2
        ? 'text-amber-400'
        : 'text-zinc-300';

  const colorScale = useMemo(() => buildColorScale(256), []);

  const maxHits = useMemo(() => {
    let max = 0;
    for (const row of displayHits) {
      for (const hit of row) max = Math.max(max, hit);
    }
    return max || 1;
  }, [displayHits]);

  const getCoverageColor = useCallback(
    (hits: number) => {
      const t = Math.min(1, hits / maxHits);
      const r = Math.round(17 + (191 - 17) * t);
      const g = Math.round(24 + (219 - 24) * t);
      const b = Math.round(39 + (254 - 39) * t);
      return `rgb(${r}, ${g}, ${b})`;
    },
    [maxHits],
  );

  const gridRef = useRef<HTMLDivElement>(null);
  const [gridSize, setGridSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    if (!gridRef.current) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setGridSize({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
      }
    });
    observer.observe(gridRef.current);
    return () => observer.disconnect();
  }, []);

  // Calculate raw cell dimensions from container and grid
  let cellWidth = Math.floor((gridSize.width - AXIS_LABEL_WIDTH) / mapBins.length);
  let cellHeight = Math.floor((gridSize.height - AXIS_LABEL_HEIGHT) / rpmBins.length);

  // CRITICAL: Cap aspect ratio to prevent ultra-wide rectangular cells
  if (cellHeight > 0 && cellWidth / cellHeight > MAX_ASPECT_RATIO) {
    cellWidth = Math.floor(cellHeight * MAX_ASPECT_RATIO);
  }

  // Enforce minimum readability
  const needsScroll = cellWidth < MIN_CELL_WIDTH || cellHeight < MIN_CELL_HEIGHT;
  const effectiveCellWidth = Math.max(cellWidth, MIN_CELL_WIDTH);
  const effectiveCellHeight = Math.max(cellHeight, MIN_CELL_HEIGHT);

  // If grid is now narrower than container, center it horizontally
  const gridPixelWidth = effectiveCellWidth * mapBins.length + AXIS_LABEL_WIDTH;
  const gridPixelHeight = effectiveCellHeight * rpmBins.length + AXIS_LABEL_HEIGHT;
  const horizontalPadding = needsScroll ? 0 : Math.max(0, (gridSize.width - gridPixelWidth) / 2);

  const gridStyle = {
    gridTemplateColumns: `${AXIS_LABEL_WIDTH}px repeat(${mapBins.length}, ${effectiveCellWidth}px)`,
    gridTemplateRows: `${AXIS_LABEL_HEIGHT}px repeat(${rpmBins.length}, ${effectiveCellHeight}px)`,
    width: needsScroll ? gridPixelWidth : gridPixelWidth,
    height: needsScroll ? gridPixelHeight : undefined,
    marginLeft: horizontalPadding > 0 ? `${horizontalPadding}px` : undefined,
  } as const;

  const activeCell = cellTrace ? { row: cellTrace.rpmIdx, col: cellTrace.mapIdx } : null;
  const neighborCells = useMemo(() => {
    if (!cellTrace) return new Set<string>();
    const set = new Set<string>();
    for (const cell of cellTrace.activeCells) {
      if (cell.rpmIdx === cellTrace.rpmIdx && cell.mapIdx === cellTrace.mapIdx) continue;
      set.add(`${cell.rpmIdx}-${cell.mapIdx}`);
    }
    return set;
  }, [cellTrace]);

  const handleCylinderChange = (next: Cylinder) => {
    setLocalCylinder(next);
    onCylinderChange?.(next);
  };

  const handleCellHover = (row: number, col: number, value: number, hits: number, event: MouseEvent<HTMLDivElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const confidence = getConfidenceLabel(hits);
    const correction = getCorrectionDisplay(value, hits);
    const absCorrValue = Math.abs(value);
    let clampNote = '';
    if (absCorrValue >= 15) {
      clampNote = ' | ⚠ MAX clamp at ±15%';
    } else if (absCorrValue >= 7) {
      clampNote = ` | ⚠ Clamped at ±7% — computed ${value >= 0 ? '+' : ''}${value.toFixed(DISPLAY_DECIMALS)}%`;
    }
    setTooltip({
      x: rect.left + rect.width / 2,
      y: rect.top - 8,
      text: `RPM: ${rpmBins[row]} | MAP: ${mapBins[col]} kPa | Correction: ${correction} | Hits: ${hits} | Confidence: ${confidence} | ${cylinder === 'front' ? 'Front' : 'Rear'} Cyl${clampNote}`,
    });
  };

  const handleCellLeave = () => setTooltip(null);

  return (
    <div className={cn('flex h-full flex-col rounded-lg border border-zinc-800 bg-zinc-900', className)}>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="text-xs font-medium uppercase tracking-wider text-zinc-500">VE Heatmap</div>
          <div className="flex items-center rounded-md border border-zinc-800 bg-zinc-950/60 p-1 text-xs">
            <button
              type="button"
              className={cn(
                'rounded px-2 py-1 transition-colors',
                cylinder === 'front' ? 'bg-orange-500 text-white' : 'text-zinc-400 hover:text-zinc-200',
              )}
              onClick={() => handleCylinderChange('front')}
            >
              Front
            </button>
            <button
              type="button"
              className={cn(
                'rounded px-2 py-1 transition-colors',
                cylinder === 'rear' ? 'bg-orange-500 text-white' : 'text-zinc-400 hover:text-zinc-200',
              )}
              onClick={() => handleCylinderChange('rear')}
            >
              Rear
            </button>
          </div>
          <div className={cn('text-xs font-medium', balanceClass)}>
            dF-R {balanceLabel}
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs">
          <button
            type="button"
            className={cn(
              'rounded-md border border-zinc-800 px-2 py-1 text-zinc-400 transition-colors',
              showCoverage ? 'bg-zinc-800 text-zinc-100' : 'hover:text-zinc-200',
            )}
            onClick={() => setShowCoverage((prev) => !prev)}
          >
            Coverage
          </button>
          <button
            type="button"
            className={cn(
              'rounded-md border border-zinc-800 px-2 py-1 text-zinc-400 transition-colors',
              showUncertainty ? 'bg-zinc-800 text-zinc-100' : 'hover:text-zinc-200',
            )}
            onClick={() => setShowUncertainty((prev) => !prev)}
          >
            Uncertainty
          </button>
        </div>
      </div>

      <div ref={gridRef} className="relative flex-1 overflow-hidden">
        <div className={cn('absolute inset-0', needsScroll ? 'overflow-auto' : 'overflow-hidden')}>
          <div className="grid gap-px bg-zinc-800 p-px" style={gridStyle}>
            <div className="flex flex-col justify-center px-2 text-[10px] text-zinc-600">
              <span>RPM ↑</span>
              <span>kPa →</span>
            </div>
            {mapBins.map((map) => (
              <div
                key={`map-${map}`}
                className="flex items-center justify-center bg-zinc-900 text-[10px] text-zinc-400"
              >
                {map}
              </div>
            ))}
            {rpmBins.map((rpm, rowIdx) => (
              <Fragment key={`rpm-row-${rpm}`}>
                <div
                  className="flex items-center justify-end bg-zinc-900 pr-2 text-[10px] text-zinc-400"
                >
                  {rpm}
                </div>
                {mapBins.map((map, colIdx) => {
                  const correction = displayCorrections[rowIdx]?.[colIdx] ?? 0;
                  const hits = displayHits[rowIdx]?.[colIdx] ?? 0;
                  const clamped = Math.abs(correction) > 7;
                  const normalized = Math.max(-7, Math.min(7, correction));
                  const colorIndex = Math.round(((normalized + 7) / 14) * (colorScale.length - 1));
                  const correctionColor = colorScale[colorIndex] ?? 'rgb(63, 63, 70)';
                  const isNoData = hits === 0;
                  const coverageColor = getCoverageColor(hits);
                  // Spec: no-data = zinc-950 (#09090b), zero-correction = zinc-700, corrections = color scale
                  const background = showCoverage
                    ? coverageColor
                    : isNoData
                      ? '#09090b'
                      : correctionColor;
                  const textColor = isNoData
                    ? '#52525b'  // zinc-600 for no-data dash
                    : getLuminanceFromRgb(background) > 0.55 ? '#18181b' : '#fafafa';
                  const display = showCoverage
                    ? hits > 0
                      ? `${hits}`
                      : MISSING_VALUE
                    : getCorrectionDisplay(correction, hits);
                  const isActive = activeCell?.row === rowIdx && activeCell?.col === colIdx;
                  const isNeighbor = neighborCells.has(`${rowIdx}-${colIdx}`);
                  const uncertaintyValue = uncertaintyMap?.[rowIdx]?.[colIdx] ?? 1;
                  const showUncertaintyCell = showUncertainty && uncertaintyValue < 0.5;
                  const isClampWarning = Math.abs(correction) >= 7;
                  const isClampCritical = Math.abs(correction) >= 15;
                  const cellTextSize = getCellTextSize(effectiveCellWidth);

                  return (
                    <VECell
                      key={`cell-${rowIdx}-${colIdx}`}
                      correction={isNoData ? null : correction}
                      hitCount={hits}
                      isCurrentCell={isActive}
                      isAdjacentCell={isNeighbor}
                      isSelected={false}
                      isClampWarning={isClampWarning}
                      isClampCritical={isClampCritical}
                      width={effectiveCellWidth}
                      height={effectiveCellHeight}
                      textSize={cellTextSize}
                      display={display}
                      background={background}
                      textColor={textColor}
                      showUncertainty={showUncertaintyCell}
                      onHover={(event) => handleCellHover(rowIdx, colIdx, correction, hits, event)}
                      onLeave={handleCellLeave}
                    />
                  );
                })}
              </Fragment>
            ))}
          </div>
        </div>
      </div>

      {tooltip && (
        <div
          className="pointer-events-none fixed z-50 rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2 text-xs text-zinc-200"
          style={{ left: tooltip.x, top: tooltip.y, transform: 'translate(-50%, -100%)' }}
        >
          {tooltip.text}
        </div>
      )}
    </div>
  );
}

function VEHeatmapPanelWithLive({
  apiUrl,
  afrTargets,
  enginePreset,
  customRpmBins,
  customMapBins,
  activeCylinder,
  onCylinderChange,
  onHitCountsChange,
  uncertaintyMap,
  className,
}: VEHeatmapPanelProps) {
  const live = useJetDriveLive({
    apiUrl: apiUrl ?? 'http://127.0.0.1:5001/api/jetdrive',
    autoConnect: true,
    pollInterval: 800,
    useSse: true,
  });

  return (
    <VEHeatmapPanelContent
      live={live}
      afrTargets={afrTargets ?? DEFAULT_AFR_TARGETS}
      enginePreset={enginePreset}
      customRpmBins={customRpmBins}
      customMapBins={customMapBins}
      activeCylinder={activeCylinder}
      onCylinderChange={onCylinderChange}
      onHitCountsChange={onHitCountsChange}
      uncertaintyMap={uncertaintyMap}
      className={className}
    />
  );
}

export function VEHeatmapPanel({
  live,
  apiUrl,
  afrTargets,
  enginePreset,
  customRpmBins,
  customMapBins,
  activeCylinder,
  onCylinderChange,
  onHitCountsChange,
  uncertaintyMap,
  className,
}: VEHeatmapPanelProps) {
  if (live) {
    return (
      <VEHeatmapPanelContent
        live={live}
        afrTargets={afrTargets ?? DEFAULT_AFR_TARGETS}
        enginePreset={enginePreset}
        customRpmBins={customRpmBins}
        customMapBins={customMapBins}
        activeCylinder={activeCylinder}
        onCylinderChange={onCylinderChange}
        onHitCountsChange={onHitCountsChange}
        uncertaintyMap={uncertaintyMap}
        className={className}
      />
    );
  }

  return (
    <VEHeatmapPanelWithLive
      apiUrl={apiUrl}
      afrTargets={afrTargets}
      enginePreset={enginePreset}
      customRpmBins={customRpmBins}
      customMapBins={customMapBins}
      activeCylinder={activeCylinder}
      onCylinderChange={onCylinderChange}
      onHitCountsChange={onHitCountsChange}
      uncertaintyMap={uncertaintyMap}
      className={className}
    />
  );
}
