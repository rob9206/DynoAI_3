/**
 * Run Comparison Chart Component
 * 
 * Visual chart overlay showing HP/TQ curves from multiple runs
 * Complements the RunComparisonTable with graphical comparison
 */

import { useMemo } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Activity } from 'lucide-react';

interface RunData {
    run_id: string;
    peak_hp: number;
    peak_tq: number;
    power_curve?: Array<{ rpm: number; hp: number; tq: number }>;
}

interface RunComparisonChartProps {
    runs: RunData[];
    metric?: 'hp' | 'tq' | 'both';
    height?: number;
}

// Color palette for up to 5 runs
const RUN_COLORS = [
    '#f97316', // Orange - baseline
    '#22d3ee', // Cyan
    '#a78bfa', // Purple
    '#4ade80', // Green
    '#f59e0b', // Amber
];

export function RunComparisonChart({
    runs,
    metric = 'hp',
    height = 300
}: RunComparisonChartProps) {
    // Combine all run data into a single dataset
    const chartData = useMemo(() => {
        if (runs.length === 0) return [];

        // Get all unique RPM points
        const rpmSet = new Set<number>();
        runs.forEach(run => {
            run.power_curve?.forEach(point => rpmSet.add(point.rpm));
        });

        const rpmPoints = Array.from(rpmSet).sort((a, b) => a - b);

        // Build combined dataset
        return rpmPoints.map(rpm => {
            const point: Record<string, number> = { rpm };
            
            runs.forEach((run, idx) => {
                const dataPoint = run.power_curve?.find(p => p.rpm === rpm);
                if (dataPoint) {
                    if (metric === 'hp' || metric === 'both') {
                        point[`${run.run_id}_hp`] = dataPoint.hp;
                    }
                    if (metric === 'tq' || metric === 'both') {
                        point[`${run.run_id}_tq`] = dataPoint.tq;
                    }
                }
            });

            return point;
        });
    }, [runs, metric]);

    // Calculate Y-axis domain
    const domain = useMemo(() => {
        if (chartData.length === 0) return { min: 0, max: 200 };

        const allValues: number[] = [];
        chartData.forEach(point => {
            Object.entries(point).forEach(([key, value]) => {
                if (key !== 'rpm' && typeof value === 'number') {
                    allValues.push(value);
                }
            });
        });

        if (allValues.length === 0) return { min: 0, max: 200 };

        const min = Math.min(...allValues);
        const max = Math.max(...allValues);
        const padding = (max - min) * 0.1;

        return {
            min: Math.floor(min - padding),
            max: Math.ceil(max + padding),
        };
    }, [chartData]);

    if (runs.length === 0 || chartData.length === 0) {
        return (
            <Card className="bg-zinc-900/50 border-zinc-800">
                <CardHeader className="pb-3">
                    <CardTitle className="text-base flex items-center gap-2">
                        <Activity className="w-4 h-4 text-cyan-400" />
                        Power Curve Comparison
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="h-[300px] flex items-center justify-center text-zinc-500 text-sm">
                        No power curve data available
                    </div>
                </CardContent>
            </Card>
        );
    }

    return (
        <Card className="bg-zinc-900/50 border-zinc-800">
            <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                    <Activity className="w-4 h-4 text-cyan-400" />
                    Power Curve Comparison
                </CardTitle>
                <CardDescription className="text-xs">
                    Overlay of {runs.length} run{runs.length !== 1 ? 's' : ''} • 
                    {metric === 'hp' ? ' Horsepower' : metric === 'tq' ? ' Torque' : ' HP & Torque'}
                </CardDescription>
            </CardHeader>
            <CardContent>
                <ResponsiveContainer width="100%" height={height}>
                    <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                        <XAxis
                            dataKey="rpm"
                            tick={{ fontSize: 11, fill: '#71717a' }}
                            tickLine={false}
                            axisLine={{ stroke: '#3f3f46' }}
                            label={{ value: 'RPM', position: 'insideBottom', offset: -5, fontSize: 11, fill: '#71717a' }}
                        />
                        <YAxis
                            domain={[domain.min, domain.max]}
                            tick={{ fontSize: 11, fill: '#71717a' }}
                            tickLine={false}
                            axisLine={{ stroke: '#3f3f46' }}
                            width={45}
                            label={{ 
                                value: metric === 'hp' ? 'HP' : metric === 'tq' ? 'TQ' : 'HP / TQ', 
                                angle: -90, 
                                position: 'insideLeft',
                                fontSize: 11,
                                fill: '#71717a'
                            }}
                        />
                        <Tooltip
                            contentStyle={{
                                backgroundColor: '#18181b',
                                border: '1px solid #3f3f46',
                                borderRadius: '8px',
                                fontSize: '12px',
                                padding: '8px',
                            }}
                            labelFormatter={(label) => `${label} RPM`}
                            formatter={(value: number, name: string) => {
                                const [runId, metricType] = name.split('_');
                                return [
                                    value.toFixed(1),
                                    `${runId} (${metricType.toUpperCase()})`
                                ];
                            }}
                        />
                        <Legend
                            wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }}
                            formatter={(value) => {
                                const [runId, metricType] = value.split('_');
                                return `${runId} (${metricType?.toUpperCase() || ''})`;
                            }}
                        />
                        
                        {/* Render lines for each run */}
                        {runs.map((run, idx) => (
                            <Line
                                key={`${run.run_id}_hp`}
                                type="monotone"
                                dataKey={`${run.run_id}_hp`}
                                stroke={RUN_COLORS[idx % RUN_COLORS.length]}
                                strokeWidth={idx === 0 ? 3 : 2}
                                dot={false}
                                isAnimationActive={false}
                                opacity={idx === 0 ? 1 : 0.8}
                                strokeDasharray={metric === 'both' ? '5 5' : undefined}
                            />
                        ))}
                        
                        {metric === 'both' && runs.map((run, idx) => (
                            <Line
                                key={`${run.run_id}_tq`}
                                type="monotone"
                                dataKey={`${run.run_id}_tq`}
                                stroke={RUN_COLORS[idx % RUN_COLORS.length]}
                                strokeWidth={idx === 0 ? 2 : 1.5}
                                dot={false}
                                isAnimationActive={false}
                                opacity={0.6}
                            />
                        ))}
                    </LineChart>
                </ResponsiveContainer>
            </CardContent>
        </Card>
    );
}

