import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { MouseEvent } from 'react';
import { cn } from '../../lib/utils';
import { useThrottle } from '../../hooks/useDebounce';
import {
  useJetDriveLive,
  type JetDriveChannel,
  type UseJetDriveLiveReturn,
} from '../../hooks/useJetDriveLive';
import type { LiveVEExportData } from './LiveVETable';
import { ENGINE_GRID_CONFIGS, type EnginePreset } from '../../utils/enginePresets';
import { DEFAULT_AFR_TARGETS } from './AFRTargetTable';
import { VECell } from './VECell';

const MISSING_VALUE = '—';

const MIN_CELL_WIDTH = 29;   // allows 17 MAP columns on typical 1080p layouts
const MIN_CELL_HEIGHT = 24;  // fits one line of text
const MAX_ASPECT_RATIO = 2.0; // permit narrower cells before width is capped
const AXIS_LABEL_WIDTH = 40;
const AXIS_LABEL_HEIGHT = 28;
const MAX_CORRECTION = 0.15; // +/-15% preview clamp
const MIN_HITS_FOR_CORRECTION = 1;
// UI-only formatting precision for display labels/tooltips (does not affect correction math)
const DISPLAY_DECIMALS = 0;

function formatSignedPercent(value: number, decimals: number = DISPLAY_DECIMALS): string {
  const sign = value >= 0 ? '+' : '';
  if (decimals <= 0) return `${sign}${Math.round(value)}%`;
  return `${sign}${value.toFixed(decimals)}%`;
}

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
  onLiveDataUpdate?: (data: LiveVEExportData) => void;
  uncertaintyMap?: number[][];
  targetMarker?: { rpm: number; map: number; label?: string } | null;
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

