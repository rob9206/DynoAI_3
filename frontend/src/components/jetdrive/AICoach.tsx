import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { toast } from '@/lib/toast';
import { cn } from '@/lib/utils';
import { Button } from '../ui/button';
import { Progress } from '../ui/progress';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '../ui/sheet';
import { useV3Session } from '../../hooks/useV3Session';
import { useApplyRollback } from '../../hooks/useApplyRollback';
import api, { handleApiError } from '../../lib/api';
import { getV3Status, type CreateSessionPayload, type HardwareConfig, type ConvergenceStatus } from '../../api/v3Session';
import { TuneImport, type TuneImportResult } from './TuneImport';
import { AFRTargetTable, DEFAULT_AFR_TARGETS } from './AFRTargetTable';
import { calculateCoverage, getCoverageGrade } from '../../utils/veApply/coverageCalculator';

const MISSING_VALUE = '—';
const JETDRIVE_API_BASE = `${import.meta.env.VITE_API_URL || 'http://localhost:5001'}/api/jetdrive`;
const V3_MATERIALIZE_FALLBACK_ENABLED = import.meta.env.VITE_V3_MATERIALIZE_FALLBACK !== 'false';

const ENGINE_FAMILIES = [
  { value: 'm8_107', label: 'M8 107 (Air-Cooled)' },
  { value: 'm8_114', label: 'M8 114 (Air-Cooled)' },
  { value: 'm8_117', label: 'M8 117 (Air-Cooled)' },
  { value: 'm8_131', label: 'M8 131 (Oil-Cooled)' },
  { value: 'tc_88', label: 'TC 88 (Air-Cooled)' },
  { value: 'tc_96', label: 'TC 96 (Air-Cooled)' },
  { value: 'tc_103', label: 'TC 103 (Air-Cooled)' },
  { value: 'tc_110', label: 'TC 110 (Air-Cooled)' },
  { value: 'revmax_1250', label: 'RevMax 1250 (Liquid)' },
  { value: 'evo_1200', label: 'Evo 1200 (Air-Cooled)' },
] as const;

const CAM_OPTIONS = [
  'stock',
  "s&s_475",
  "s&s_510",
  "s&s_585",
  'feuling_574',
  'wood_tw777',
  'other',
] as const;

const EXHAUST_OPTIONS = ['stock', 'slip_on', '2into1', 'open'] as const;
const AIR_CLEANER_OPTIONS = ['stock', 'high_flow', 'velocity_stack', 'other'] as const;

type Cylinder = 'front' | 'rear';

interface AICoachProps {
  activeCylinder?: Cylinder;
  onCylinderChange?: (cylinder: Cylinder) => void;
  afrTargets?: Record<number, number>;
  onAfrTargetsChange?: (targets: Record<number, number>) => void;
  hitData?: {
    frontHits: number[][];
    rearHits: number[][];
    rpmBins: number[];
    mapBins: number[];
  } | null;
  balanceDelta?: number;
  runId?: string;
  onRunIdChange?: (runId: string | undefined) => void;
  onTargetChange?: (target: { rpm: number; map: number; label?: string } | null) => void;
  onExport?: () => void;
  className?: string;
}

function formatTarget(value: number | undefined): string {
  if (!value || !Number.isFinite(value)) return MISSING_VALUE;
  return value.toFixed(1);
}

