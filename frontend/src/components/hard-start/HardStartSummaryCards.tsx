import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { HardStartSummary } from '@/api/hardStart';

interface HardStartSummaryCardsProps {
  summary: HardStartSummary;
}

function severityBadgeVariant(severity: HardStartSummary['result_severity']): 'default' | 'secondary' | 'destructive' {
  if (severity === 'critical') {
    return 'destructive';
  }
  if (severity === 'warning') {
    return 'secondary';
  }
  return 'default';
}

function formatSeconds(value: number | null): string {
  if (value == null) {
    return 'N/A';
  }
  return `${value.toFixed(2)} s`;
}

export function HardStartSummaryCards({ summary }: HardStartSummaryCardsProps) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm text-muted-foreground">Result</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-between gap-2">
          <span className="text-sm font-medium">{summary.result_label}</span>
          <Badge variant={severityBadgeVariant(summary.result_severity)}>{summary.result}</Badge>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm text-muted-foreground">Min Voltage</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-2xl font-semibold">{summary.min_voltage_v.toFixed(2)} V</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm text-muted-foreground">Peak RPM</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-2xl font-semibold">{summary.peak_rpm.toLocaleString()}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm text-muted-foreground">Time To Catch</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-2xl font-semibold">{formatSeconds(summary.time_to_catch_s)}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm text-muted-foreground">Crank Duration</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-2xl font-semibold">{formatSeconds(summary.crank_duration_s)}</p>
        </CardContent>
      </Card>
    </div>
  );
}

