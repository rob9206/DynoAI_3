import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { CrankSegment, CrankTimeSample } from '@/api/hardStart';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

interface HardStartChartsProps {
  timeSeries: CrankTimeSample[];
  segments: CrankSegment[];
}

interface LineSeriesConfig {
  dataKey: keyof CrankTimeSample;
  label: string;
  color: string;
}

const SEGMENT_FILL: Record<CrankSegment['type'], string> = {
  NO_START: '#ef4444',
  CATCH: '#f59e0b',
  RUN: '#22c55e',
};

function getSeriesValue(value: unknown): string {
  if (typeof value === 'number') {
    return value.toFixed(2);
  }
  return 'N/A';
}

function HardStartChartPanel({
  title,
  yAxisLabel,
  lines,
  timeSeries,
  segments,
}: {
  title: string;
  yAxisLabel: string;
  lines: LineSeriesConfig[];
  timeSeries: CrankTimeSample[];
  segments: CrankSegment[];
}) {
  return (
    <div className="grid gap-2">
      <p className="text-sm font-medium text-muted-foreground">{title}</p>
      <div className="h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={timeSeries} margin={{ top: 8, right: 12, left: 4, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="t_s"
              tickFormatter={(value: number) => `${value.toFixed(1)}s`}
              tickLine={false}
            />
            <YAxis
              tickLine={false}
              width={56}
              label={{
                value: yAxisLabel,
                angle: -90,
                position: 'insideLeft',
              }}
            />
            <Tooltip
              labelFormatter={(value: number) => `t=${value.toFixed(2)}s`}
              formatter={(value: unknown, name: string) => [getSeriesValue(value), name]}
            />
            <Legend />
            {segments.map((segment) => (
              <ReferenceArea
                key={`${title}-${segment.type}-${segment.start_s}-${segment.end_s}`}
                x1={segment.start_s}
                x2={segment.end_s}
                fill={SEGMENT_FILL[segment.type]}
                fillOpacity={0.08}
              />
            ))}
            {lines.map((line) => (
              <Line
                key={`${title}-${line.dataKey}`}
                type="monotone"
                dataKey={line.dataKey}
                name={line.label}
                stroke={line.color}
                dot={false}
                strokeWidth={2}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function HardStartCharts({ timeSeries, segments }: HardStartChartsProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Time-Series Channels</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-8">
        <HardStartChartPanel
          title="RPM"
          yAxisLabel="RPM"
          lines={[{ dataKey: 'rpm', label: 'RPM', color: '#3b82f6' }]}
          timeSeries={timeSeries}
          segments={segments}
        />
        <HardStartChartPanel
          title="Battery Voltage"
          yAxisLabel="V"
          lines={[{ dataKey: 'vbatt', label: 'Vbatt', color: '#a855f7' }]}
          timeSeries={timeSeries}
          segments={segments}
        />
        <HardStartChartPanel
          title="MAP"
          yAxisLabel="kPa"
          lines={[{ dataKey: 'map_kpa', label: 'MAP kPa', color: '#14b8a6' }]}
          timeSeries={timeSeries}
          segments={segments}
        />
        <HardStartChartPanel
          title="Spark"
          yAxisLabel="deg"
          lines={[
            { dataKey: 'spark_f', label: 'Spark F', color: '#f97316' },
            { dataKey: 'spark_r', label: 'Spark R', color: '#f43f5e' },
          ]}
          timeSeries={timeSeries}
          segments={segments}
        />
        <HardStartChartPanel
          title="Injector Pulse Width"
          yAxisLabel="ms"
          lines={[
            { dataKey: 'inj_pw_f_ms', label: 'Inj PW F', color: '#10b981' },
            { dataKey: 'inj_pw_r_ms', label: 'Inj PW R', color: '#22c55e' },
          ]}
          timeSeries={timeSeries}
          segments={segments}
        />
      </CardContent>
    </Card>
  );
}

