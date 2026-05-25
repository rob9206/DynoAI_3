/**
 * ChannelHealthBoard — Operator-facing canonical channel health view.
 *
 * STRICT renderer (see `.cursor/rules/no-physics-in-frontend.mdc`):
 * Every status, value, age, and validity flag rendered here is computed
 * server-side at /hardware/channels/health. This component MUST NOT add
 * unit conversions, plausibility math, or threshold logic. If a status
 * the operator needs is missing, extend the backend payload.
 */

import { useMemo, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  Loader2,
  Radio,
  RefreshCw,
  XCircle,
} from 'lucide-react';
import { cn } from '../../lib/utils';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { useHardwareStatusContext } from '../../hooks/HardwareStatusContext';
import type {
  ChannelHealthRow,
  ChannelSource,
  ChannelStatus,
  ChannelsHealthPayload,
} from '../../hooks/useHardwareStatus';

interface ChannelHealthBoardProps {
  /** Optional className passthrough. The hook source comes from the shared context. */
  className?: string;
}

const STATUS_STYLE: Record<
  ChannelStatus,
  { label: string; pillClass: string; rowClass: string }
> = {
  OK: {
    label: 'OK',
    pillClass:
      'bg-emerald-500/10 text-emerald-300 border-emerald-500/40',
    rowClass: 'border-emerald-500/20',
  },
  STALE: {
    label: 'STALE',
    pillClass: 'bg-amber-500/10 text-amber-200 border-amber-500/40',
    rowClass: 'border-amber-500/30 bg-amber-500/5',
  },
  UNMAPPED: {
    label: 'UNMAPPED',
    pillClass: 'bg-zinc-500/10 text-zinc-300 border-zinc-500/40',
    rowClass: 'border-zinc-700',
  },
  INVALID: {
    label: 'INVALID',
    pillClass: 'bg-red-500/10 text-red-300 border-red-500/40',
    rowClass: 'border-red-500/40 bg-red-500/5',
  },
  NO_SIGNAL: {
    label: 'NO SIGNAL',
    pillClass: 'bg-sky-500/10 text-sky-300 border-sky-500/40',
    rowClass: 'border-sky-500/30',
  },
};

const FILTER_OPTIONS: { value: 'all' | 'attention' | ChannelStatus; label: string }[] = [
  { value: 'attention', label: 'Needs attention' },
  { value: 'all', label: 'All' },
  { value: 'OK', label: 'OK' },
  { value: 'STALE', label: 'Stale' },
  { value: 'INVALID', label: 'Invalid' },
  { value: 'UNMAPPED', label: 'Unmapped' },
  { value: 'NO_SIGNAL', label: 'No signal' },
];

function formatAge(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds)) return '—';
  if (seconds < 1) return `${Math.round(seconds * 1000)} ms`;
  if (seconds < 60) return `${seconds.toFixed(1)} s`;
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds % 60);
  return `${minutes}m ${rest}s`;
}

function formatValue(row: ChannelHealthRow): string {
  if (row.value === null || !Number.isFinite(row.value)) return '—';
  // Display formatting only — server emits the canonical value/units.
  const abs = Math.abs(row.value);
  const decimals = abs >= 1000 ? 0 : abs >= 100 ? 1 : 2;
  return row.value.toFixed(decimals);
}

function formatRate(rate: number | undefined | null): string {
  // Pure renderer: backend ships ``samples_per_second`` already rounded.
  // We only swap "—" for missing values and append the unit label.
  if (rate === undefined || rate === null || !Number.isFinite(rate)) return '—';
  if (rate === 0) return '0 Hz';
  return `${rate.toFixed(1)} Hz`;
}

function formatSource(source: ChannelSource | null): string {
  if (!source) return 'UNMAPPED';
  const provider = source.provider_id ?? '—';
  const channel = source.channel_id ?? '—';
  const raw = source.raw_name ?? 'unknown';
  return `${provider} : ${channel} : ${raw}`;
}

function formatFlag(flag: string): string {
  switch (flag) {
    case 'lc2_pegged':
      return 'LC-2 pegged';
    case 'afr_implausible':
      return 'AFR implausible';
    case 'rpm_zero_at_wot':
      return 'RPM = 0 @ WOT';
    case 'not_finite':
      return 'Non-numeric';
    default:
      return flag;
  }
}

