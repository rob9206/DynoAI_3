import { useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { cn } from '../../lib/utils';
import { useThrottle } from '../../hooks/useDebounce';
import {
  useJetDriveLive,
  type JetDriveChannel,
  type UseJetDriveLiveReturn,
} from '../../hooks/useJetDriveLive';
import { AudioCapturePanel } from './AudioCapturePanel';
import { DEFAULT_AFR_TARGETS } from './AFRTargetTable';
import { Sparkline } from './Sparkline';
import type { KnockEvent } from '../../hooks/useAudioCapture';

const MISSING_VALUE = '—';

interface TelemetryStripProps {
  apiUrl?: string;
  live?: UseJetDriveLiveReturn;
  afrTargets?: Record<number, number>;
  className?: string;
}

interface ChannelMatch {
  name: string;
  value: number;
  units?: string;
  source_name?: string;
}

function getChannel(channels: Record<string, JetDriveChannel>, name: string): ChannelMatch | null {
  const channel = channels[name];
  if (!channel || !Number.isFinite(channel.value)) return null;
  return {
    name,
    value: channel.value,
    units: channel.units,
    source_name: channel.source_name,
  };
}

function formatNumber(value: number | null, decimals: number): string {
  if (value === null || !Number.isFinite(value)) return MISSING_VALUE;
  return value.toFixed(decimals);
}

function formatRpm(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return MISSING_VALUE;
  return new Intl.NumberFormat('en-US').format(Math.round(value));
}

function getAfrTarget(mapKpa: number | null, targets: Record<number, number>): number | null {
  if (mapKpa === null || !Number.isFinite(mapKpa)) return null;
  const bins = Object.keys(targets).map(Number).sort((a, b) => a - b);
  if (bins.length === 0) return null;
  let closest = bins[0];
  for (const bin of bins) {
    if (Math.abs(bin - mapKpa) < Math.abs(closest - mapKpa)) {
      closest = bin;
    }
  }
  return targets[closest] ?? null;
}

function getAfrState(value: number | null, target: number | null) {
  if (value === null || target === null) {
    return {
      valueClass: 'text-zinc-600',
      label: MISSING_VALUE,
    };
  }

  const diff = value - target;
  const absDiff = Math.abs(diff);
  const valueClass =
    absDiff <= 0.3 ? 'text-green-400' : absDiff <= 0.7 ? 'text-amber-400' : 'text-red-400';
  const label = absDiff <= 0.3 ? 'on-tgt' : diff > 0 ? 'lean' : 'rich';

  return { valueClass, label };
}

/* ---------------------------------------------------------------------------
 * InstrumentCell — MoTeC-style flat instrument cell
 *
 * No rounded corners, no card border, no bar element, no transitions on
 * container. Lives inside a CSS Grid row separated by border-r dividers.
 * ------------------------------------------------------------------------- */
function InstrumentCell({
  label,
  value,
  valueClass,
  size = 'hero',
  units,
  statusLeft,
  statusRight,
  labelClass,
  dot,
  sparkline,
}: {
  label: string;
  value: string;
  valueClass?: string;
  size?: 'hero' | 'compact';
  units?: string;
  statusLeft?: string;
  statusRight?: string;
  labelClass?: string;
  dot?: 'live' | 'warning' | 'off';
  sparkline?: ReactNode;
}) {
  const isHero = size === 'hero';

  return (
    <div className={cn('relative', isHero ? 'px-4 py-2' : 'px-3 py-2')}>
      {/* Label row */}
      <div className="flex items-center justify-between">
        <span
          className={cn(
            'text-[10px] uppercase tracking-widest',
            labelClass ?? 'text-zinc-600',
          )}
        >
          {label}
        </span>
        {dot && (
          <span
            className={cn(
              'h-1.5 w-1.5 rounded-full',
              dot === 'live' && 'bg-green-500',
              dot === 'warning' && 'bg-amber-500',
              dot === 'off' && 'bg-zinc-700',
            )}
          />
        )}
      </div>

      {/* Value + sparkline */}
      <div className="flex items-end gap-3">
        <div
          className={cn(
            'font-mono font-bold tabular-nums',
            isHero ? 'mt-1 text-3xl' : 'mt-0.5 text-base',
            value === MISSING_VALUE ? 'text-zinc-600' : (valueClass ?? 'text-zinc-50'),
          )}
        >
          {value}
          {units && !isHero ? (
            <span className="ml-1 text-xs font-normal text-zinc-600">{units}</span>
          ) : null}
        </div>
        {sparkline && <div className="mb-1">{sparkline}</div>}
      </div>

      {/* Status footer */}
      {(statusLeft || statusRight) && (
        <div className="mt-0.5 flex items-center justify-between text-xs text-zinc-500">
          <span>{statusLeft ?? ''}</span>
          <span>{statusRight ?? ''}</span>
        </div>
      )}
    </div>
  );
}

function TelemetryStripContent({
  live,
  afrTargets,
  className,
}: {
  live: UseJetDriveLiveReturn;
  afrTargets: Record<number, number>;
  className?: string;
}) {
  const [audioExpanded, setAudioExpanded] = useState(false);
  const [audioRecording, setAudioRecording] = useState(false);
  const [lastKnock, setLastKnock] = useState<KnockEvent | null>(null);
  const [lastKnockAt, setLastKnockAt] = useState<number | null>(null);

  const rpmChannel = useMemo(
    () => getChannel(live.channels, 'Engine RPM') ?? getChannel(live.channels, 'RPM'),
    [live.channels],
  );
  const afrFrontChannel = useMemo(
    () => getChannel(live.channels, 'AFR Front'),
    [live.channels],
  );
  const afrRearChannel = useMemo(
    () => getChannel(live.channels, 'AFR Rear'),
    [live.channels],
  );
  const mapChannel = useMemo(
    () => getChannel(live.channels, 'MAP kPa'),
    [live.channels],
  );
  const tpsChannel = useMemo(
    () => getChannel(live.channels, 'TPS'),
    [live.channels],
  );
  const iatChannel = useMemo(
    () => getChannel(live.channels, 'IAT'),
    [live.channels],
  );
  const ectChannel = useMemo(
    () => getChannel(live.channels, 'ECT'),
    [live.channels],
  );
  const knockChannel = useMemo(
    () => getChannel(live.channels, 'Knock'),
    [live.channels],
  );

  const rawValues = useMemo(
    () => ({
      rpm: rpmChannel?.value ?? null,
      afrFront: afrFrontChannel?.value ?? null,
      afrRear: afrRearChannel?.value ?? null,
      map: mapChannel?.value ?? null,
      tps: tpsChannel?.value ?? null,
      iat: iatChannel?.value ?? null,
      ect: ectChannel?.value ?? null,
      knock: knockChannel?.value ?? null,
    }),
    [
      rpmChannel?.value,
      afrFrontChannel?.value,
      afrRearChannel?.value,
      mapChannel?.value,
      tpsChannel?.value,
      iatChannel?.value,
      iatChannel?.units,
      ectChannel?.value,
      ectChannel?.units,
      knockChannel?.value,
    ],
  );

  const values = useThrottle(rawValues, 100);
  // Moderate throttle for AFR to reduce jitter while staying responsive
  const afrValues = useThrottle({ afrFront: rawValues.afrFront, afrRear: rawValues.afrRear }, 250);
  const rpmValue = values.rpm;
  const mapValue = values.map;
  const afrTarget = getAfrTarget(mapValue, afrTargets);
  const afrFrontState = getAfrState(afrValues.afrFront, afrTarget);
  const afrRearState = getAfrState(afrValues.afrRear, afrTarget);
  const afrFrontSource = afrFrontChannel?.source_name ?? null;
  const afrRearSource = afrRearChannel?.source_name ?? null;
  const afrFrontStatusLeft = afrFrontSource
    ? `${afrFrontState.label} · src: ${afrFrontSource}`
    : afrFrontState.label;
  const afrRearStatusLeft = afrRearSource
    ? `${afrRearState.label} · src: ${afrRearSource}`
    : afrRearState.label;

  const rpmHistory = rpmChannel?.name ? live.history[rpmChannel.name] : null;
  const afrFrontHistory = afrFrontChannel?.name ? live.history[afrFrontChannel.name] : null;
  const afrRearHistory = afrRearChannel?.name ? live.history[afrRearChannel.name] : null;

  const rpmStats = useMemo(() => {
    if (!rpmHistory || rpmHistory.length === 0) return null;
    let min = rpmHistory[0]?.value ?? 0;
    let max = rpmHistory[0]?.value ?? 0;
    for (const point of rpmHistory) {
      min = Math.min(min, point.value);
      max = Math.max(max, point.value);
    }
    return { min, max };
  }, [rpmHistory]);

  // Extract last N values for sparklines (take the 20 most recent points)
  const rpmSparkData = useMemo(
    () => rpmHistory?.slice(-20).map((p) => p.value) ?? [],
    [rpmHistory],
  );
  const afrFrontSparkData = useMemo(
    () => afrFrontHistory?.slice(-20).map((p) => p.value) ?? [],
    [afrFrontHistory],
  );
  const afrRearSparkData = useMemo(
    () => afrRearHistory?.slice(-20).map((p) => p.value) ?? [],
    [afrRearHistory],
  );

  const showKnock = lastKnockAt !== null && Date.now() - lastKnockAt < 5000;
  const knockValue =
    knockChannel?.value ?? (showKnock ? lastKnock?.intensity ?? null : audioRecording ? 0 : null);
  const knockWarning = knockValue !== null && knockValue > 0.5;

  return (
    <div className={cn('w-full bg-zinc-900 border-b border-zinc-800 gpu-accelerated', className)}>
      {/* Disconnected banner — sits above the instrument panel */}
      {!live.isConnected && (
        <div className="border-b border-zinc-800 bg-zinc-950 px-4 py-1.5 text-xs text-zinc-400">
          Connect hardware to see live data &rarr; [HW Setup]
        </div>
      )}

      {/* ── HERO ROW: RPM | AFR FRONT | AFR REAR ─────────────────────── */}
      <div className="grid grid-cols-3">
        {/* RPM */}
        <div className="border-r border-zinc-800">
          <InstrumentCell
            label="RPM"
            value={formatRpm(rpmValue)}
            valueClass={rpmValue === null ? 'text-zinc-600' : 'text-zinc-50'}
            dot={live.isConnected ? 'live' : 'off'}
            statusLeft={rpmStats ? `\u2191${formatRpm(rpmStats.max)}` : '\u2191 \u2014'}
            statusRight={rpmStats ? `\u2193${formatRpm(rpmStats.min)}` : '\u2193 \u2014'}
            sparkline={
              rpmSparkData.length >= 2
                ? <Sparkline data={rpmSparkData} color="rgb(244, 244, 245)" width={50} height={24} />
                : undefined
            }
          />
        </div>

        {/* AFR FRONT */}
        <div className="border-r border-zinc-800">
          <InstrumentCell
            label="AFR FRONT"
            value={formatNumber(afrValues.afrFront, 1)}
            valueClass={afrFrontState.valueClass}
            dot={afrValues.afrFront !== null ? 'live' : 'off'}
            statusLeft={afrFrontStatusLeft}
            statusRight={afrTarget !== null ? `tgt: ${afrTarget.toFixed(1)}` : 'tgt: \u2014'}
            sparkline={
              afrFrontSparkData.length >= 2
                ? <Sparkline data={afrFrontSparkData} color="rgb(34, 197, 94)" width={50} height={24} />
                : undefined
            }
          />
        </div>

        {/* AFR REAR */}
        <div>
          <InstrumentCell
            label="AFR REAR"
            value={formatNumber(afrValues.afrRear, 1)}
            valueClass={afrRearState.valueClass}
            dot={afrValues.afrRear !== null ? 'live' : 'off'}
            statusLeft={afrRearStatusLeft}
            statusRight={afrTarget !== null ? `tgt: ${afrTarget.toFixed(1)}` : 'tgt: \u2014'}
            sparkline={
              afrRearSparkData.length >= 2
                ? <Sparkline data={afrRearSparkData} color="rgb(239, 68, 68)" width={50} height={24} />
                : undefined
            }
          />
        </div>
      </div>

      {/* ── COMPACT ROW: MAP | TPS | IAT | ECT | KNOCK | AUDIO ───────── */}
      <div
        className="grid border-t border-zinc-800"
        style={{ gridTemplateColumns: 'repeat(5, minmax(0, 1fr)) 1.5fr' }}
      >
        <div className="border-r border-zinc-800">
          <InstrumentCell
            label="MAP"
            value={formatNumber(values.map, 0)}
            size="compact"
            units="kPa"
          />
        </div>
        <div className="border-r border-zinc-800">
          <InstrumentCell
            label="TPS"
            value={formatNumber(values.tps, 1)}
            size="compact"
            units="%"
          />
        </div>
        <div className="border-r border-zinc-800">
          <InstrumentCell
            label="IAT"
            value={formatNumber(values.iat, 0)}
            size="compact"
            units={'\u00b0F'}
          />
        </div>
        <div className="border-r border-zinc-800">
          <InstrumentCell
            label="ECT"
            value={formatNumber(values.ect, 0)}
            size="compact"
            units={'\u00b0F'}
            labelClass={values.ect === null ? 'text-amber-500' : undefined}
          />
        </div>
        <div className="border-r border-zinc-800">
          <InstrumentCell
            label="KNOCK"
            value={formatNumber(knockValue, 1)}
            size="compact"
            valueClass={knockWarning ? 'text-red-500' : undefined}
          />
        </div>

        {/* Audio cell — inline status + expand toggle */}
        <div className="flex items-center gap-2 px-3 py-2">
          <div className="flex flex-col gap-0.5">
            <span className="text-[10px] uppercase tracking-widest text-zinc-600">Audio</span>
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  'h-2 w-2 rounded-full',
                  audioRecording ? 'bg-red-500 animate-pulse' : 'bg-zinc-600',
                )}
              />
              <span className="font-mono text-base tabular-nums text-zinc-300">
                {audioRecording ? 'Rec' : 'Idle'}
              </span>
            </div>
          </div>
          <button
            type="button"
            className="ml-auto flex items-center gap-1 text-xs text-zinc-400 hover:text-zinc-200"
            onClick={() => setAudioExpanded((prev) => !prev)}
          >
            {audioExpanded ? 'Hide' : 'Show'}
            {audioExpanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          </button>
        </div>
      </div>

      {/* Audio expansion panel */}
      <AnimatePresence initial={false}>
        {audioExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className="overflow-hidden border-t border-zinc-800"
          >
            <div className="px-4 py-4">
              <AudioCapturePanel
                isDynoCapturing={live.isCapturing}
                currentRpm={rpmValue ?? 0}
                onRecordingStart={() => setAudioRecording(true)}
                onRecordingStop={() => setAudioRecording(false)}
                onKnockDetected={(event) => {
                  setLastKnock(event);
                  setLastKnockAt(Date.now());
                }}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function TelemetryStripWithLive({ apiUrl, afrTargets, className }: TelemetryStripProps) {
  const live = useJetDriveLive({
    apiUrl: apiUrl ?? 'http://127.0.0.1:5001/api/jetdrive',
    autoConnect: true,
    pollInterval: 800,
    useSse: true,
  });

  return (
    <TelemetryStripContent
      live={live}
      afrTargets={afrTargets ?? DEFAULT_AFR_TARGETS}
      className={className}
    />
  );
}

export function TelemetryStrip({ live, apiUrl, afrTargets, className }: TelemetryStripProps) {
  if (live) {
    return (
      <TelemetryStripContent
        live={live}
        afrTargets={afrTargets ?? DEFAULT_AFR_TARGETS}
        className={className}
      />
    );
  }

  return <TelemetryStripWithLive apiUrl={apiUrl} afrTargets={afrTargets} className={className} />;
}
