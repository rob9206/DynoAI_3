/**
 * Run detail page showing full run information
 */

import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
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
  ChevronDown,
  ChevronRight,
  Eye,
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
import type { RunStatus, OutputFile } from '../api/jetstream';
import { VEHeatmap } from '../components/results/VEHeatmap';
import { VEHeatmapLegend } from '../components/results/VEHeatmapLegend';
import { useVEData } from '../hooks/useVEData';
import { FilePreview, useFileContent } from '../components/results/FilePreview';
import { SessionReplayViewer } from '../components/session-replay';
import { cn } from '../lib/utils';

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
      toast.success(`Downloaded ${filename}`);
    } catch (err) {
      console.error('Download failed:', err);
      toast.error(`Failed to download ${filename}`);
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

      {/* Output Files with Visual Previews */}
      {run.status === 'complete' && run.output_files && run.output_files.length > 0 && (
        <div>
          <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Output Files
          </h2>
          <div className="space-y-4">
            {run.output_files.map((file) => (
              <ExpandableFileCard
                key={file.name}
                file={file}
                runId={run.run_id}
                onDownload={handleDownload}
              />
            ))}
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

          {/* Per-Cylinder Balance Results */}
          {run.output_files?.some((f) => f.name === 'Cylinder_Balance_Report.json') && (
            <BalanceResultsCard runId={run.run_id} outputFiles={run.output_files} onDownload={handleDownload} />
          )}

          {/* Session Replay */}
          {run.output_files?.some((f) => f.name === 'session_replay.json') && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Activity className="h-5 w-5" />
                  Session Replay
                </CardTitle>
                <CardDescription>
                  Timeline of all decisions made during tuning
                </CardDescription>
              </CardHeader>
              <CardContent>
                <SessionReplayViewer runId={run.run_id} />
              </CardContent>
            </Card>
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
 * Expandable file card with visual preview
 */
function ExpandableFileCard({
  file,
  runId,
  onDownload,
}: {
  file: OutputFile;
  runId: string;
  onDownload: (filename: string) => void;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const { content, isLoading, error } = useFileContent(
    isExpanded ? runId : undefined,
    isExpanded ? file.name : undefined
  );

  const fileIcon = file.name.endsWith('.csv') ? (
    <Table className="h-5 w-5 text-blue-500" />
  ) : file.name.endsWith('.json') ? (
    <FileText className="h-5 w-5 text-green-500" />
  ) : file.name.includes('Anomaly') ? (
    <AlertCircle className="h-5 w-5 text-yellow-500" />
  ) : (
    <FileText className="h-5 w-5 text-purple-500" />
  );

  const fileType = file.name.split('.').pop()?.toUpperCase() ?? 'FILE';
  const fileDescription = getFileDescription(file.name);

  return (
    <Card className={cn(
      "transition-all duration-200",
      isExpanded && "ring-1 ring-primary/50"
    )}>
      <div
        className="flex items-center justify-between p-4 cursor-pointer hover:bg-muted/30 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-4">
          <div className="p-2 bg-primary/10 rounded-lg">
            {fileIcon}
          </div>
          <div>
            <h3 className="font-semibold text-sm text-foreground">{file.name}</h3>
            <p className="text-xs text-muted-foreground mt-0.5">{fileDescription}</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Badge variant="secondary" className="text-xs font-normal">
            {fileType}
          </Badge>
          <span className="text-xs text-muted-foreground font-mono">
            {(file.size / 1024).toFixed(1)} KB
          </span>
          <Button
            variant="ghost"
            size="icon"
            onClick={(e) => {
              e.stopPropagation();
              onDownload(file.name);
            }}
          >
            <Download className="h-4 w-4" />
          </Button>
          <div className="text-muted-foreground">
            {isExpanded ? (
              <ChevronDown className="h-5 w-5" />
            ) : (
              <ChevronRight className="h-5 w-5" />
            )}
          </div>
        </div>
      </div>

      {isExpanded && (
        <div className="border-t border-border">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-3 text-xs text-muted-foreground">
              <Eye className="h-3 w-3" />
              <span>Data Preview</span>
            </div>
            <FilePreview
              filename={file.name}
              content={content}
              isLoading={isLoading}
              error={error}
            />
          </CardContent>
        </div>
      )}
    </Card>
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
 * Get human-readable description for a file
 */
function getFileDescription(filename: string): string {
  const descriptions: Record<string, string> = {
    'VE_Correction_Delta_DYNO.csv': 'Volumetric Efficiency correction values',
    'Spark_Adjust_Suggestion_Front.csv': 'Front cylinder spark advance suggestions',
    'Spark_Adjust_Suggestion_Rear.csv': 'Rear cylinder spark advance suggestions',
    'AFR_Error_Map_Front.csv': 'Front cylinder air-fuel ratio error mapping',
    'AFR_Error_Map_Rear.csv': 'Rear cylinder air-fuel ratio error mapping',
    'Coverage_Front.csv': 'Front cylinder data coverage analysis',
    'Coverage_Rear.csv': 'Rear cylinder data coverage analysis',
    'VE_Delta_PasteReady.txt': 'VE corrections formatted for tuning software',
    'Spark_Front_PasteReady.txt': 'Front spark values formatted for tuning software',
    'Spark_Rear_PasteReady.txt': 'Rear spark values formatted for tuning software',
    'Diagnostics_Report.txt': 'Analysis summary and diagnostic metrics',
    'Anomaly_Hypotheses.json': 'Detected anomalies and possible causes',
  };

  return descriptions[filename] ?? 'Analysis output file';
}

/**
 * Balance Results Card Component
 */
interface BalanceResultsCardProps {
  runId: string;
  outputFiles: Array<{ name: string; size: number; url: string }>;
  onDownload: (filename: string) => void;
}

function BalanceResultsCard({ runId, outputFiles, onDownload }: BalanceResultsCardProps) {
  const frontFactor = outputFiles.find((f) => f.name === 'Front_Balance_Factor.csv');
  const rearFactor = outputFiles.find((f) => f.name === 'Rear_Balance_Factor.csv');
  const balanceReport = outputFiles.find((f) => f.name === 'Cylinder_Balance_Report.json');

  return (
    <Card className="border-blue-500/30 bg-blue-500/5">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Activity className="h-5 w-5 text-blue-500" />
          Per-Cylinder Auto-Balancing
        </CardTitle>
        <CardDescription>
          Automated AFR equalization between front and rear cylinders
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center gap-2 text-sm">
          <CheckCircle2 className="h-4 w-4 text-green-500" />
          <span>Cylinder balance analysis completed successfully</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {frontFactor && (
            <Button
              variant="outline"
              className="justify-start"
              onClick={() => onDownload(frontFactor.name)}
            >
              <Download className="h-4 w-4 mr-2" />
              <div className="text-left">
                <div className="font-medium">Front VE Factor</div>
                <div className="text-xs text-muted-foreground">
                  {(frontFactor.size / 1024).toFixed(1)} KB
                </div>
              </div>
            </Button>
          )}
          {rearFactor && (
            <Button
              variant="outline"
              className="justify-start"
              onClick={() => onDownload(rearFactor.name)}
            >
              <Download className="h-4 w-4 mr-2" />
              <div className="text-left">
                <div className="font-medium">Rear VE Factor</div>
                <div className="text-xs text-muted-foreground">
                  {(rearFactor.size / 1024).toFixed(1)} KB
                </div>
              </div>
            </Button>
          )}
          {balanceReport && (
            <Button
              variant="outline"
              className="justify-start"
              onClick={() => onDownload(balanceReport.name)}
            >
              <FileText className="h-4 w-4 mr-2" />
              <div className="text-left">
                <div className="font-medium">Balance Report</div>
                <div className="text-xs text-muted-foreground">
                  {(balanceReport.size / 1024).toFixed(1)} KB
                </div>
              </div>
            </Button>
          )}
        </div>

        <p className="text-xs text-muted-foreground">
          Apply front and rear correction factors simultaneously using dual-cylinder VE apply to equalize AFR between cylinders.
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