const STATUS_SORT_ORDER: Record<ChannelStatus, number> = {
  INVALID: 0,
  STALE: 1,
  NO_SIGNAL: 2,
  UNMAPPED: 3,
  OK: 4,
};

function sortRows(rows: ChannelHealthRow[]): ChannelHealthRow[] {
  return [...rows].sort((a, b) => {
    if (a.required !== b.required) return a.required ? -1 : 1;
    const orderA = STATUS_SORT_ORDER[a.status] ?? 99;
    const orderB = STATUS_SORT_ORDER[b.status] ?? 99;
    if (orderA !== orderB) return orderA - orderB;
    return a.canonical_name.localeCompare(b.canonical_name);
  });
}

export function ChannelHealthBoard({
  className,
}: ChannelHealthBoardProps) {
  const { status, isFetching, error, refresh } = useHardwareStatusContext();
  const payload: ChannelsHealthPayload | null = status?.channels ?? null;
  const [filter, setFilter] = useState<'all' | 'attention' | ChannelStatus>('attention');

  const sortedRows = useMemo(
    () => (payload ? sortRows(payload.channels) : []),
    [payload],
  );

  const filteredRows = useMemo(() => {
    if (!payload) return [];
    if (filter === 'all') return sortedRows;
    if (filter === 'attention') {
      return sortedRows.filter((row) => row.status !== 'OK');
    }
    return sortedRows.filter((row) => row.status === filter);
  }, [payload, sortedRows, filter]);

  const summaryColor = payload?.all_required_ok
    ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-200'
    : payload?.summary.state === 'invalid'
      ? 'border-red-500/40 bg-red-500/10 text-red-200'
      : payload?.summary.state === 'stale'
        ? 'border-amber-500/40 bg-amber-500/10 text-amber-100'
        : 'border-zinc-700 bg-zinc-900/40 text-zinc-200';

  const SummaryIcon = payload?.all_required_ok
    ? CheckCircle2
    : payload?.summary.state === 'invalid'
      ? XCircle
      : payload?.summary.state === 'stale'
        ? AlertTriangle
        : Radio;

  return (
    <div className={cn('flex flex-col gap-3 text-sm', className)}>
      {/* Header / summary banner */}
      <div
        className={cn(
          'flex items-start gap-3 rounded-md border px-3 py-2',
          summaryColor,
        )}
      >
        <SummaryIcon className="mt-0.5 h-4 w-4 shrink-0" />
        <div className="flex-1">
          <div className="flex items-center justify-between gap-2">
            <span className="font-semibold uppercase tracking-wider text-xs">
              {payload
                ? payload.all_required_ok
                  ? 'All channels healthy'
                  : payload.summary.state.replace(/_/g, ' ')
                : 'Loading…'}
            </span>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-6 w-6 text-current"
              onClick={refresh}
              aria-label="Refresh channel health"
            >
              {isFetching ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <RefreshCw className="h-3.5 w-3.5" />
              )}
            </Button>
          </div>
          <div className="text-xs opacity-90">
            {payload?.summary.message ?? 'Waiting for health snapshot.'}
          </div>
          {payload?.provider?.name && (
            <div className="mt-1 text-[11px] opacity-70">
              Provider {payload.provider.provider_id ?? '?'} · {payload.provider.name}
              {payload.provider.host ? ` (${payload.provider.host})` : ''}
            </div>
          )}
          {error && (
            <div className="mt-1 text-[11px] text-red-300">
              {error}
            </div>
          )}
        </div>
      </div>

      {/* Counters */}
      {payload && (
        <div className="grid grid-cols-5 gap-1 text-[11px]">
          {(Object.keys(STATUS_STYLE) as ChannelStatus[]).map((key) => (
            <button
              key={key}
              type="button"
              onClick={() => setFilter(key)}
              className={cn(
                'flex flex-col items-center justify-center rounded border px-1 py-1 transition-colors',
                STATUS_STYLE[key].pillClass,
                filter === key && 'ring-1 ring-current',
              )}
            >
              <span className="text-base font-semibold leading-tight">
                {payload.summary.counts[key] ?? 0}
              </span>
              <span className="opacity-80">{STATUS_STYLE[key].label}</span>
            </button>
          ))}
        </div>
      )}

      {/* Filter selector */}
      <div className="flex flex-wrap items-center gap-1">
        {FILTER_OPTIONS.map((option) => (
          <Button
            key={option.value}
            type="button"
            variant={filter === option.value ? 'default' : 'ghost'}
            size="sm"
            className={cn(
              'h-7 px-2 text-[11px]',
              filter === option.value ? '' : 'text-zinc-300',
            )}
            onClick={() => setFilter(option.value)}
          >
            {option.label}
          </Button>
        ))}
      </div>

      {/* Channel rows */}
      <div className="flex flex-col gap-1.5">
        {payload === null && (
          <div className="rounded border border-zinc-800 bg-zinc-900/40 px-3 py-4 text-center text-xs text-zinc-500">
            Loading channel health…
          </div>
        )}
        {payload && filteredRows.length === 0 && (
          <div className="rounded border border-zinc-800 bg-zinc-900/40 px-3 py-4 text-center text-xs text-zinc-500">
            No channels match the current filter.
          </div>
        )}
        {filteredRows.map((row) => {
          const style = STATUS_STYLE[row.status];
          const expectedUnits = row.units ?? row.expected_units;
          return (
            <div
              key={row.canonical_name}
              className={cn(
                'rounded border px-2.5 py-2 transition-colors',
                style.rowClass,
              )}
            >
              <div className="flex items-center gap-2">
                <span className="flex-1 truncate font-mono text-xs uppercase tracking-wider text-zinc-100">
                  {row.canonical_name}
                </span>
                {row.required && (
                  <Badge
                    variant="outline"
                    className="border-zinc-600 text-[10px] uppercase text-zinc-300"
                  >
                    Required
                  </Badge>
                )}
                <Badge
                  variant="outline"
                  className={cn('border text-[10px] uppercase', style.pillClass)}
                >
                  {style.label}
                </Badge>
              </div>
              <div className="mt-1 grid grid-cols-4 gap-2 text-[11px] text-zinc-400">
                <div className="flex flex-col">
                  <span className="opacity-60">Value</span>
                  <span className="font-mono text-sm tabular-nums text-zinc-100">
                    {formatValue(row)}{' '}
                    <span className="text-[10px] text-zinc-500">{expectedUnits}</span>
                  </span>
                </div>
                <div className="flex flex-col">
                  <span className="opacity-60">Age</span>
                  <span
                    className={cn(
                      'font-mono text-sm tabular-nums',
                      row.status === 'STALE'
                        ? 'text-amber-300'
                        : row.status === 'OK'
                          ? 'text-emerald-300'
                          : 'text-zinc-400',
                    )}
                  >
                    {formatAge(row.age_seconds)}
                  </span>
                </div>
                <div className="flex flex-col">
                  <span className="opacity-60">Rate</span>
                  <span className="font-mono text-sm tabular-nums text-zinc-200">
                    {formatRate(row.samples_per_second)}
                    {row.lc2_peg_count_60s ? (
                      <span className="ml-1 text-[10px] text-red-300">
                        peg×{row.lc2_peg_count_60s}/60s
                      </span>
                    ) : null}
                  </span>
                </div>
                <div className="flex flex-col">
                  <span className="opacity-60">Source</span>
                  <span className="truncate font-mono text-[11px] text-zinc-300">
                    {formatSource(row.source)}
                  </span>
                </div>
              </div>
              {(row.flags.length > 0 || row.reasons.length > 0) && (
                <div className="mt-1.5 flex flex-wrap items-start gap-1.5 text-[11px]">
                  {row.flags.map((flag) => (
                    <Badge
                      key={flag}
                      variant="outline"
                      className="border-red-500/40 bg-red-500/10 text-[10px] uppercase text-red-200"
                    >
                      {formatFlag(flag)}
                    </Badge>
                  ))}
                  {row.reasons.map((reason, idx) => (
                    <span
                      key={`${row.canonical_name}-reason-${idx}`}
                      className="flex items-center gap-1 text-zinc-400"
                    >
                      <HelpCircle className="h-3 w-3 opacity-60" />
                      {reason}
                    </span>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default ChannelHealthBoard;
