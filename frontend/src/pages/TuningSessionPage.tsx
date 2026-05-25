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
import { isAxiosError } from 'axios';
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Download,
  File as FileIcon,
  FileWarning,
  FlaskConical,
  FolderOpen,
  Plus,
  Upload,
} from 'lucide-react';

import { toast } from '@/lib/toast';
import { cn } from '@/lib/utils';
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from '@/components/ui/empty';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { Spinner } from '@/components/ui/spinner';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';

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
import {
  downloadWorkspaceArtifact,
  type AnalysisResult,
  type ChecklistItem,
  type FileSummary,
  type RoutedFile,
  type RejectedFile,
  type WorkspaceArtifactSlot,
} from '../api/workspace';

interface PerUploadResult {
  routed: RoutedFile[];
  rejected: RejectedFile[];
}

const UPLOAD_INPUT_ID = 'session-dropzone';

export default function TuningSessionPage() {
  const { vehicleId, sessionId } = useParams<{ vehicleId: string; sessionId: string }>();

  const vehicle = useVehicle(vehicleId);
  const session = useSession(vehicleId, sessionId);
  const iterations = useIterations(vehicleId, sessionId);
  const status = useSessionStatus(vehicleId, sessionId, 5000);

  const activeIterationId =
    status.data?.iteration_id ?? session.data?.active_iteration_id ?? undefined;
  const pulls = usePulls(vehicleId, sessionId, activeIterationId);
  const patches = usePatches(vehicleId, sessionId, activeIterationId);
  const analyses = useAnalyses(vehicleId, sessionId, activeIterationId);

  const upload = useUploadToSession(vehicleId, sessionId);
  const createIter = useCreateIteration(vehicleId, sessionId);
  const analyze = useAnalyzeIteration(vehicleId, sessionId);

  const [isDragging, setIsDragging] = useState(false);
  const [lastResult, setLastResult] = useState<PerUploadResult | null>(null);
  const [lastAnalysis, setLastAnalysis] = useState<AnalysisResult | null>(null);

  const openUploadDialog = useCallback(() => {
    const input = document.getElementById(UPLOAD_INPUT_ID) as HTMLInputElement | null;
    input?.click();
  }, []);

  const baseTuneMissing = useMemo(
    () => !!lastAnalysis?.errors?.some((e) => e === 'no base tune uploaded'),
    [lastAnalysis]
  );

  const guardrailsMissing = useMemo(
    () =>
      !!lastAnalysis?.errors?.some((e) =>
        e.includes('profile.json missing tuning_guardrails block')
      ),
    [lastAnalysis]
  );

  const generatedPatchFilename = useMemo(() => {
    if (!lastAnalysis) return null;
    if (lastAnalysis.correction_pvv_filename) return lastAnalysis.correction_pvv_filename;
    if (!lastAnalysis.correction_pvv_path) return null;
    return lastAnalysis.correction_pvv_path.split(/[\\/]/).pop() ?? null;
  }, [lastAnalysis]);

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

  const startNextIteration = useCallback(() => {
    void (async () => {
      try {
        const iter = await createIter.mutateAsync(undefined);
        toast.success(`Started ${iter.id}`);
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'could not create iteration';
        toast.error(msg);
      }
    })();
  }, [createIter]);

  const downloadArtifact = useCallback(
    (slot: WorkspaceArtifactSlot, filename: string, iterationId?: string) => {
      const resolvedIterationId = iterationId ?? activeIterationId;
      if (!vehicleId || !sessionId || !resolvedIterationId) {
        toast.error('No active iteration selected for download');
        return;
      }
      void (async () => {
        try {
          await downloadWorkspaceArtifact(
            vehicleId,
            sessionId,
            resolvedIterationId,
            slot,
            filename
          );
        } catch (err) {
          const msg = err instanceof Error ? err.message : `Failed to download ${filename}`;
          if (msg.includes('404')) {
            toast.error(
              'Download endpoint returned 404. Restart backend so the new workspace download route is loaded.'
            );
            return;
          }
          toast.error(msg);
        }
      })();
    },
    [activeIterationId, sessionId, vehicleId]
  );

  const runAnalysisAsync = useCallback(async () => {
    try {
      const res = await analyze.mutateAsync({ iterationId: activeIterationId });
      setLastAnalysis(res);
      if (res.success) {
        const generatedPatchName =
          res.correction_pvv_filename ??
          res.correction_pvv_path?.split(/[\\/]/).pop() ??
          null;

        if (generatedPatchName && vehicleId && sessionId) {
          try {
            await downloadWorkspaceArtifact(
              vehicleId,
              sessionId,
              res.iteration_id,
              'patches',
              generatedPatchName
            );
            toast.success(
              res.zones_adjusted
                ? `Analyzed. ${res.zones_adjusted} zones adjusted. Downloaded ${generatedPatchName}.`
                : `Analysis complete. Downloaded ${generatedPatchName}.`
            );
          } catch {
            toast.success(
              res.zones_adjusted
                ? `Analyzed. ${res.zones_adjusted} zones adjusted.`
                : 'Analysis complete.'
            );
            toast.error(
              'Patch was generated but auto-download failed. Use Artifacts > Patches to download.'
            );
          }
        } else {
          toast.success(
            res.zones_adjusted
              ? `Analyzed. ${res.zones_adjusted} zones adjusted.`
              : 'Analysis complete.'
          );
        }
      } else {
        toast.error(res.errors?.[0] ?? 'analysis failed');
      }
    } catch (err) {
      if (isAxiosError<AnalysisResult>(err) && err.response?.data) {
        const failed = err.response.data;
        setLastAnalysis(failed);
        toast.error(failed.errors?.[0] ?? 'analysis failed');
        return;
      }
      toast.error(err instanceof Error ? err.message : 'analysis failed');
    }
  }, [activeIterationId, analyze, sessionId, vehicleId]);

  const runAnalysis = useCallback(() => {
    void runAnalysisAsync();
  }, [runAnalysisAsync]);

  const loading = vehicle.isLoading || session.isLoading;
  const notFound = vehicle.isError || session.isError;

  const analyzeReady = !!status.data?.ready_to_analyze;
  const analyzeDisabledReason = status.isLoading
    ? 'Checking readiness…'
    : analyzeReady
      ? 'Run AutoTune on this iteration'
      : 'Complete the readiness checklist below — upload base tune, pulls, and AFR data as needed.';

  return (
    <div className="container mx-auto flex max-w-6xl flex-col gap-6 py-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" asChild>
          <Link to="/jetdrive?view=tuning">
            <ArrowLeft data-icon="inline-start" />
            Workspace
          </Link>
        </Button>
      </div>

      {loading ? (
        <div className="flex flex-col gap-4">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-48 w-full" />
        </div>
      ) : notFound ? (
        <Alert variant="destructive">
          <FileWarning />
          <AlertTitle>Session not found</AlertTitle>
          <AlertDescription>
            No tuning session matches{' '}
            <code>
              {vehicleId}/{sessionId}
            </code>
            .
          </AlertDescription>
        </Alert>
      ) : vehicle.data && session.data ? (
        <>
          <SessionHeader
            vehicleName={vehicle.data.name}
            sessionId={session.data.id}
            activeIterationId={activeIterationId}
            analyzeReady={analyzeReady}
            analyzeBusy={analyze.isPending}
            statusLoading={status.isLoading}
            tooltipMessage={analyzeDisabledReason}
            onAnalyze={runAnalysis}
            onNextIteration={startNextIteration}
            iterationBusy={createIter.isPending}
          />

          <Dropzone
            isDragging={isDragging}
            uploading={upload.isPending}
            onDrop={onDrop}
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={(e) => {
              e.preventDefault();
              setIsDragging(false);
            }}
            onBrowse={onBrowse}
          />

          <Tabs defaultValue="overview">
            <TabsList>
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="artifacts">Artifacts</TabsTrigger>
              <TabsTrigger value="iterations">Iterations</TabsTrigger>
            </TabsList>

            <TabsContent value="overview" className="flex flex-col gap-4">
              {(baseTuneMissing || guardrailsMissing) && (
                <Alert variant="destructive">
                  <AlertTriangle />
                  <AlertTitle>AutoTune blocked</AlertTitle>
                  <AlertDescription className="flex flex-col gap-2">
                    <span>
                      {baseTuneMissing
                        ? 'Upload a base tune PVV before generating an AutoTune patch.'
                        : 'Vehicle profile is missing tuning_guardrails in profile.json.'}
                    </span>
                    {baseTuneMissing ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={openUploadDialog}
                      >
                        <Upload data-icon="inline-start" />
                        Upload base tune
                      </Button>
                    ) : null}
                  </AlertDescription>
                </Alert>
              )}

              <div className="grid gap-4 md:grid-cols-2">
                <ReadinessChecklistCard
                  checklist={status.data?.checklist}
                  loading={status.isLoading}
                />

                <LastAnalysisCard
                  analysis={lastAnalysis}
                  generatedPatchFilename={generatedPatchFilename}
                  onDownloadPatch={(filename, iterationId) =>
                    downloadArtifact('patches', filename, iterationId)
                  }
                />
              </div>

              <LastUploadCard result={lastResult} />
            </TabsContent>

            <TabsContent value="artifacts" className="flex flex-col gap-4">
              <ArtifactCard
                title="Pulls"
                slot="pulls"
                files={pulls.data ?? []}
                loading={pulls.isLoading}
                onDownload={downloadArtifact}
                onPromptUpload={openUploadDialog}
              />
              <ArtifactCard
                title="Patches"
                slot="patches"
                files={patches.data ?? []}
                loading={patches.isLoading}
                onDownload={downloadArtifact}
                onPromptUpload={openUploadDialog}
              />
              <ArtifactCard
                title="Analyses"
                slot="analyses"
                files={analyses.data ?? []}
                loading={analyses.isLoading}
                onDownload={downloadArtifact}
                onPromptUpload={openUploadDialog}
              />
            </TabsContent>

            <TabsContent value="iterations">
              <Card>
                <CardHeader>
                  <CardTitle>Iteration history</CardTitle>
                  <CardDescription>
                    Each iteration captures a tune + pulls + analysis cycle.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {iterations.isLoading ? (
                    <Skeleton className="h-10 w-full" />
                  ) : iterations.data && iterations.data.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {iterations.data.map((it) => {
                        const active = it.id === activeIterationId;
                        return (
                          <Badge
                            key={it.id}
                            variant={active ? 'default' : 'outline'}
                            className="gap-1"
                          >
                            {it.id}
                            {active ? (
                              <span className="text-[10px] opacity-80">
                                (active)
                              </span>
                            ) : null}
                          </Badge>
                        );
                      })}
                    </div>
                  ) : (
                    <Empty className="border-0 p-0 md:p-0">
                      <EmptyHeader>
                        <EmptyTitle>No iterations yet</EmptyTitle>
                        <EmptyDescription>
                          A first iteration is created when you upload pulls or
                          a base tune.
                        </EmptyDescription>
                      </EmptyHeader>
                    </Empty>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Header
// ---------------------------------------------------------------------------

function SessionHeader({
  vehicleName,
  sessionId,
  activeIterationId,
  analyzeReady,
  analyzeBusy,
  statusLoading,
  tooltipMessage,
  onAnalyze,
  onNextIteration,
  iterationBusy,
}: {
  vehicleName: string;
  sessionId: string;
  activeIterationId?: string;
  analyzeReady: boolean;
  analyzeBusy: boolean;
  statusLoading: boolean;
  tooltipMessage: string;
  onAnalyze: () => void;
  onNextIteration: () => void;
  iterationBusy: boolean;
}) {
  const analyzeDisabled = analyzeBusy || statusLoading || !analyzeReady;

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex flex-col gap-1">
            <CardTitle className="flex items-center gap-2 text-2xl">
              <FlaskConical className="size-6 text-primary" />
              {vehicleName}
            </CardTitle>
            <CardDescription className="flex flex-wrap items-center gap-2">
              <span>Session</span>
              <Badge variant="outline" className="font-mono">
                {sessionId}
              </Badge>
              <span>·</span>
              <span>active iteration</span>
              <Badge variant="secondary">{activeIterationId ?? '(none)'}</Badge>
            </CardDescription>
          </div>

          <div className="flex items-center gap-2">
            <Tooltip>
              <TooltipTrigger asChild>
                <span className={analyzeDisabled ? 'cursor-not-allowed' : undefined}>
                  <Button
                    onClick={onAnalyze}
                    disabled={analyzeDisabled}
                    aria-label="Generate AutoTune patch"
                  >
                    {analyzeBusy ? (
                      <Spinner data-icon="inline-start" />
                    ) : (
                      <FlaskConical data-icon="inline-start" />
                    )}
                    Generate AutoTune patch
                  </Button>
                </span>
              </TooltipTrigger>
              <TooltipContent>{tooltipMessage}</TooltipContent>
            </Tooltip>

            <Button
              variant="outline"
              onClick={onNextIteration}
              disabled={iterationBusy}
            >
              {iterationBusy ? (
                <Spinner data-icon="inline-start" />
              ) : (
                <Plus data-icon="inline-start" />
              )}
              Next iteration
            </Button>
          </div>
        </div>
      </CardHeader>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Dropzone
// ---------------------------------------------------------------------------

function Dropzone({
  isDragging,
  uploading,
  onDrop,
  onDragOver,
  onDragLeave,
  onBrowse,
}: {
  isDragging: boolean;
  uploading: boolean;
  onDrop: (e: React.DragEvent<HTMLDivElement>) => void;
  onDragOver: (e: React.DragEvent<HTMLDivElement>) => void;
  onDragLeave: (e: React.DragEvent<HTMLDivElement>) => void;
  onBrowse: (e: React.ChangeEvent<HTMLInputElement>) => void;
}) {
  return (
    <Card
      className={cn(
        'border-2 border-dashed transition-colors',
        isDragging
          ? 'border-primary bg-primary/5'
          : 'border-border'
      )}
      onDrop={onDrop}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
    >
      <CardContent className="py-10">
        <label
          htmlFor={UPLOAD_INPUT_ID}
          className="flex cursor-pointer flex-col items-center gap-3"
        >
          <div className="flex size-14 items-center justify-center rounded-full bg-muted text-muted-foreground">
            {uploading ? (
              <Spinner className="size-6 text-primary" />
            ) : (
              <Upload className="size-6" />
            )}
          </div>
          <div className="flex flex-col items-center gap-1">
            <p className="text-base font-medium">
              {uploading ? 'Routing files…' : 'Drop WP8, PVV, or TXT files here'}
            </p>
            <p className="text-sm text-muted-foreground">
              Or click to browse. Content type is detected automatically.
            </p>
            <p className="text-xs text-muted-foreground/70">
              PVV → base tune or patch · WP8 / TXT / CSV → pulls on the active
              iteration
            </p>
          </div>
          <input
            id={UPLOAD_INPUT_ID}
            type="file"
            className="hidden"
            multiple
            accept=".csv,.txt,.wp8,.pvv,.pvm,.pti"
            onChange={onBrowse}
          />
        </label>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Readiness checklist
// ---------------------------------------------------------------------------

function ReadinessChecklistCard({
  checklist,
  loading,
}: {
  checklist?: ChecklistItem[];
  loading: boolean;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <CheckCircle2 className="size-4" />
          Readiness checklist
        </CardTitle>
        <CardDescription>
          AutoTune unlocks once every item passes.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-32 w-full" />
        ) : checklist && checklist.length > 0 ? (
          <ul className="flex flex-col gap-3">
            {checklist.map((c) => (
              <li key={c.id} className="flex items-start gap-3 text-sm">
                {c.ok ? (
                  <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-primary" />
                ) : (
                  <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" />
                )}
                <div className="flex min-w-0 flex-col gap-0.5">
                  <p className="font-medium leading-tight">{c.label}</p>
                  {c.detail ? (
                    <p className="break-all text-xs text-muted-foreground">
                      {c.detail}
                    </p>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <Empty className="border-0 p-0 md:p-0">
            <EmptyHeader>
              <EmptyTitle>No status available</EmptyTitle>
              <EmptyDescription>
                The session readiness checklist will appear once the workspace
                responds.
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Last analysis
// ---------------------------------------------------------------------------

function LastAnalysisCard({
  analysis,
  generatedPatchFilename,
  onDownloadPatch,
}: {
  analysis: AnalysisResult | null;
  generatedPatchFilename: string | null;
  onDownloadPatch: (filename: string, iterationId: string) => void;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Last analysis</CardTitle>
        {analysis ? (
          <CardDescription className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="font-mono">
              {analysis.iteration_id}
            </Badge>
            <span>source</span>
            <Badge variant="secondary">{analysis.data_source ?? '—'}</Badge>
          </CardDescription>
        ) : (
          <CardDescription>
            Run "Generate AutoTune patch" to populate this.
          </CardDescription>
        )}
      </CardHeader>
      <CardContent>
        {analysis ? (
          <div className="flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-4">
              <Stat label="Peak HP" value={analysis.peak_hp} suffix=" hp" />
              <Stat label="Zones adjusted" value={analysis.zones_adjusted} />
              <Stat
                label="Mean AFR error"
                value={analysis.afr_mean_error_pct}
                suffix=" %"
              />
              <Stat label="Primary pull" valueText={analysis.primary_pull ?? '—'} />
            </div>

            {analysis.correction_pvv_path ? (
              <>
                <Separator />
                <div className="flex flex-col gap-2 text-xs">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-muted-foreground">Patch:</span>
                    <Badge variant="outline" className="font-mono">
                      {analysis.correction_pvv_filename ??
                        analysis.correction_pvv_path.split(/[\\/]/).pop() ??
                        'patch.pvv'}
                    </Badge>
                  </div>
                  {analysis.correction_pvv_sha256 ? (
                    <p className="font-mono text-muted-foreground">
                      SHA-256: {analysis.correction_pvv_sha256.slice(0, 12)}
                    </p>
                  ) : null}
                  {typeof analysis.correction_pvv_n_changed_cells === 'number' ? (
                    <p className="text-muted-foreground">
                      Cells changed: {analysis.correction_pvv_n_changed_cells}
                    </p>
                  ) : null}
                  {analysis.correction_manifest_path ? (
                    <p className="font-mono text-muted-foreground">
                      Manifest:{' '}
                      {analysis.correction_manifest_path.split(/[\\/]/).pop()}
                    </p>
                  ) : null}
                  {generatedPatchFilename ? (
                    <div className="pt-1">
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() =>
                          onDownloadPatch(generatedPatchFilename, analysis.iteration_id)
                        }
                      >
                        <Download data-icon="inline-start" />
                        Download patch
                      </Button>
                    </div>
                  ) : null}
                </div>
              </>
            ) : null}

            {analysis.errors?.length ? (
              <ul className="ml-4 list-disc text-xs text-destructive">
                {analysis.errors.map((e, i) => (
                  <li key={i}>{e}</li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : (
          <Empty className="border-0 p-0 md:p-0">
            <EmptyHeader>
              <EmptyTitle>No analysis yet</EmptyTitle>
              <EmptyDescription>
                Run AutoTune to see peak HP, zones adjusted, and patch metadata
                here.
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Last upload
// ---------------------------------------------------------------------------

function LastUploadCard({ result }: { result: PerUploadResult | null }) {
  if (!result || (result.routed.length === 0 && result.rejected.length === 0)) {
    return null;
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Last upload</CardTitle>
        <CardDescription>
          {result.routed.length} routed · {result.rejected.length} rejected
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="flex flex-col gap-2">
          {result.routed.map((r, i) => (
            <li
              key={`${r.name}-routed-${i}`}
              className="flex items-center justify-between gap-3 rounded-md border border-border bg-card px-3 py-2 text-sm"
            >
              <div className="flex min-w-0 items-center gap-3">
                <CheckCircle2 className="size-4 shrink-0 text-primary" />
                <span className="truncate font-mono">{r.name}</span>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <Badge variant="outline">{r.type}</Badge>
                <Badge>{r.slot}</Badge>
              </div>
            </li>
          ))}
          {result.rejected.map((r, i) => (
            <li
              key={`${r.name}-rej-${i}`}
              className="flex items-center justify-between gap-3 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm"
            >
              <div className="flex min-w-0 items-center gap-3">
                <FileWarning className="size-4 shrink-0 text-destructive" />
                <span className="truncate font-mono">{r.name}</span>
              </div>
              <span className="max-w-[50%] truncate text-right text-xs text-muted-foreground">
                {r.reason}
              </span>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Artifacts
// ---------------------------------------------------------------------------

function ArtifactCard({
  title,
  slot,
  files,
  loading,
  onDownload,
  onPromptUpload,
}: {
  title: string;
  slot: WorkspaceArtifactSlot;
  files: FileSummary[];
  loading: boolean;
  onDownload: (
    slot: WorkspaceArtifactSlot,
    filename: string,
    iterationId?: string
  ) => void;
  onPromptUpload: () => void;
}) {
  const displayFiles = useMemo(
    () => [...files].sort((a, b) => b.mtime - a.mtime).slice(0, 12),
    [files]
  );

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <FolderOpen className="size-4" />
            {title}
          </CardTitle>
          <Badge variant="outline">{files.length}</Badge>
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-12 w-full" />
        ) : displayFiles.length === 0 ? (
          <Empty className="border-0 p-0 md:p-0">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <FolderOpen />
              </EmptyMedia>
              <EmptyTitle>No {title.toLowerCase()} yet</EmptyTitle>
              <EmptyDescription>
                Drop files into the dropzone above and they'll be routed here.
              </EmptyDescription>
            </EmptyHeader>
            <EmptyContent>
              <Button variant="outline" size="sm" onClick={onPromptUpload}>
                <Upload data-icon="inline-start" />
                Upload files
              </Button>
            </EmptyContent>
          </Empty>
        ) : (
          <ul className="flex flex-col">
            {displayFiles.map((f, i) => (
              <li key={f.path}>
                {i > 0 ? <Separator /> : null}
                <button
                  type="button"
                  className="flex w-full items-center justify-between gap-3 py-2 text-left text-sm transition-colors hover:bg-accent/40"
                  title={`Download ${f.name}`}
                  onClick={() =>
                    onDownload(slot, f.name, extractIterationIdFromFilePath(f.path))
                  }
                >
                  <div className="flex min-w-0 items-center gap-2">
                    <FileIcon className="size-4 shrink-0 text-muted-foreground" />
                    <span className="truncate font-mono">{f.name}</span>
                  </div>
                  <div className="flex shrink-0 items-center gap-2 text-xs text-muted-foreground">
                    <span>{(f.size / 1024).toFixed(1)} KB</span>
                    <Download className="size-3.5" />
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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
    <div className="flex flex-col gap-1">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="text-lg font-semibold">{display}</p>
    </div>
  );
}

function extractIterationIdFromFilePath(filePath: string): string | undefined {
  const match = /[\\/]iterations[\\/]([^\\/]+)[\\/]/i.exec(filePath);
  return match?.[1];
}