function expandRpmBins(baseBins: number[], targetCount: number): number[] {
  if (baseBins.length <= 1 || targetCount <= baseBins.length) return baseBins;
  const min = baseBins[0];
  const max = baseBins[baseBins.length - 1];
  const step = (max - min) / (targetCount - 1);
  const bins = Array.from({ length: targetCount }, (_, idx) => Math.round(min + step * idx));
  return dedupeBins(bins);
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
  return formatSignedPercent(value);
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

function rpmMapToPixel(
  rpm: number,
  map: number,
  rpmBins: number[],
  mapBins: number[],
  cellWidth: number,
  cellHeight: number,
): { x: number; y: number; inBounds: boolean } {
  if (rpmBins.length < 2 || mapBins.length < 2) {
    return { x: AXIS_LABEL_WIDTH, y: AXIS_LABEL_HEIGHT, inBounds: false };
  }
  const rpmMin = rpmBins[0];
  const rpmMax = rpmBins[rpmBins.length - 1];
  const mapMin = mapBins[0];
  const mapMax = mapBins[mapBins.length - 1];
  const inBounds = rpm >= rpmMin && rpm <= rpmMax && map >= mapMin && map <= mapMax;

  const clampedRpm = Math.max(rpmMin, Math.min(rpmMax, rpm));
  const clampedMap = Math.max(mapMin, Math.min(mapMax, map));

  let rpmIdx = 0;
  let rpmWeight = 0;
  for (let i = 0; i < rpmBins.length - 1; i++) {
    if (clampedRpm >= rpmBins[i] && clampedRpm < rpmBins[i + 1]) {
      rpmIdx = i;
      rpmWeight = (clampedRpm - rpmBins[i]) / (rpmBins[i + 1] - rpmBins[i]);
      break;
    }
    if (clampedRpm >= rpmBins[rpmBins.length - 1]) {
      rpmIdx = rpmBins.length - 1;
      rpmWeight = 1;
    }
  }

  let mapIdx = 0;
  let mapWeight = 0;
  for (let i = 0; i < mapBins.length - 1; i++) {
    if (clampedMap >= mapBins[i] && clampedMap < mapBins[i + 1]) {
      mapIdx = i;
      mapWeight = (clampedMap - mapBins[i]) / (mapBins[i + 1] - mapBins[i]);
      break;
    }
    if (clampedMap >= mapBins[mapBins.length - 1]) {
      mapIdx = mapBins.length - 1;
      mapWeight = 1;
    }
  }

  const x = AXIS_LABEL_WIDTH + (mapIdx + mapWeight) * cellWidth;
  const y = AXIS_LABEL_HEIGHT + (rpmIdx + rpmWeight) * cellHeight;
  return { x, y, inBounds };
}

/** Compute text size based on cell dimensions */
function getCellTextSize(cellWidth: number): string {
  if (cellWidth >= 72) return 'text-xs';
  if (cellWidth >= 42) return 'text-[10px]';
  if (cellWidth >= 32) return 'text-[9px]';
  return 'text-[8px]';
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
  onLiveDataUpdate,
  uncertaintyMap,
  targetMarker,
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
  onLiveDataUpdate?: (data: LiveVEExportData) => void;
  uncertaintyMap?: number[][];
  targetMarker?: { rpm: number; map: number; label?: string } | null;
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
    () => {
      if (customRpmBins && customRpmBins.length) return dedupeBins(customRpmBins);
      if (enginePreset === 'harley_m8') return expandRpmBins(config.rpmBins, 21);
      return config.rpmBins;
    },
    [customRpmBins, config.rpmBins, enginePreset],
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
  const liveValues = useThrottle(rawLiveValues, 50);
  const hudLiveValues = useThrottle(rawLiveValues, 80);
  const [displayHudValues, setDisplayHudValues] = useState(hudLiveValues);

  useEffect(() => {
    setDisplayHudValues((prev) => {
      const rpmDelta = hudLiveValues.rpm - prev.rpm;
      const mapDelta = hudLiveValues.map - prev.map;
      const rpm = Math.abs(rpmDelta) < 25 ? prev.rpm : prev.rpm + rpmDelta * 0.55;
      const map = Math.abs(mapDelta) < 1.0 ? prev.map : prev.map + mapDelta * 0.55;
      return {
        ...hudLiveValues,
        rpm,
        map,
      };
    });
  }, [hudLiveValues]);

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
    if (!cellTrace || liveValues.rpm < 500) {
      if (debugHeatmap) {
        // Debug: log why accumulation isn't happening
        if (!cellTrace) console.log('[VEHeatmap] No cellTrace');
        if (liveValues.rpm < 500) console.log('[VEHeatmap] RPM too low:', liveValues.rpm);
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

  // Ref to hold the latest channel values seen from drained samples.
  // Updated each flush cycle so RPM/MAP/AFR can be reconstructed from individual channel entries.
  const drainChannelValuesRef = useRef<Record<string, number>>({});

  // ── VE cell flush: use requestAnimationFrame for display-aligned timing ──
  // This replaces the old 250ms setInterval. RAF fires at ~60Hz (16.7ms) which
  // is much better aligned with the 50ms aggregation window and 100ms drain
  // polling. We throttle the heavy state updates to at most every 100ms to
  // avoid excessive React re-renders while keeping accumulation up to date.
  useEffect(() => {
    let rafId: number | null = null;
    let lastFlushAt = 0;
    const FLUSH_INTERVAL_MS = 100; // state update cadence (10Hz)

    const tick = () => {
      const now = performance.now();

      const fHits = frontHitsRef.current;
      const rHits = rearHitsRef.current;
      const fAcc = frontAccRef.current;
      const rAcc = rearAccRef.current;

      // ── Process drained samples for VE accumulation ──────────────
      // This gives us every sample from the backend ring buffer, not just
      // the latest snapshot value. Each drained sample is a single channel
      // entry (e.g., "Digital RPM 1" = 3500). We maintain running latest
      // values per channel and run cell trace + accumulation whenever we
      // see an RPM sample (the trigger signal for a new "moment").
      if (live.consumeDrainedSamples) {
        const drained = live.consumeDrainedSamples();
        if (drained.length > 0) {
          const cv = drainChannelValuesRef.current;

          for (const sample of drained) {
            cv[sample.name] = sample.value;

            // Only trigger accumulation on RPM updates (the fastest-changing
            // dyno signal), which ensures we have a fresh RPM+MAP pair.
            const isRpmSample = RPM_CANDIDATES.some(
              (c) => c === sample.name || sample.name.toLowerCase().includes('rpm'),
            );
            if (!isRpmSample) continue;

            // Reconstruct current values from the running channel map
            const rpm = cv['Digital RPM 1'] ?? cv['Engine RPM'] ?? cv['RPM'] ?? cv['Digital RPM 2'] ?? 0;
            const map = cv['MAP kPa'] ?? cv['MAP'] ?? 0;
            const afrFront =
              cv['Air/Fuel Ratio 1'] ?? cv['User Analog 1'] ?? cv['AFR Front'] ?? cv['AFR 1'] ?? cv['AFR'] ?? 0;
            const afrRear =
              cv['Air/Fuel Ratio 2'] ?? cv['User Analog 2'] ?? cv['AFR Rear'] ?? cv['AFR 2'] ?? 0;

            if (rpm < 500 || map <= 0) continue;

            const trace = calculateCellTrace(rpm, map, rpmBins, mapBins);
            for (const cell of trace.activeCells) {
              if (cell.weight <= 0.2) continue;
              const i = cell.rpmIdx;
              const j = cell.mapIdx;
              fHits[i][j] += 1;
              rHits[i][j] += 1;
            }

            if (afrFront > 8 && afrFront < 20) {
              for (const cell of trace.activeCells) {
                if (cell.weight <= 0.2) continue;
                const i = cell.rpmIdx;
                const j = cell.mapIdx;
                fAcc[i][j].sum += afrFront * cell.weight;
                fAcc[i][j].count += cell.weight;
              }
            }

            if (afrRear > 8 && afrRear < 20) {
              for (const cell of trace.activeCells) {
                if (cell.weight <= 0.2) continue;
                const i = cell.rpmIdx;
                const j = cell.mapIdx;
                rAcc[i][j].sum += afrRear * cell.weight;
                rAcc[i][j].count += cell.weight;
              }
            }
          }

          if (debugHeatmap) {
            console.log('[VEHeatmap] Processed', drained.length, 'drained samples');
          }
        }
      }

      // Throttle React state updates to FLUSH_INTERVAL_MS
      if (now - lastFlushAt >= FLUSH_INTERVAL_MS) {
        lastFlushAt = now;

        if (debugHeatmap) {
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

        const nextFrontCorrections = calcCorrections(fAcc);
        const nextRearCorrections = calcCorrections(rAcc);
        setFrontCorrections(nextFrontCorrections);
        setRearCorrections(nextRearCorrections);

        // Notify parent of hit count changes
        if (onHitCountsChange) {
          onHitCountsChange(
            fHits.map((row) => [...row]),
            rHits.map((row) => [...row]),
            rpmBins,
            mapBins,
          );
        }

        if (onLiveDataUpdate) {
          const combinedHits = fHits.map((row, rowIdx) =>
            row.map((frontHit, colIdx) => Math.min(frontHit, rHits[rowIdx]?.[colIdx] ?? 0)),
          );
          const totalHits = combinedHits.flat().reduce((sum, value) => sum + value, 0);
          onLiveDataUpdate({
            frontCorrections: nextFrontCorrections,
            rearCorrections: nextRearCorrections,
            hitCounts: combinedHits,
            frontHitCounts: fHits.map((row) => [...row]),
            rearHitCounts: rHits.map((row) => [...row]),
            rpmBins,
            mapBins,
            afrTargets,
            enginePreset,
            totalHits,
            exportedAt: new Date().toISOString(),
          });
        }
      }

      rafId = requestAnimationFrame(tick);
    };

    rafId = requestAnimationFrame(tick);

    return () => {
      if (rafId !== null) cancelAnimationFrame(rafId);
    };
  }, [afrTargets, mapBins, rpmBins, onHitCountsChange, onLiveDataUpdate, enginePreset, debugHeatmap, live]);

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

  const balanceLabel = formatSignedPercent(balanceDelta);
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
  // Reserve space for the compact stats panel (min 224px + 1px border) — 20% wider than current for optimal balance
  const STATS_PANEL_MIN_WIDTH = 225;
  const availableGridWidth = Math.max(0, gridSize.width - STATS_PANEL_MIN_WIDTH);
  let cellWidth = Math.floor((availableGridWidth - AXIS_LABEL_WIDTH) / mapBins.length);
  let cellHeight = Math.floor((gridSize.height - AXIS_LABEL_HEIGHT) / rpmBins.length);

  // CRITICAL: Cap aspect ratio to prevent ultra-wide rectangular cells
  if (cellHeight > 0 && cellWidth / cellHeight > MAX_ASPECT_RATIO) {
    cellWidth = Math.floor(cellHeight * MAX_ASPECT_RATIO);
  }

  // Enforce minimum readability
  const needsScroll = cellWidth < MIN_CELL_WIDTH || cellHeight < MIN_CELL_HEIGHT;
  const effectiveCellWidth = Math.max(cellWidth, MIN_CELL_WIDTH);
  const effectiveCellHeight = Math.max(cellHeight, MIN_CELL_HEIGHT);

  // Grid pixel dimensions — no centering; stats panel fills remaining space
  const gridPixelWidth = effectiveCellWidth * mapBins.length + AXIS_LABEL_WIDTH;
  const gridPixelHeight = effectiveCellHeight * rpmBins.length + AXIS_LABEL_HEIGHT;

  const gridStyle = {
    gridTemplateColumns: `${AXIS_LABEL_WIDTH}px repeat(${mapBins.length}, ${effectiveCellWidth}px)`,
    gridTemplateRows: `${AXIS_LABEL_HEIGHT}px repeat(${rpmBins.length}, ${effectiveCellHeight}px)`,
    width: gridPixelWidth,
    height: needsScroll ? gridPixelHeight : undefined,
  } as const;

  const currentPos = useMemo(
    () =>
      rpmMapToPixel(
        displayHudValues.rpm,
        displayHudValues.map,
        rpmBins,
        mapBins,
        effectiveCellWidth,
        effectiveCellHeight,
      ),
    [displayHudValues, rpmBins, mapBins, effectiveCellWidth, effectiveCellHeight],
  );

  const targetPos = useMemo(() => {
    if (!targetMarker) return null;
    return rpmMapToPixel(
      targetMarker.rpm,
      targetMarker.map,
      rpmBins,
      mapBins,
      effectiveCellWidth,
      effectiveCellHeight,
    );
  }, [targetMarker, rpmBins, mapBins, effectiveCellWidth, effectiveCellHeight]);

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

  // ── Stats panel data (derived from existing state) ──────────────────
  const gridStats = useMemo(() => {
    const totalCells = rpmBins.length * mapBins.length;
    let cellsWithData = 0;
    let totalHits = 0;
    let correctionSum = 0;
    let correctionCount = 0;
    let minCorr = Infinity;
    let maxCorr = -Infinity;
    // Zone accumulators — cruise: MAP < 60, partThrottle: 60-80, wot: > 80
    const zones = {
      cruise: { hits: 0, cells: 0, corrSum: 0, corrCount: 0, total: 0 },
      partThrottle: { hits: 0, cells: 0, corrSum: 0, corrCount: 0, total: 0 },
      wot: { hits: 0, cells: 0, corrSum: 0, corrCount: 0, total: 0 },
    };

    for (let i = 0; i < rpmBins.length; i++) {
      for (let j = 0; j < mapBins.length; j++) {
        const hits = displayHits[i]?.[j] ?? 0;
        const corr = displayCorrections[i]?.[j] ?? 0;
        const mapVal = mapBins[j];
        const zone = mapVal < 60 ? zones.cruise : mapVal <= 80 ? zones.partThrottle : zones.wot;
        zone.total += 1;

        totalHits += hits;
        if (hits > 0) {
          cellsWithData += 1;
          correctionSum += corr;
          correctionCount += 1;
          minCorr = Math.min(minCorr, corr);
          maxCorr = Math.max(maxCorr, corr);
          zone.cells += 1;
          zone.corrSum += corr;
          zone.corrCount += 1;
        }
        zone.hits += hits;
      }
    }

    return {
      totalCells,
      cellsWithData,
      totalHits,
      meanCorr: correctionCount > 0 ? correctionSum / correctionCount : 0,
      maxAbsCorr: correctionCount > 0 ? Math.max(Math.abs(minCorr), Math.abs(maxCorr)) : 0,
      minCorr: correctionCount > 0 ? minCorr : 0,
      maxCorr: correctionCount > 0 ? maxCorr : 0,
      zones: {
        cruise: {
          coverage: zones.cruise.total > 0 ? Math.round((zones.cruise.cells / zones.cruise.total) * 100) : 0,
          meanCorr: zones.cruise.corrCount > 0 ? zones.cruise.corrSum / zones.cruise.corrCount : 0,
        },
        partThrottle: {
          coverage: zones.partThrottle.total > 0 ? Math.round((zones.partThrottle.cells / zones.partThrottle.total) * 100) : 0,
          meanCorr: zones.partThrottle.corrCount > 0 ? zones.partThrottle.corrSum / zones.partThrottle.corrCount : 0,
        },
        wot: {
          coverage: zones.wot.total > 0 ? Math.round((zones.wot.cells / zones.wot.total) * 100) : 0,
          meanCorr: zones.wot.corrCount > 0 ? zones.wot.corrSum / zones.wot.corrCount : 0,
        },
      },
    };
  }, [displayCorrections, displayHits, rpmBins, mapBins]);

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
      clampNote = ` | ⚠ Clamped at ±7% — computed ${formatSignedPercent(value)}`;
    }
    setTooltip({
      x: rect.left + rect.width / 2,
      y: rect.top - 12,
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

      <div ref={gridRef} className="relative flex flex-1 overflow-hidden">
        {/* Heatmap grid — left-aligned, shrink-to-fit */}
        <div className={cn('shrink-0', needsScroll ? 'overflow-auto' : 'overflow-hidden')}>
          <div className="relative" style={{ width: gridPixelWidth, height: gridPixelHeight }}>
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
                  // no-data = zinc-800/40 (visible rectangle), zero-correction = zinc-700, corrections = color scale
                  const background = showCoverage
                    ? coverageColor
                    : isNoData
                      ? '#1e1e22'
                      : correctionColor;
                  const textColor = isNoData
                    ? '#52525b'  // zinc-600 — visible dash on #1e1e22
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

          <div className="pointer-events-none absolute inset-0 z-10">
            {live.isConnected && displayHudValues.rpm >= 500 && currentPos.inBounds && (
              <div
                className="absolute"
                style={{ left: currentPos.x, top: currentPos.y, transform: 'translate(-50%, -50%)' }}
              >
                <div className="h-5 w-5 rounded-full border border-emerald-400/60" />
                <div className="absolute left-1/2 top-1/2 h-px w-5 -translate-x-1/2 bg-emerald-400/80" />
                <div className="absolute left-1/2 top-1/2 w-px h-5 -translate-y-1/2 bg-emerald-400/80" />
              </div>
            )}
            {targetMarker && targetPos?.inBounds && (
              <div
                className="absolute"
                style={{ left: targetPos.x, top: targetPos.y, transform: 'translate(-50%, -50%)' }}
              >
                <div className="h-9 w-9 rounded-full border border-amber-400/70 border-dashed" />
                <div className="mt-1 text-[10px] uppercase tracking-wider text-amber-400/90 text-center">
                  {targetMarker.label ?? 'Target'}
                </div>
              </div>
            )}
          </div>
        </div>
        </div>

        {/* Stats panel — fills remaining width to the right of the grid */}
        <div className="flex-1 min-w-[224px] border-l border-zinc-800 overflow-y-auto px-2 py-2 space-y-2">
          {/* Color Scale Legend */}
          <div>
            <div className="mb-1 text-[10px] uppercase tracking-widest text-zinc-600">Correction Scale</div>
            <div className="flex items-stretch gap-1.5">
              <div
                className="w-3.5 rounded-sm"
                style={{
                  background: 'linear-gradient(to bottom, #2563eb, #60a5fa, #93c5fd, #bfdbfe, #3f3f46, #fed7aa, #fdba74, #fb923c, #ea580c)',
                  minHeight: 96,
                }}
              />
              <div className="flex flex-col justify-between text-[10px] font-mono tabular-nums text-zinc-500">
                <span>-7%</span>
                <span>-3%</span>
                <span>&nbsp;0%</span>
                <span>+3%</span>
                <span>+7%</span>
              </div>
            </div>
          </div>

          {/* Zone Summary */}
          <div className="border-t border-zinc-800 pt-2">
            <div className="mb-1 text-[10px] uppercase tracking-widest text-zinc-600">Zone Summary</div>
            <div className="space-y-1.5">
              {([
                ['Cruise', gridStats.zones.cruise] as const,
                ['Part Throttle', gridStats.zones.partThrottle] as const,
                ['WOT', gridStats.zones.wot] as const,
              ]).map(([label, zone]) => (
                <div key={label} className="flex items-center justify-between">
                  <span className="text-[10px] text-zinc-500">{label}</span>
                  <div className="flex items-center gap-1 text-[10px] font-mono tabular-nums">
                    <span className={cn(
                      zone.coverage >= 70 ? 'text-green-400' : zone.coverage >= 40 ? 'text-amber-400' : 'text-zinc-500',
                    )}>
                      {zone.coverage}%
                    </span>
                    <span className="text-zinc-600">
                      {zone.meanCorr >= 0 ? '+' : ''}{zone.meanCorr.toFixed(1)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Grid Stats */}
          <div className="border-t border-zinc-800 pt-2">
            <div className="mb-1 text-[10px] uppercase tracking-widest text-zinc-600">Grid Stats</div>
            <div className="space-y-1 text-[10px]">
              <div className="flex items-center justify-between">
                <span className="text-zinc-500">Cells</span>
                <span className="font-mono tabular-nums text-zinc-300">
                  {gridStats.cellsWithData} / {gridStats.totalCells}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-zinc-500">Total Hits</span>
                <span className="font-mono tabular-nums text-zinc-300">
                  {gridStats.totalHits.toLocaleString()}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-zinc-500">Mean Corr.</span>
                <span className="font-mono tabular-nums text-zinc-300">
                  {gridStats.meanCorr >= 0 ? '+' : ''}{gridStats.meanCorr.toFixed(1)}%
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-zinc-500">Max |Corr.|</span>
                <span className="font-mono tabular-nums text-zinc-300">
                  {gridStats.maxAbsCorr.toFixed(1)}%
                </span>
              </div>
            </div>
          </div>

          {/* Correction Range */}
          <div className="border-t border-zinc-800 pt-2">
            <div className="mb-1 text-[10px] uppercase tracking-widest text-zinc-600">Correction Range</div>
            <div className="flex items-center justify-between text-[10px] font-mono tabular-nums">
              <span className="text-blue-400">
                {gridStats.cellsWithData > 0 ? `${gridStats.minCorr >= 0 ? '+' : ''}${gridStats.minCorr.toFixed(1)}%` : MISSING_VALUE}
              </span>
              <span className="text-zinc-600">to</span>
              <span className="text-orange-400">
                {gridStats.cellsWithData > 0 ? `${gridStats.maxCorr >= 0 ? '+' : ''}${gridStats.maxCorr.toFixed(1)}%` : MISSING_VALUE}
              </span>
            </div>
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
  onLiveDataUpdate,
  uncertaintyMap,
  targetMarker,
  className,
}: VEHeatmapPanelProps) {
  const live = useJetDriveLive({
    apiUrl: apiUrl ?? 'http://127.0.0.1:5001/api/jetdrive',
    autoConnect: true,
    pollInterval: 250,  // 250ms polling fallback; SSE is preferred (~20Hz event-driven)
    useSse: true,
    enableDrainedSamples: true,
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
      onLiveDataUpdate={onLiveDataUpdate}
      uncertaintyMap={uncertaintyMap}
      targetMarker={targetMarker}
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
  onLiveDataUpdate,
  uncertaintyMap,
  targetMarker,
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
        onLiveDataUpdate={onLiveDataUpdate}
        uncertaintyMap={uncertaintyMap}
        targetMarker={targetMarker}
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
      onLiveDataUpdate={onLiveDataUpdate}
      uncertaintyMap={uncertaintyMap}
      targetMarker={targetMarker}
      className={className}
    />
  );
}
