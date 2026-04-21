/**
 * Tuning Session page.
 *
 * Per-bike dropzone with smart content routing and a live status checklist.
 * Solves the "save / name / route / find / open" friction by letting users
 * drop any mix of WP8, PVV, TXT, CSV files and having the backend classify
 * and route them into base_tune / patches / pulls automatically.
 */

import { useCallback, useMemo, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  ArrowLeft,
  CheckCircle2,
  XCircle,
  Loader2,
  File as FileIcon,
  Upload,
  AlertTriangle,
  FlaskConical,
  FileWarning,
  FolderOpen,
  Plus,
} from 'lucide-react';

import { toast } from '@/lib/toast';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';

import {
  useAnalyses,
  useAnalyzeIteration,
  useCreateIteration,
  useIterations,
  usePatches,
  usePulls,
  useSession,
  useSessionStatus,
  useUploadToSession,
  useVehicle,
} from '../hooks/useTuningWorkspace';
import type { AnalysisResult, RoutedFile, RejectedFile } from '../api/workspace';

interface PerUploadResult {
  routed: RoutedFile[];
  rejected: RejectedFile[];
}

export default function TuningSessionPage() {
  const { vehicleId, sessionId } = useParams<{ vehicleId: string; sessionId: string }>();

  const vehicle = useVehicle(vehicleId);
  const session = useSession(vehicleId, sessionId);
  const iterations = useIterations(vehicleId, sessionId);
  const status = useSessionStatus(vehicleId, sessionId, 5000);

  const activeIterationId = status.data?.iteration_id ?? session.data?.active_iteration_id ?? undefined;
  const pulls = usePulls(vehicleId, sessionId, activeIterationId);
  const patches = usePatches(vehicleId, sessionId, activeIterationId);
  const analyses = useAnalyses(vehicleId, sessionId, activeIterationId);

  const upload = useUploadToSession(vehicleId, sessionId);
  const createIter = useCreateIteration(vehicleId, sessionId);
  const analyze = useAnalyzeIteration(vehicleId, sessionId);

  const [isDragging, setIsDragging] = useState(false);
  const [lastResult, setLastResult] = useState<PerUploadResult | null>(null);
  const [lastAnalysis, setLastAnalysis] = useState<AnalysisResult | null>(null);

  const handleFiles = useCallback(
    async (files: File[]) => {
      if (files.length === 0) return;
      try {
        const res = await upload.mutateAsync({ files });
        setLastResult({ routed: res.routed, rejected: res.rejected });
        if (res.routed.length > 0) {
          toast.success(`Routed ${res.routed.length} file${res.routed.length === 1 ? '' : 's'}`);
        }
        if (res.rejected.length > 0) {
          toast.error(`${res.rejected.length} file${res.rejected.length === 1 ? '' : 's'} rejected`);
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'upload failed';
        toast.error(msg);
      }
    },
    [upload]
  );

  const onDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDragging(false);
      const files = Array.from(e.dataTransfer.files);
      if (files.length > 0) void handleFiles(files);
    },
    [handleFiles]
  );

  const onBrowse = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(e.target.files ?? []);
      if (files.length > 0) void handleFiles(files);
      e.target.value = '';
    },
    [handleFiles]
  );

  const startNextIteration = useCallback(async () => {
    try {
      const iter = await createIter.mutateAsync(undefined);
      toast.success(`Started ${iter.id}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'could not create iteration';
      toast.error(msg);
    }
  }, [createIter]);

  const runAnalysis = useCallback(async () => {
    try {
      const res = await analyze.mutateAsync({});
      setLastAnalysis(res);
      if (res.success) {
        toast.success(
          res.zones_adjusted
            ? `Analyzed. ${res.zones_adjusted} zones adjusted.`
            : 'Analysis complete.'
        );
      } else {
        toast.error(res.errors?.[0] ?? 'analysis failed');
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'analysis failed');
    }
  }, [analyze]);

  const loading = vehicle.isLoading || session.isLoading;
  const notFound = vehicle.isError || session.isError;

  return (
    <div className="container mx-auto py-6 space-y-6 max-w-6xl">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" asChild>
          <Link to="/workspace">
            <ArrowLeft className="h-4 w-4 mr-1" />
            Workspace
          </Link>
        </Button>
      </div>

      {loading && (
        <div className="space-y-4">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-48 w-full" />
        </div>
      )}

      {notFound && (
        <Alert variant="destructive">
          <FileWarning className="h-4 w-4" />
          <AlertTitle>Session not found</AlertTitle>
          <AlertDescription>
            No tuning session matches{' '}
            <code>
              {vehicleId}/{sessionId}
            </code>
            .
          </AlertDescription>
        </Alert>
      )}

      {!loading && !notFound && vehicle.data && session.data && (
        <>
          <Card>
            <CardHeader>
              <div className="flex items-start justify-between flex-wrap gap-4">
                <div>
                  <CardTitle className="text-2xl flex items-center gap-2">
                    <FlaskConical className="h-6 w-6 text-primary" />
                    {vehicle.data.name}
                  </CardTitle>
                  <CardDescription className="mt-1">
                    Session {session.data.id} &middot; active iteration{' '}
                    <Badge variant="secondary">{activeIterationId ?? '(none)'}</Badge>
                  </CardDescription>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <div className="flex items-center gap-2">
                    <Button
                      onClick={runAnalysis}
                      disabled={
                        analyze.isPending ||
                        status.isLoading ||
                        !status.data?.ready_to_analyze
                      }
                      title={
                        status.data?.ready_to_analyze
                          ? 'Run AutoTune on this iteration'
                          : status.isLoading
                            ? 'Checking readiness…'
                            : 'Complete the readiness checklist below'
                      }
                    >
                      {analyze.isPending ? (
                        <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                      ) : (
                        <FlaskConical className="h-4 w-4 mr-1" />
                      )}
                      Analyze
                    </Button>
                    <Button variant="outline" onClick={startNextIteration} disabled={createIter.isPending}>
                      <Plus className="h-4 w-4 mr-1" />
                      Next iteration
                    </Button>
                  </div>
                  {status.isLoading && (
                    <p className="text-xs text-muted-foreground text-right max-w-xs">
                      Checking readiness…
                    </p>
                  )}
                  {status.data && !status.data.ready_to_analyze && (
                    <p className="text-xs text-muted-foreground text-right max-w-xs">
                      Analyze stays disabled until every checklist item passes — upload base tune, pulls,
                      and AFR data as needed.
                    </p>
                  )}
                </div>
              </div>
            </CardHeader>
          </Card>

          <Card
            className={`border-2 ${isDragging ? 'border-primary bg-primary/5' : 'border-dashed border-muted-foreground/25'} transition-colors`}
            onDrop={onDrop}
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={(e) => {
              e.preventDefault();
              setIsDragging(false);
            }}
          >
            <CardContent className="py-12">
              <label htmlFor="session-dropzone" className="flex flex-col items-center cursor-pointer">
                <div className="p-4 rounded-full bg-muted mb-4">
                  {upload.isPending ? (
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                  ) : (
                    <Upload className="h-8 w-8 text-muted-foreground" />
                  )}
                </div>
                <p className="text-lg font-medium mb-1">
                  {upload.isPending ? 'Routing files…' : 'Drop WP8, PVV, or TXT files here'}
                </p>
                <p className="text-sm text-muted-foreground mb-2">
                  Or click to browse. Content type is detected automatically.
                </p>
                <p className="text-xs text-muted-foreground/70">
                  PVV → base tune or patch &middot; WP8 / TXT / CSV → pulls on the active iteration
                </p>
                <input
                  id="session-dropzone"
                  type="file"
                  className="hidden"
                  multiple
                  accept=".csv,.txt,.wp8,.pvv,.pvm,.pti"
                  onChange={onBrowse}
                />
              </label>
            </CardContent>
          </Card>

          {lastResult && (lastResult.routed.length > 0 || lastResult.rejected.length > 0) && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Last upload</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {lastResult.routed.map((r, i) => (
                  <div
                    key={`${r.name}-routed-${i}`}
                    className="flex items-center justify-between text-sm border rounded px-3 py-2"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
                      <span className="font-mono truncate">{r.name}</span>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <Badge variant="outline">{r.type}</Badge>
                      <Badge>{r.slot}</Badge>
                    </div>
                  </div>
                ))}
                {lastResult.rejected.map((r, i) => (
                  <div
                    key={`${r.name}-rej-${i}`}
                    className="flex items-center justify-between text-sm border rounded px-3 py-2 border-destructive/30 bg-destructive/5"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <XCircle className="h-4 w-4 text-destructive shrink-0" />
                      <span className="font-mono truncate">{r.name}</span>
                    </div>
                    <span className="text-xs text-muted-foreground truncate max-w-[50%] text-right">
                      {r.reason}
                    </span>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {lastAnalysis && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Last analysis</CardTitle>
                <CardDescription>
                  {lastAnalysis.iteration_id} &middot; source {lastAnalysis.data_source ?? '—'}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <div className="grid grid-cols-2 gap-4">
                  <Stat label="Peak HP" value={lastAnalysis.peak_hp} suffix=" hp" />
                  <Stat label="Zones adjusted" value={lastAnalysis.zones_adjusted} />
                  <Stat
                    label="Mean AFR error"
                    value={lastAnalysis.afr_mean_error_pct}
                    suffix=" %"
                  />
                  <Stat label="Primary pull" valueText={lastAnalysis.primary_pull ?? '—'} />
                </div>
                {lastAnalysis.correction_pvv_path && (
                  <p className="text-xs text-muted-foreground">
                    Correction PVV saved to the patches folder.
                  </p>
                )}
                {lastAnalysis.errors?.length ? (
                  <ul className="text-xs text-destructive list-disc ml-4">
                    {lastAnalysis.errors.map((e, i) => (
                      <li key={i}>{e}</li>
                    ))}
                  </ul>
                ) : null}
              </CardContent>
            </Card>
          )}

          <div className="grid md:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4" />
                  Readiness checklist
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {status.isLoading ? (
                  <Skeleton className="h-32 w-full" />
                ) : status.data ? (
                  <ul className="space-y-2">
                    {status.data.checklist.map((c) => (
                      <li key={c.id} className="flex items-start gap-3 text-sm">
                        {c.ok ? (
                          <CheckCircle2 className="h-4 w-4 text-emerald-500 mt-0.5 shrink-0" />
                        ) : (
                          <AlertTriangle className="h-4 w-4 text-amber-500 mt-0.5 shrink-0" />
                        )}
                        <div className="min-w-0">
                          <p className="font-medium">{c.label}</p>
                          {c.detail && (
                            <p className="text-xs text-muted-foreground break-all">{c.detail}</p>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-muted-foreground">No status available.</p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <FolderOpen className="h-4 w-4" />
                  Artifacts (active iteration)
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <ArtifactSection title="Pulls" files={pulls.data ?? []} loading={pulls.isLoading} />
                <ArtifactSection title="Patches" files={patches.data ?? []} loading={patches.isLoading} />
                <ArtifactSection title="Analyses" files={analyses.data ?? []} loading={analyses.isLoading} />
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Iteration history</CardTitle>
            </CardHeader>
            <CardContent>
              {iterations.isLoading ? (
                <Skeleton className="h-10 w-full" />
              ) : iterations.data && iterations.data.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {iterations.data.map((it) => (
                    <Badge
                      key={it.id}
                      variant={it.id === activeIterationId ? 'default' : 'outline'}
                      className="gap-1"
                    >
                      {it.id}
                      {it.id === activeIterationId && (
                        <span className="text-[10px] opacity-80">(active)</span>
                      )}
                    </Badge>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No iterations yet.</p>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  valueText,
  suffix,
}: {
  label: string;
  value?: number | null;
  valueText?: string;
  suffix?: string;
}) {
  let display: string;
  if (valueText !== undefined) {
    display = valueText;
  } else if (value === null || value === undefined || Number.isNaN(value)) {
    display = '—';
  } else {
    display = `${value.toFixed(2)}${suffix ?? ''}`;
  }
  return (
    <div>
      <p className="text-xs text-muted-foreground uppercase tracking-wide">{label}</p>
      <p className="text-lg font-semibold">{display}</p>
    </div>
  );
}

function ArtifactSection({
  title,
  files,
  loading,
}: {
  title: string;
  files: Array<{ name: string; size: number; mtime: number; path: string }>;
  loading: boolean;
}) {
  const displayFiles = useMemo(
    () => [...files].sort((a, b) => b.mtime - a.mtime).slice(0, 8),
    [files]
  );

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <p className="text-sm font-medium">{title}</p>
        <Badge variant="outline">{files.length}</Badge>
      </div>
      {loading ? (
        <Skeleton className="h-6 w-full" />
      ) : displayFiles.length === 0 ? (
        <p className="text-xs text-muted-foreground italic">none</p>
      ) : (
        <ul className="space-y-1">
          {displayFiles.map((f) => (
            <li key={f.path} className="flex items-center gap-2 text-xs">
              <FileIcon className="h-3 w-3 text-muted-foreground shrink-0" />
              <span className="font-mono truncate flex-1">{f.name}</span>
              <span className="text-muted-foreground shrink-0">
                {(f.size / 1024).toFixed(1)} KB
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
