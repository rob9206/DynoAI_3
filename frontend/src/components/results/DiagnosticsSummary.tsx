import { useState } from 'react';
import { ChevronDown, ChevronUp, Grid3X3, Percent, AlertTriangle, BarChart3 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardAction } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { MetricCard } from './MetricCard';
import { DiagnosticsDetail, DiagnosticsData, RunMetadata } from './DiagnosticsDetail';

export type { DiagnosticsData, RunMetadata };

export interface DiagnosticsSummaryProps {
  data: DiagnosticsData | null;
  isLoading?: boolean;
  error?: Error | null;
  expandable?: boolean;
  defaultExpanded?: boolean;
  runMetadata?: RunMetadata;
  className?: string;
}

type MetricStatus = 'success' | 'warning' | 'error' | 'neutral';

function getMetricStatus(
  metric: string,
  value: number,
  data: DiagnosticsData
): MetricStatus {
  switch (metric) {
    case 'cellsClamped':
      if (value === 0) return 'success';
      if (data.totalCells === 0) return 'neutral';
      if (value / data.totalCells > 0.1) return 'error';
      return 'warning';

    case 'maxCorrection':
      if (Math.abs(value) > data.clampLimit) return 'warning';
      return 'neutral';

    case 'coveragePercent':
      if (value >= 70) return 'success';
      if (value >= 50) return 'neutral';
      return 'warning';

    default:
      return 'neutral';
  }
}

function formatMaxCorrection(value: number): string {
  return `±${Math.abs(value).toFixed(1)}%`;
}

function LoadingSkeleton() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Skeleton className="h-5 w-40" />
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="space-y-2">
              <Skeleton className="h-16 w-full" />
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function ErrorDisplay({ error }: { error: Error }) {
  return (
    <Card className="border-destructive">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-destructive">
          <AlertTriangle className="h-5 w-5" />
          Error Loading Diagnostics
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">{error.message}</p>
      </CardContent>
    </Card>
  );
}

export function DiagnosticsSummary({
  data,
  isLoading = false,
  error = null,
  expandable = true,
  defaultExpanded = false,
  runMetadata,
  className,
}: DiagnosticsSummaryProps): JSX.Element {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  if (isLoading) {
    return <LoadingSkeleton />;
  }

  if (error) {
    return <ErrorDisplay error={error} />;
  }

  if (!data) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle>Diagnostics Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No diagnostics data available.</p>
        </CardContent>
      </Card>
    );
  }

  const cellsClampedStatus = getMetricStatus('cellsClamped', data.cellsClamped, data);
  const maxCorrectionStatus = getMetricStatus('maxCorrection', data.maxCorrection, data);
  const coverageStatus = getMetricStatus('coveragePercent', data.coveragePercent, data);

  const content = (
    <>
      <CardHeader className="pb-4">
        <CardTitle className="flex items-center gap-2">
          Diagnostics Summary
        </CardTitle>
        {expandable && (
          <CardAction>
            <CollapsibleTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsExpanded(!isExpanded)}
                className="gap-1"
              >
                {isExpanded ? (
                  <>
                    Collapse <ChevronUp className="h-4 w-4" />
                  </>
                ) : (
                  <>
                    Expand <ChevronDown className="h-4 w-4" />
                  </>
                )}
              </Button>
            </CollapsibleTrigger>
          </CardAction>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Primary Metrics Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard
            label="Cells Corrected"
            value={data.cellsCorrected}
            unit="cells"
            icon={<Grid3X3 className="h-3.5 w-3.5" />}
            status="neutral"
            tooltip="Number of VE table cells that received corrections"
          />
          <MetricCard
            label="Max Correction"
            value={formatMaxCorrection(data.maxCorrection)}
            icon={<Percent className="h-3.5 w-3.5" />}
            status={maxCorrectionStatus}
            tooltip={`Largest absolute correction applied. Clamp limit is ±${data.clampLimit}%`}
          />
          <MetricCard
            label="Clamped"
            value={data.cellsClamped}
            unit="cells"
            icon={<AlertTriangle className="h-3.5 w-3.5" />}
            status={cellsClampedStatus}
            tooltip="Cells that hit the clamp limit and were constrained"
          />
          <MetricCard
            label="Coverage"
            value={`${data.coveragePercent.toFixed(1)}%`}
            icon={<BarChart3 className="h-3.5 w-3.5" />}
            status={coverageStatus}
            tooltip="Percentage of VE table cells with data coverage"
          />
        </div>

        {/* Expandable Details */}
        {expandable && (
          <CollapsibleContent className="overflow-hidden data-[state=closed]:animate-collapsible-up data-[state=open]:animate-collapsible-down">
            <div className="pt-4 border-t border-border">
              <DiagnosticsDetail data={data} runMetadata={runMetadata} />
            </div>
          </CollapsibleContent>
        )}

        {/* Non-expandable Details */}
        {!expandable && (
          <div className="pt-4 border-t border-border">
            <DiagnosticsDetail data={data} runMetadata={runMetadata} />
          </div>
        )}
      </CardContent>
    </>
  );

  if (expandable) {
    return (
      <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
        <Card className={cn('transition-all duration-200', className)}>
          {content}
        </Card>
      </Collapsible>
    );
  }

  return (
    <Card className={cn('transition-all duration-200', className)}>
      {content}
    </Card>
  );
}

export default DiagnosticsSummary;