export function AICoach({
  activeCylinder,
  onCylinderChange,
  afrTargets,
  onAfrTargetsChange,
  hitData,
  balanceDelta,
  runId,
  onRunIdChange,
  onTargetChange,
  onExport,
  className,
}: AICoachProps) {
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [sessionRunId, setSessionRunId] = useState<string | undefined>();
  const [localImportedTune, setLocalImportedTune] = useState<TuneImportResult | null>(null);
  const [showImportSheet, setShowImportSheet] = useState(false);
  const [showConfigSheet, setShowConfigSheet] = useState(false);
  const [showTargetsSheet, setShowTargetsSheet] = useState(false);
  const [localTargets, setLocalTargets] = useState<Record<number, number>>(
    afrTargets ?? DEFAULT_AFR_TARGETS,
  );
  const [localCylinder, setLocalCylinder] = useState<Cylinder>('front');
  const [showFullAnalysis, setShowFullAnalysis] = useState(false);
  const [lastAnalyzedAt, setLastAnalyzedAt] = useState<string | null>(null);
  const [lastRunReadyAt, setLastRunReadyAt] = useState<string | null>(null);
  const lastTargetKeyRef = useRef<string | null>(null);

  useEffect(() => {
    if (afrTargets) {
      setLocalTargets(afrTargets);
    }
  }, [afrTargets]);

  const [config, setConfig] = useState<HardwareConfig>({
    engine_family: 'm8_114',
    displacement_ci: 114,
    cam_spec: 'stock',
    exhaust_type: 'stock',
    air_cleaner: 'stock',
  });

  // Only use a true analysis run_id for apply/rollback; v3 session_id is not valid here.
  const effectiveRunId = runId ?? sessionRunId;
  const v3 = useV3Session(sessionId);
  const applyRollback = useApplyRollback({
    runId: effectiveRunId ?? 'inactive',
    initialCanApply: true,
    initialCanRollback: false,
  });

  const v3StatusQuery = useQuery({
    queryKey: ['v3', 'status'],
    queryFn: async () => {
      try {
        return await getV3Status();
      } catch {
        return { available: false as const, message: 'AI Coach is not available on this server' };
      }
    },
    enabled: !sessionId,
    staleTime: 60_000,
  });

  const handleStartSession = useCallback(async () => {
    try {
      const payload: CreateSessionPayload = { ...config };
      if (localImportedTune?.veFront?.values?.length) {
        payload.initial_ve_table = localImportedTune.veFront.values;
        payload.rpm_bins = localImportedTune.rpmBins;
        payload.map_bins = localImportedTune.mapBins;
      }

      const result = await v3.startSession(payload);
      setSessionId(result.session_id);
      const derivedRunId = (result as { run_id?: string }).run_id;
      setSessionRunId(derivedRunId);
      setLastAnalyzedAt(null);
      setLastRunReadyAt(null);
      onRunIdChange?.(derivedRunId);
      const matchLabel = result.template_match
        ? `Template ${(result.template_match.similarity_score * 100).toFixed(0)}%`
        : 'No template match';
      toast.success(`Session started — ${matchLabel}`);
    } catch (error) {
      toast.error('Failed to start AI Coach session', {
        description: handleApiError(error),
      });
    }
  }, [config, localImportedTune, onRunIdChange, v3]);

  useEffect(() => {
    if (!onTargetChange) return;
    if (!v3.nextPull) {
      if (lastTargetKeyRef.current !== 'none') {
        lastTargetKeyRef.current = 'none';
        onTargetChange(null);
      }
      return;
    }
    const label = v3.nextPull.pull_mode === 'steady_state' ? 'Steady-state' : 'WOT';
    const rpm = Math.round(v3.nextPull.rpm);
    const map = Math.round(v3.nextPull.map_kpa);
    const key = `${rpm}|${map}|${label}`;
    if (lastTargetKeyRef.current === key) return;
    lastTargetKeyRef.current = key;
    onTargetChange({ rpm, map, label });
  }, [onTargetChange, v3.nextPull]);

  const handleTargetsChange = useCallback(
    (targets: Record<number, number>) => {
      setLocalTargets(targets);
      onAfrTargetsChange?.(targets);
    },
    [onAfrTargetsChange],
  );

  const handleApplyCorrections = useCallback(async () => {
    if (applyRollback.status !== 'idle' || !applyRollback.canApply) return;
    if (!sessionId) {
      toast.info('Start AI session before applying corrections.');
      return;
    }

    const targetRunId =
      effectiveRunId ??
      `dyno_${new Date().toISOString().slice(0, 10).replace(/-/g, '')}_${Date.now().toString(36)}`;

    try {
      let resolvedRunId: string | null = null;
      try {
        const materialized = await v3.materializeLatestRun();
        resolvedRunId = materialized.run_id;
      } catch (materializeError) {
        const materializeErrorMessage = handleApiError(materializeError);

        // If no cached correction surface exists yet, run one realistic v3 update
        // and retry materialize before dropping to legacy fallback.
        if (
          materializeErrorMessage.toLowerCase().includes('run analyze/update first') ||
          materializeErrorMessage.toLowerCase().includes('no cached v3 corrections')
        ) {
          try {
            await v3.simulate({ mode: 'realistic' });
            v3.refreshSessionData();
            setLastAnalyzedAt(new Date().toISOString());
            const retried = await v3.materializeLatestRun();
            resolvedRunId = retried.run_id;
          } catch {
            // Continue to fallback path below when retry fails.
          }
        }

        if (resolvedRunId) {
          if (!effectiveRunId || resolvedRunId !== effectiveRunId) {
            setSessionRunId(resolvedRunId);
            onRunIdChange?.(resolvedRunId);
          }
          setLastRunReadyAt(new Date().toISOString());
          await applyRollback.apply(resolvedRunId);
          return;
        }

        if (!V3_MATERIALIZE_FALLBACK_ENABLED) {
          throw materializeError;
        }

        const analyzeWithMode = async (mode: 'simulator_pull' | 'simulate') => {
          const analyzeRes = await api.post(`${JETDRIVE_API_BASE}/analyze`, {
            run_id: targetRunId,
            mode,
            afr_targets: localTargets,
          });
          return analyzeRes.data as {
            success?: boolean;
            run_id?: string;
            error?: string;
          };
        };

        let analyzeData: { success?: boolean; run_id?: string; error?: string } | null = null;
        let analyzeErr: unknown = null;
        try {
          analyzeData = await analyzeWithMode('simulator_pull');
        } catch (error) {
          analyzeErr = error;
        }
        if (!analyzeData?.success && !analyzeData?.run_id) {
          try {
            analyzeData = await analyzeWithMode('simulate');
            analyzeErr = null;
          } catch (error) {
            analyzeErr = error;
          }
        }
        if (!analyzeData?.run_id) {
          const fallbackError =
            analyzeData?.error ||
            (analyzeErr ? handleApiError(analyzeErr) : undefined) ||
            materializeErrorMessage;
          throw new Error(fallbackError || 'Failed to materialize run for apply.');
        }
        resolvedRunId = analyzeData.run_id;
        toast.info('Using temporary legacy analyze fallback for this apply.');
      }

      if (!resolvedRunId) {
        throw new Error('Failed to materialize run for apply.');
      }

      if (!effectiveRunId || resolvedRunId !== effectiveRunId) {
        setSessionRunId(resolvedRunId);
        onRunIdChange?.(resolvedRunId);
      }
      setLastRunReadyAt(new Date().toISOString());

      await applyRollback.apply(resolvedRunId);
    } catch (error) {
      toast.error('Failed to prepare corrections', {
        description: handleApiError(error),
      });
    }
  }, [applyRollback, effectiveRunId, localTargets, onRunIdChange, sessionId, v3]);

  useEffect(() => {
    const handler = (event: Event) => {
      const detail = (event as CustomEvent<{ action?: string }>).detail;
      if (!detail?.action) return;
      if (detail.action === 'rollback') {
        if (effectiveRunId && applyRollback.canRollback && applyRollback.status === 'idle') {
          const confirmed = window.confirm('Rollback VE corrections? This will revert applied changes.');
          if (confirmed) {
            void applyRollback.rollback();
          }
        }
      }
      if (detail.action === 'export') {
        onExport?.();
      }
    };

    window.addEventListener('dynoai:shortcut', handler);
    return () => window.removeEventListener('dynoai:shortcut', handler);
  }, [applyRollback, effectiveRunId, onExport]);

  useEffect(() => {
    const handler = (_event: Event) => {
      if (!sessionId) {
        toast.info('Start AI session before triggering pull analysis.');
        return;
      }
      if (v3.sessionPhase === 'idle') {
        toast.info('AI session is not ready yet.');
        return;
      }
      if (v3.isSimulating) return;

      void v3
        .simulate({ mode: 'realistic' })
        .then(async () => {
          // If simulating, we need to ingest the result
          // In a real scenario, this data comes from the hardware/log
          // For now, we'll auto-ingest the simulation result to close the loop

          // Force refresh to get latest state
          await v3.refreshSessionData();
          setLastAnalyzedAt(new Date().toISOString());
          toast.success('AI Coach updated from simulator pull.');
        })
        .catch((error) => {
          toast.error('AI Coach update failed', {
            description: error instanceof Error ? error.message : 'Unknown error',
          });
        });
    };

    window.addEventListener('dynoai:simulator-pull', handler);
    return () => window.removeEventListener('dynoai:simulator-pull', handler);
  }, [sessionId, v3]);

  const totalSteps = v3.initResult?.estimated_pulls
    ? v3.initResult.estimated_pulls
    : v3.convergence
      ? v3.pullCount + v3.convergence.estimated_pulls_remaining
      : null;
  const currentStep = totalSteps ? Math.min(v3.pullCount + 1, totalSteps) : null;
  const stepProgress = totalSteps ? Math.round((currentStep! / totalSteps) * 100) : 0;

  // Calculate zone-weighted coverage from hit counts
  const frontCoverageReport = useMemo(() => {
    if (!hitData) return null;
    return calculateCoverage(hitData.frontHits, hitData.rpmBins, hitData.mapBins);
  }, [hitData]);

  const rearCoverageReport = useMemo(() => {
    if (!hitData) return null;
    return calculateCoverage(hitData.rearHits, hitData.rpmBins, hitData.mapBins);
  }, [hitData]);

  // Calculate combined (minimum of front/rear) coverage
  const overallCoverageReport = useMemo(() => {
    if (!hitData) return null;
    const combinedHits = hitData.frontHits.map((row, rpmIdx) =>
      row.map((frontHit, mapIdx) => {
        const rearHit = hitData.rearHits[rpmIdx]?.[mapIdx] ?? 0;
        return Math.min(frontHit, rearHit);
      })
    );
    return calculateCoverage(combinedHits, hitData.rpmBins, hitData.mapBins);
  }, [hitData]);

  const overallCoverage = overallCoverageReport?.weightedCoveragePct ?? 0;
  const frontCoverage = frontCoverageReport?.weightedCoveragePct ?? 0;
  const rearCoverage = rearCoverageReport?.weightedCoveragePct ?? 0;
  const coverageGrade = overallCoverageReport ? getCoverageGrade(overallCoverage) : null;

  const guidanceTitle = v3.nextPull
    ? v3.nextPull.pull_mode === 'steady_state'
      ? 'Ready for steady-state pull'
      : 'Ready for WOT pull'
    : 'Awaiting pull recommendation';
  const guidanceDetail = v3.nextPull
    ? `${Math.round(v3.nextPull.rpm)} RPM @ ${Math.round(v3.nextPull.map_kpa)} kPa`
    : 'Start a session to generate AI guidance';

  const planItems = v3.initResult?.initial_plan?.slice(0, 3) ?? [];

  const cruiseTarget = formatTarget(localTargets[60]);
  const wotTarget = formatTarget(localTargets[80]);
  const balanceText =
    balanceDelta === undefined
      ? MISSING_VALUE
      : `${balanceDelta >= 0 ? '+' : ''}${balanceDelta.toFixed(1)}%`;
  const cylinder = activeCylinder ?? localCylinder;
  const formattedLastAnalyzedAt = lastAnalyzedAt
    ? new Date(lastAnalyzedAt).toLocaleTimeString()
    : MISSING_VALUE;
  const formattedRunReadyAt = lastRunReadyAt
    ? new Date(lastRunReadyAt).toLocaleTimeString()
    : MISSING_VALUE;
  const applyStateText = applyRollback.canApply
    ? 'Ready to apply for current run'
    : 'Applied for this run; trigger new pull/update to apply again';

  if (v3.sessionPhase === 'idle') {
    return (
      <div className={cn('flex h-full flex-col bg-zinc-900 border-l border-zinc-800', className)}>
        <div className="border-b border-zinc-800 px-4 py-3">
          <div className="text-xs font-medium uppercase tracking-wider text-zinc-500">
            Start a Session
          </div>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
          <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-3">
            <div className="text-xs uppercase tracking-wider text-zinc-500">1. Import Tune</div>
            <div className="mt-2 text-sm text-zinc-200">
              {localImportedTune ? localImportedTune.sourceName : 'No tune loaded'}
            </div>
            <Button
              type="button"
              variant="secondary"
              className="mt-3 w-full"
              onClick={() => setShowImportSheet(true)}
            >
              {localImportedTune ? 'Replace Tune' : 'Import Tune'}
            </Button>
          </div>

          <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-3">
            <div className="text-xs uppercase tracking-wider text-zinc-500">2. Configuration</div>
            <div className="mt-2 space-y-1 text-sm text-zinc-300">
              <div>Engine: {config.engine_family}</div>
              <div>Cam: {config.cam_spec}</div>
              <div>Exhaust: {config.exhaust_type}</div>
            </div>
            <Button
              type="button"
              variant="secondary"
              className="mt-3 w-full"
              onClick={() => setShowConfigSheet(true)}
            >
              Edit Config
            </Button>
          </div>

          <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-3">
            <div className="text-xs uppercase tracking-wider text-zinc-500">3. Start Session</div>
            <div className="mt-2 text-sm text-zinc-300">
              Estimated pulls: {v3.initResult?.estimated_pulls ?? '6-8'}
            </div>
            {v3StatusQuery.data?.available === false && !v3StatusQuery.isLoading && (
              <div className="mt-2 text-xs text-amber-400">
                {v3StatusQuery.data?.message ?? 'AI Coach is not available on this server'}
              </div>
            )}
            {v3.createError && (
              <div className="mt-2 text-xs text-red-400">
                {handleApiError(v3.createError)}
              </div>
            )}
            <Button
              type="button"
              className="mt-3 w-full bg-orange-500 hover:bg-orange-600 text-white"
              onClick={handleStartSession}
              disabled={
                v3.isCreating ||
                v3StatusQuery.isLoading ||
                v3StatusQuery.data?.available === false
              }
            >
              {v3.isCreating
                ? 'Starting...'
                : v3StatusQuery.isLoading
                  ? 'Checking...'
                  : 'Start Session'}
            </Button>
          </div>
        </div>

        <Sheet open={showImportSheet} onOpenChange={setShowImportSheet}>
          <SheetContent side="right" className="w-[560px] sm:max-w-[560px] flex flex-col">
            <SheetHeader>
              <SheetTitle>Import Tune</SheetTitle>
            </SheetHeader>
            <div className="flex-1 overflow-y-auto mt-4">
              <TuneImport
                onImport={(result) => {
                  setLocalImportedTune(result);
                }}
                sheet
              />
            </div>
            <div className="border-t border-zinc-800 pt-4 mt-4">
              <Button
                onClick={() => setShowImportSheet(false)}
                className="w-full"
                variant="outline"
              >
                Done
              </Button>
            </div>
          </SheetContent>
        </Sheet>

        <Sheet open={showConfigSheet} onOpenChange={setShowConfigSheet}>
          <SheetContent side="right" className="w-[420px] sm:max-w-[420px]">
            <SheetHeader>
              <SheetTitle>Edit Configuration</SheetTitle>
            </SheetHeader>
            <div className="mt-4 space-y-4">
              <div className="space-y-2">
                <Label>Engine Family</Label>
                <Select
                  value={config.engine_family}
                  onValueChange={(value) =>
                    setConfig((prev) => ({
                      ...prev,
                      engine_family: value,
                      displacement_ci: parseInt(value.split('_')[1] ?? '114', 10) || 114,
                    }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ENGINE_FAMILIES.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Displacement (ci)</Label>
                <Input
                  type="number"
                  value={config.displacement_ci}
                  onChange={(event) =>
                    setConfig((prev) => ({
                      ...prev,
                      displacement_ci: Number(event.target.value),
                    }))
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>Cam Spec</Label>
                <Select
                  value={config.cam_spec ?? 'stock'}
                  onValueChange={(value) => setConfig((prev) => ({ ...prev, cam_spec: value }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {CAM_OPTIONS.map((option) => (
                      <SelectItem key={option} value={option}>
                        {option}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Exhaust</Label>
                <Select
                  value={config.exhaust_type ?? 'stock'}
                  onValueChange={(value) => setConfig((prev) => ({ ...prev, exhaust_type: value }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {EXHAUST_OPTIONS.map((option) => (
                      <SelectItem key={option} value={option}>
                        {option}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Air Cleaner</Label>
                <Select
                  value={config.air_cleaner ?? 'stock'}
                  onValueChange={(value) => setConfig((prev) => ({ ...prev, air_cleaner: value }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {AIR_CLEANER_OPTIONS.map((option) => (
                      <SelectItem key={option} value={option}>
                        {option}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </SheetContent>
        </Sheet>
      </div>
    );
  }

  return (
    <div className={cn('flex h-full flex-col bg-zinc-900 border-l border-zinc-800', className)}>
      <div className="border-b border-zinc-800 px-4 py-4">
        <div className="flex items-center justify-between text-xs text-zinc-500">
          <span className="uppercase tracking-wider">AI Coach</span>
          {currentStep && totalSteps ? (
            <span className="text-zinc-400">
              Step {currentStep} / ~{totalSteps}
            </span>
          ) : (
            <span className="text-zinc-400">Step ? / ~?</span>
          )}
        </div>
        <Progress value={stepProgress} className="mt-2 h-2 bg-zinc-800 border-0" />
        <div className="mt-3 text-sm font-semibold text-zinc-100">{guidanceTitle}</div>
        <div className="mt-1 text-xs text-zinc-400">{guidanceDetail}</div>
        <div className="mt-3 rounded-md border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-[11px] text-zinc-400">
          <div>Last analyzed update: {formattedLastAnalyzedAt}</div>
          <div>Run ready: {effectiveRunId ?? MISSING_VALUE}</div>
          <div>Run prepared at: {formattedRunReadyAt}</div>
          <div>{applyStateText}</div>
        </div>

        {/* Section 2: Convergence — percentage bars only */}
        <div className="mt-3 space-y-2">
          <div className="flex items-center justify-between text-xs text-zinc-400">
            <span>Overall</span>
            <span>{Math.round(overallCoverage)}%</span>
          </div>
          <Progress value={overallCoverage} className="h-2 bg-zinc-800 border-0" />

          <div className="flex items-center justify-between text-xs text-zinc-500">
            <span>Front</span>
            <span>{Math.round(frontCoverage)}%</span>
          </div>
          <Progress value={frontCoverage} className="h-2 bg-zinc-800 border-0" />

          <div className="flex items-center justify-between text-xs text-zinc-500">
            <span>Rear</span>
            <span>{Math.round(rearCoverage)}%</span>
          </div>
          <Progress value={rearCoverage} className="h-2 bg-zinc-800 border-0" />
        </div>
      </div>

      {/* Section 3: AI Insight — single prose block */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        <div className="border-t border-zinc-800 pt-3">
          <div className="text-[10px] uppercase tracking-wider text-zinc-500">AI Insight</div>
          <div className="mt-2 space-y-2 text-sm leading-snug text-zinc-300">
            {v3.nextPull ? (
              <>
                <div className="space-y-1">
                  <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                    <span className="text-[10px] uppercase tracking-wider text-zinc-500">Next</span>
                    <span className="font-semibold text-zinc-100">
                      {v3.nextPull.pull_mode === 'steady_state' ? 'Steady-state pull' : 'WOT pull'}
                    </span>
                  </div>
                  <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                    <span className="text-[10px] uppercase tracking-wider text-zinc-500">Target</span>
                    <span className="font-mono tabular-nums text-zinc-200">
                      {Math.round(v3.nextPull.rpm)} RPM @ {Math.round(v3.nextPull.map_kpa)} kPa
                    </span>
                  </div>
                </div>

                {v3.nextPull.reason && (
                  <div>
                    <div className="text-[10px] uppercase tracking-wider text-zinc-500">Why</div>
                    <div className="mt-1 text-zinc-300">{v3.nextPull.reason}</div>
                  </div>
                )}

                {planItems.length > 1 && (
                  <div className="text-xs text-zinc-400">
                    Then: {planItems.length - 1} more pull{planItems.length - 1 === 1 ? '' : 's'} planned.
                  </div>
                )}
              </>
            ) : (
              <span className="text-zinc-500">
                Start a session and complete your first pull to generate AI insights.
              </span>
            )}
          </div>

          <button
            type="button"
            className="mt-3 flex items-center gap-1 text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
            onClick={() => setShowFullAnalysis((prev) => !prev)}
          >
            {showFullAnalysis ? 'Hide full analysis' : 'Show full analysis'}
            <ChevronDown className={cn('h-3 w-3 transition-transform', showFullAnalysis && 'rotate-180')} />
          </button>

          {showFullAnalysis && (
            <div className="mt-3 space-y-3 border-t border-zinc-800 pt-3">
              {/* Zone coverage detail */}
              {overallCoverageReport && (
                <div>
                  <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-2">Zone Coverage</div>
                  {coverageGrade && (
                    <div className="mb-2 flex items-center gap-2">
                      <span className={cn('text-xs font-semibold', coverageGrade.color)}>
                        Grade {coverageGrade.grade}
                      </span>
                      <span className="text-[10px] text-zinc-500">{coverageGrade.description}</span>
                    </div>
                  )}
                  <ul className="space-y-1 text-xs">
                    {overallCoverageReport.zoneBreakdown
                      .filter((z) => ['cruise', 'partThrottle', 'wot'].includes(z.zone))
                      .map((zoneData) => (
                        <li key={zoneData.zone} className="flex items-center justify-between">
                          <span className="text-zinc-400 capitalize">
                            {zoneData.zone === 'partThrottle' ? 'Part Throttle' : zoneData.zone}
                          </span>
                          <span className={cn(
                            'font-medium',
                            zoneData.coveragePct >= 70 ? 'text-green-400' :
                              zoneData.coveragePct >= 50 ? 'text-yellow-400' :
                                'text-orange-400'
                          )}>
                            {Math.round(zoneData.coveragePct)}%
                          </span>
                        </li>
                      ))}
                  </ul>
                </div>
              )}

              {/* Model uncertainty detail */}
              {v3.convergence && (
                <div>
                  <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-2">Model Uncertainty (Advanced)</div>
                  <ul className="space-y-1 text-xs text-zinc-400">
                    <li>Cells needing more coverage (above threshold): {v3.convergence.cells_above_threshold}</li>
                    <li>Mean uncertainty: {v3.convergence.mean_uncertainty.toFixed(3)}</li>
                    {v3.nextPull && <li>Expected info gain: {v3.nextPull.expected_info_gain.toFixed(2)}</li>}
                  </ul>
                </div>
              )}

              {/* Planned pulls */}
              {planItems.length > 0 && (
                <div>
                  <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-2">Planned Pulls</div>
                  <ul className="space-y-1 text-xs text-zinc-400">
                    {planItems.map((plan) => (
                      <li key={`${plan.pull_number}-${plan.rpm}-${plan.map_kpa}`} className="flex items-center gap-2">
                        <ChevronRight className="h-3 w-3 text-zinc-500" />
                        {Math.round(plan.rpm)} RPM / {Math.round(plan.map_kpa)} kPa
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="border-t border-zinc-800 px-4 py-4">
        <div className="text-[10px] uppercase tracking-wider text-zinc-500">Cylinder</div>
        <div className="mt-2 flex items-center gap-2">
          <button
            type="button"
            className={cn(
              'rounded-md border border-zinc-800 px-3 py-1 text-xs',
              cylinder === 'front'
                ? 'bg-orange-500 text-white'
                : 'text-zinc-400 hover:text-zinc-200',
            )}
            onClick={() => {
              setLocalCylinder('front');
              onCylinderChange?.('front');
            }}
          >
            Front
          </button>
          <button
            type="button"
            className={cn(
              'rounded-md border border-zinc-800 px-3 py-1 text-xs',
              cylinder === 'rear'
                ? 'bg-orange-500 text-white'
                : 'text-zinc-400 hover:text-zinc-200',
            )}
            onClick={() => {
              setLocalCylinder('rear');
              onCylinderChange?.('rear');
            }}
          >
            Rear
          </button>
          <span className="ml-auto text-xs text-zinc-400">Balance: {balanceText}</span>
        </div>

        <div className="mt-4 border-t border-zinc-800 pt-4">
          <div className="text-[10px] uppercase tracking-wider text-zinc-500">AFR Targets</div>
          <div className="mt-2 flex items-center justify-between text-xs text-zinc-300">
            <span>Cruise: {cruiseTarget}</span>
            <span>WOT: {wotTarget}</span>
          </div>
          <Button
            type="button"
            variant="ghost"
            className="mt-2 px-0 text-xs text-zinc-400 hover:text-zinc-200"
            onClick={() => setShowTargetsSheet(true)}
          >
            Edit targets
          </Button>
        </div>
      </div>

      <div className="sticky bottom-0 border-t border-zinc-800 bg-zinc-900 px-4 py-4">
        <Button
          type="button"
          className="w-full bg-orange-500 hover:bg-orange-600 text-white"
          disabled={!applyRollback.canApply || applyRollback.status !== 'idle' || v3.isMaterializingRun}
          onClick={() => void handleApplyCorrections()}
        >
          {v3.isMaterializingRun
            ? 'Preparing run...'
            : applyRollback.status === 'applying'
              ? 'Applying...'
              : 'Accept Corrections'}
        </Button>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <Button
            type="button"
            variant="secondary"
            disabled={!effectiveRunId || !applyRollback.canRollback || applyRollback.status !== 'idle'}
            onClick={() => {
              const confirmed = window.confirm('Rollback VE corrections? This will revert applied changes.');
              if (confirmed) {
                void applyRollback.rollback();
              }
            }}
          >
            Rollback
          </Button>
          <Button type="button" variant="secondary" disabled={!onExport} onClick={onExport}>
            Export
          </Button>
        </div>
      </div>

      <Sheet open={showTargetsSheet} onOpenChange={setShowTargetsSheet}>
        <SheetContent side="right" className="w-[520px] sm:max-w-[520px]">
          <SheetHeader>
            <SheetTitle>AFR Targets</SheetTitle>
          </SheetHeader>
          <div className="mt-4">
            <AFRTargetTable targets={localTargets} onChange={handleTargetsChange} />
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
