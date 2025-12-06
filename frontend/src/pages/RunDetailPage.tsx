/**
 * Run detail page showing full run information
 */

import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Clock,
  FileText,
  Download,
  AlertCircle,
  CheckCircle2,
  Loader2,
  Activity,
  Thermometer,
  Gauge,
  Table,
  Flame,
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Skeleton } from '../components/ui/skeleton';
import { Progress } from '../components/ui/progress';
import { useJetstreamRun } from '../hooks/useJetstream';
import { useJetstreamProgress } from '../hooks/useJetstreamProgress';
import { downloadRunFile } from '../api/jetstream';
import type { RunStatus } from '../api/jetstream';
import { VEHeatmap } from '../components/results/VEHeatmap';
import { VEHeatmapLegend } from '../components/results/VEHeatmapLegend';
import { useVEData } from '../hooks/useVEData';

const statusConfig: Record<
  RunStatus,
  { label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline' }
> = {
  pending: { label: 'Pending', variant: 'outline' },
  downloading: { label: 'Downloading', variant: 'secondary' },
  converting: { label: 'Converting', variant: 'secondary' },
  validating: { label: 'Validating', variant: 'secondary' },
  processing: { label: 'Processing', variant: 'default' },
  complete: { label: 'Complete', variant: 'default' },
  error: { label: 'Error', variant: 'destructive' },
};

export default function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();

  const isProcessing = (status: RunStatus) =>
    ['downloading', 'converting', 'validating', 'processing'].includes(status);

  // Fetch run data with auto-refresh when processing
  const { data: run, isLoading, error } = useJetstreamRun(
    runId,
    runId ? 5000 : undefined // Refresh every 5s
  );

  // Subscribe to progress events when processing
  const progress = useJetstreamProgress(
    run && isProcessing(run.status) ? runId : undefined
  );

  const handleDownload = async (filename: string) => {
    if (!runId) return;
    try {
      const blob = await downloadRunFile(runId, filename);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      console.error('Download failed:', err);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-32" />
        <Skeleton className="h-48 w-full" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Skeleton className="h-64" />
          <Skeleton className="h-64" />
        </div>
      </div>
    );
  }

  if (error ?? !run) {
    return (
      <div className="text-center py-12">
        <AlertCircle className="h-12 w-12 mx-auto text-destructive mb-4" />
        <h2 className="text-xl font-semibold">Run Not Found</h2>
        <p className="text-muted-foreground mt-2">
          The run you're looking for doesn't exist or has been deleted.
        </p>
        <Button variant="outline" onClick={() => void navigate('/jetstream')} className="mt-4">
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Feed
        </Button>
      </div>
    );
  }

  const status = statusConfig[run.status] ?? statusConfig.pending;
  const metadata = run.jetstream_metadata;
  const processing = isProcessing(run.status);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="space-y-2">
          <Button variant="ghost" size="sm" onClick={() => void navigate(-1)}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
          <h1 className="text-2xl font-bold font-mono">{run.run_id}</h1>
          <div className="flex items-center gap-3">
            <Badge variant={status.variant}>{status.label}</Badge>
            <Badge variant="outline">
              {run.source === 'jetstream' ? 'Jetstream' : 'Manual Upload'}
            </Badge>
            {run.jetstream_id && (
              <span className="text-sm text-muted-foreground">
                JS ID: {run.jetstream_id}
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Clock className="h-4 w-4" />
          {new Date(run.created_at).toLocaleString()}
        </div>
      </div>

      {/* Processing Progress */}
      {processing && (
        <Card className="border-primary/50 bg-primary/5">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2">
              <Loader2 className="h-5 w-5 animate-spin" />
              Processing in Progress
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>{progress.stage ?? run.current_stage ?? 'Processing'}</span>
                <span>{progress.progress ?? run.progress_percent ?? 0}%</span>
              </div>
              <Progress value={progress.progress ?? run.progress_percent ?? 0} />
              {progress.substage && (
                <p className="text-xs text-muted-foreground">{progress.substage}</p>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Error Display */}
      {run.error && (
        <Card className="border-destructive/50 bg-destructive/5">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-destructive">
              <AlertCircle className="h-5 w-5" />
              Processing Error
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="font-medium">{run.error.code}</p>
            <p className="text-sm text-muted-foreground mt-1">{run.error.message}</p>
            <p className="text-xs text-muted-foreground mt-2">
              Failed at stage: {run.error.stage}
            </p>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Metadata */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Run Metadata
            </CardTitle>
            <CardDescription>Information about this dyno run</CardDescription>
          </CardHeader>
          <CardContent>
            {metadata ? (
              <dl className="space-y-3">
                {metadata.vehicle && (
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Vehicle</dt>
                    <dd className="font-medium">{metadata.vehicle}</dd>
                  </div>
                )}
                {metadata.dyno_type && (
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Dyno Type</dt>
                    <dd className="font-medium">{metadata.dyno_type}</dd>
                  </div>
                )}
                {metadata.engine_type && (
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Engine</dt>
                    <dd className="font-medium">{metadata.engine_type}</dd>
                  </div>
                )}
                {metadata.peak_hp != null && (
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Peak HP</dt>
                    <dd className="font-medium">{metadata.peak_hp.toFixed(1)} hp</dd>
                  </div>
                )}
                {metadata.peak_torque != null && (
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Peak Torque</dt>
                    <dd className="font-medium">{metadata.peak_torque.toFixed(1)} ft-lb</dd>
                  </div>
                )}
                {metadata.duration_seconds != null && (
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Duration</dt>
                    <dd className="font-medium">{metadata.duration_seconds}s</dd>
                  </div>
                )}
              </dl>
            ) : (
              <p className="text-muted-foreground text-center py-4">
                No metadata available
              </p>
            )}
          </CardContent>
        </Card>

        {/* Environment */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Thermometer className="h-5 w-5" />
              Environment
            </CardTitle>
            <CardDescription>Conditions during the run</CardDescription>
          </CardHeader>
          <CardContent>
            {metadata && (metadata.ambient_temp_f != null || metadata.ambient_pressure_inhg != null) ? (
              <dl className="space-y-3">
                {metadata.ambient_temp_f != null && (
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Temperature</dt>
                    <dd className="font-medium">{metadata.ambient_temp_f.toFixed(1)}°F</dd>
                  </div>
                )}
                {metadata.ambient_pressure_inhg != null && (
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Pressure</dt>
                    <dd className="font-medium">
                      {metadata.ambient_pressure_inhg.toFixed(2)} inHg
                    </dd>
                  </div>
                )}
                {metadata.humidity_percent != null && (
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Humidity</dt>
                    <dd className="font-medium">{metadata.humidity_percent.toFixed(0)}%</dd>
                  </div>
                )}
              </dl>
            ) : (
              <p className="text-muted-foreground text-center py-4">
                No environment data available
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Output Files */}
      {run.status === 'complete' && run.output_files && run.output_files.length > 0 && (
        <div>
          <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Output Files
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {run.output_files.map((file) => {
              const fileIcon = file.name.endsWith('.csv') ? (
                <Table className="h-8 w-8 text-blue-500" />
              ) : file.name.endsWith('.json') ? (
                <FileText className="h-8 w-8 text-green-500" />
              ) : file.name.includes('Anomaly') ? (
                <AlertCircle className="h-8 w-8 text-yellow-500" />
              ) : (
                <FileText className="h-8 w-8 text-purple-500" />
              );

              return (
                <Card
                  key={file.name}
                  className="group hover:shadow-lg hover:scale-[1.02] transition-all duration-200 cursor-pointer overflow-hidden"
                  onClick={() => void handleDownload(file.name)}
                >
                  <CardContent className="p-6">
                    <div className="flex items-start justify-between mb-4">
                      <div className="p-3 bg-primary/10 rounded-lg group-hover:bg-primary/20 transition-colors">
                        {fileIcon}
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={(e) => {
                          e.stopPropagation();
                          void handleDownload(file.name);
                        }}
                      >
                        <Download className="h-4 w-4" />
                      </Button>
                    </div>

                    <div className="space-y-2">
                      <h3 className="font-semibold text-sm text-foreground line-clamp-2 min-h-[2.5rem]">
                        {file.name}
                      </h3>

                      <div className="flex items-center justify-between">
                        <Badge variant="secondary" className="text-xs font-normal">
                          {file.name.split('.').pop()?.toUpperCase() ?? 'FILE'}
                        </Badge>
                        <span className="text-xs text-muted-foreground font-mono">
                          {(file.size / 1024).toFixed(1)} KB
                        </span>
                      </div>
                    </div>

                    <div className="mt-4 pt-4 border-t border-border">
                      <div className="flex items-center text-xs text-primary font-medium group-hover:translate-x-1 transition-transform">
                        <Download className="h-3 w-3 mr-1" />
                        Click to download
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      )}

      {/* Placeholder sections for future features */}
      {run.status === 'complete' && (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Gauge className="h-5 w-5" />
                VE Heatmap
              </CardTitle>
              <CardDescription>Volumetric Efficiency corrections</CardDescription>
            </CardHeader>
            <CardContent>
              <VEHeatmapWithData runId={run.run_id} />
            </CardContent>
          </Card>

          {/* Decel Fuel Management Results */}
          {run.output_files?.some((f) => f.name === 'Decel_Fuel_Overlay.csv') && (
            <DecelResultsCard runId={run.run_id} outputFiles={run.output_files} onDownload={handleDownload} />
          )}

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5" />
                Actions
              </CardTitle>
              <CardDescription>Apply or rollback VE changes</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex gap-3">
                <Button disabled>Apply VE Changes</Button>
                <Button variant="outline" disabled>
                  Rollback
                </Button>
              </div>
              <p className="text-sm text-muted-foreground mt-2">
                VE apply/rollback functionality coming soon
              </p>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

/**
 * Decel Fuel Management Results Card
 */
interface DecelResultsCardProps {
  runId: string;
  outputFiles: Array<{ name: string; size: number; url: string }>;
  onDownload: (filename: string) => void;
}

function DecelResultsCard({ runId, outputFiles, onDownload }: DecelResultsCardProps) {
  const decelOverlay = outputFiles.find((f) => f.name === 'Decel_Fuel_Overlay.csv');
  const decelReport = outputFiles.find((f) => f.name === 'Decel_Analysis_Report.json');

  return (
    <Card className="border-orange-500/30 bg-orange-500/5">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Flame className="h-5 w-5 text-orange-500" />
          Decel Fuel Management
        </CardTitle>
        <CardDescription>
          Automated deceleration popping elimination
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center gap-2 text-sm">
          <CheckCircle2 className="h-4 w-4 text-green-500" />
          <span>Decel analysis completed successfully</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {decelOverlay && (
            <Button
              variant="outline"
              className="justify-start"
              onClick={() => onDownload(decelOverlay.name)}
            >
              <Download className="h-4 w-4 mr-2" />
              <div className="text-left">
                <div className="font-medium">VE Overlay</div>
                <div className="text-xs text-muted-foreground">
                  {(decelOverlay.size / 1024).toFixed(1)} KB
                </div>
              </div>
            </Button>
          )}
          {decelReport && (
            <Button
              variant="outline"
              className="justify-start"
              onClick={() => onDownload(decelReport.name)}
            >
              <FileText className="h-4 w-4 mr-2" />
              <div className="text-left">
                <div className="font-medium">Analysis Report</div>
                <div className="text-xs text-muted-foreground">
                  {(decelReport.size / 1024).toFixed(1)} KB
                </div>
              </div>
            </Button>
          )}
        </div>

        <p className="text-xs text-muted-foreground">
          Apply the VE overlay to closed-throttle cells to eliminate exhaust popping during deceleration.
        </p>
      </CardContent>
    </Card>
  );
}

/**
 * VE Heatmap component with data fetching
 */
function VEHeatmapWithData({ runId }: { runId: string }) {
  const { data: veData, isLoading, error } = useVEData(runId);

  if (isLoading) {
    return (
      <div className="h-64 flex items-center justify-center">
        <div className="flex flex-col items-center gap-2">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground">Loading VE data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-64 bg-muted/50 rounded-lg flex items-center justify-center">
        <div className="flex flex-col items-center gap-2 text-center px-4">
          <AlertCircle className="h-8 w-8 text-muted-foreground" />
          <p className="text-muted-foreground">
            Unable to load VE data: {error instanceof Error ? error.message : 'Unknown error'}
          </p>
        </div>
      </div>
    );
  }

  if (!veData?.before || veData.before.length === 0) {
    return (
      <div className="h-64 bg-muted/50 rounded-lg flex items-center justify-center">
        <div className="flex flex-col items-center gap-2">
          <FileText className="h-8 w-8 text-muted-foreground" />
          <p className="text-muted-foreground">No VE correction data available</p>
        </div>
      </div>
    );
  }

  // Calculate corrections (delta = after - before)
  const corrections = veData.before.map((row, rowIdx) =>
    row.map((beforeVal, colIdx) => veData.after[rowIdx][colIdx] - beforeVal)
  );

  return (
    <div className="space-y-4">
      <VEHeatmapLegend clampLimit={7} />
      <VEHeatmap
        data={corrections}
        rowLabels={veData.rpm.map(String)}
        colLabels={veData.load.map(String)}
        clampLimit={7}
        showClampIndicators={true}
        showValues={true}
      />
    </div>
  );
}
