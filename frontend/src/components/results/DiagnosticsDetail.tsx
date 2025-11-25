import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';

export interface DiagnosticsData {
  cellsCorrected: number;
  totalCells: number;
  maxCorrection: number;
  minCorrection: number;
  avgCorrection: number;
  cellsClamped: number;
  clampLimit: number;
  coveragePercent: number;
  processingTimeMs: number;
  dataPoints: number;
  kernelsApplied: string[];
}

export interface RunMetadata {
  source: 'jetstream' | 'manual_upload';
  vehicle?: string;
  timestamp: string;
  operator?: string;
}

export interface DiagnosticsDetailProps {
  data: DiagnosticsData;
  runMetadata?: RunMetadata;
  className?: string;
}

function formatTime(ms: number): string {
  if (ms < 1000) {
    return `${ms}ms`;
  }
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatNumber(num: number): string {
  return num.toLocaleString();
}

function formatPercent(num: number): string {
  const sign = num >= 0 ? '+' : '';
  return `${sign}${num.toFixed(1)}%`;
}

function formatDate(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

function getSourceDisplay(source: RunMetadata['source']): string {
  switch (source) {
    case 'jetstream':
      return 'Jetstream';
    case 'manual_upload':
      return 'Manual Upload';
    default:
      return source;
  }
}

export function DiagnosticsDetail({
  data,
  runMetadata,
  className,
}: DiagnosticsDetailProps): JSX.Element {
  return (
    <div className={cn('space-y-4', className)}>
      {/* Additional Details Section */}
      <div>
        <h4 className="text-sm font-medium text-foreground mb-3">
          Additional Details
        </h4>
        <Separator className="mb-3" />
        <div className="grid grid-cols-2 md:grid-cols-3 gap-y-3 gap-x-6 text-sm">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Total Cells:</span>
            <span className="font-mono">{formatNumber(data.totalCells)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Avg Correction:</span>
            <span className="font-mono">{formatPercent(data.avgCorrection)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Min Correction:</span>
            <span className="font-mono">{formatPercent(data.minCorrection)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Processing Time:</span>
            <span className="font-mono">{formatTime(data.processingTimeMs)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Data Points:</span>
            <span className="font-mono">{formatNumber(data.dataPoints)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Clamp Limit:</span>
            <span className="font-mono">±{data.clampLimit}%</span>
          </div>
          <div className="col-span-2 md:col-span-3 flex justify-between items-center">
            <span className="text-muted-foreground">Kernels Applied:</span>
            <div className="flex gap-1.5 flex-wrap justify-end">
              {data.kernelsApplied.length > 0 ? (
                data.kernelsApplied.map((kernel) => (
                  <Badge key={kernel} variant="secondary" className="font-mono text-xs">
                    {kernel}
                  </Badge>
                ))
              ) : (
                <span className="text-muted-foreground text-xs">None</span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Run Information Section */}
      {runMetadata && (
        <div>
          <h4 className="text-sm font-medium text-foreground mb-3">
            Run Information
          </h4>
          <Separator className="mb-3" />
          <div className="grid grid-cols-2 gap-y-3 gap-x-6 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Source:</span>
              <span>{getSourceDisplay(runMetadata.source)}</span>
            </div>
            {runMetadata.vehicle && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Vehicle:</span>
                <span>{runMetadata.vehicle}</span>
              </div>
            )}
            <div className="flex justify-between">
              <span className="text-muted-foreground">Timestamp:</span>
              <span>{formatDate(runMetadata.timestamp)}</span>
            </div>
            {runMetadata.operator && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Operator:</span>
                <span>{runMetadata.operator}</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default DiagnosticsDetail;
