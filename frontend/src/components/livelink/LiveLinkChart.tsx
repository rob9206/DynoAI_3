/**
 * LiveLinkChart - Real-time line chart for channel history
 */

import { useMemo } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';

interface LiveLinkChartProps {
    title: string;
    data: { time: number; value: number }[];
    color?: string;
    units?: string;
    yMin?: number;
    yMax?: number;
    targetValue?: number;
    showGrid?: boolean;
    height?: number;
}

export function LiveLinkChart({
    title,
    data,
    color = '#4ade80',
    units = '',
    yMin,
    yMax,
    targetValue,
    showGrid = false,
    height = 200,
}: LiveLinkChartProps) {
    // Transform data for chart - use relative time
    const chartData = useMemo(() => {
        if (data.length === 0) return [];

        const startTime = data[0].time;
        return data.map((point, index) => ({
            index,
            time: ((point.time - startTime) / 1000).toFixed(1), // seconds from start
            value: point.value,
        }));
    }, [data]);

    // Calculate domain
    const domain = useMemo(() => {
        if (data.length === 0) return { min: 0, max: 100 };

        const values = data.map(d => d.value);
        const dataMin = Math.min(...values);
        const dataMax = Math.max(...values);
        const padding = (dataMax - dataMin) * 0.1 || 10;

        return {
            min: yMin ?? Math.floor(dataMin - padding),
            max: yMax ?? Math.ceil(dataMax + padding),
        };
    }, [data, yMin, yMax]);

    // Get current value
    const currentValue = data.length > 0 ? data[data.length - 1].value : 0;

    return (
        <Card className="border-border/50">
            <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-medium text-muted-foreground">
                        {title}
                    </CardTitle>
                    <div className="flex items-baseline gap-1">
                        <span className="text-2xl font-mono font-bold" style={{ color }}>
                            {currentValue.toFixed(1)}
                        </span>
                        <span className="text-xs text-muted-foreground">{units}</span>
                    </div>
                </div>
            </CardHeader>
            <CardContent className="pb-4">
                <ResponsiveContainer width="100%" height={height}>
                    <LineChart data={chartData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
                        <XAxis
                            dataKey="time"
                            tick={{ fontSize: 10, fill: '#888' }}
                            tickLine={false}
                            axisLine={{ stroke: '#333' }}
                            interval="preserveStartEnd"
                        />
                        <YAxis
                            domain={[domain.min, domain.max]}
                            tick={{ fontSize: 10, fill: '#888' }}
                            tickLine={false}
                            axisLine={{ stroke: '#333' }}
                            width={35}
                        />
                        <Tooltip
                            contentStyle={{
                                backgroundColor: 'hsl(var(--card))',
                                border: '1px solid hsl(var(--border))',
                                borderRadius: '8px',
                                fontSize: '12px',
                            }}
                            labelFormatter={(label) => `${label}s`}
                            formatter={(value: number) => [value.toFixed(2), title]}
                        />
                        {showGrid && (
                            <>
                                {/* Horizontal grid lines at 25%, 50%, 75% */}
                                {[0.25, 0.5, 0.75].map((pct) => (
                                    <ReferenceLine
                                        key={pct}
                                        y={domain.min + (domain.max - domain.min) * pct}
                                        stroke="#333"
                                        strokeDasharray="3 3"
                                    />
                                ))}
                            </>
                        )}
                        {targetValue !== undefined && (
                            <ReferenceLine
                                y={targetValue}
                                stroke="#f59e0b"
                                strokeDasharray="5 5"
                                label={{ value: 'Target', position: 'right', fill: '#f59e0b', fontSize: 10 }}
                            />
                        )}
                        <Line
                            type="monotone"
                            dataKey="value"
                            stroke={color}
                            strokeWidth={2}
                            dot={false}
                            isAnimationActive={false}
                        />
                    </LineChart>
                </ResponsiveContainer>
            </CardContent>
        </Card>
    );
}

export default LiveLinkChart;

