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
    const { chartData, series } = useMemo(() => {
        if (runs.length === 0) return { chartData: [], series: [] as Array<{ key: string; label: string; color: string; width: number; dash?: string; opacity: number }> };

        const wantHp = metric === 'hp' || metric === 'both';
        const wantTq = metric === 'tq' || metric === 'both';

        // Define series keys that are NOT dependent on run_id text (run_id may include underscores)
        const nextSeries: Array<{ key: string; label: string; color: string; width: number; dash?: string; opacity: number }> = [];

        runs.forEach((run, idx) => {
            const color = RUN_COLORS[idx % RUN_COLORS.length];
            const width = idx === 0 ? 3 : 2;
            const opacity = idx === 0 ? 1 : 0.8;

            if (wantHp) {
                nextSeries.push({
                    key: `s${idx}:hp`,
                    label: `${run.run_id} (HP)`,
                    color,
                    width,
                    dash: metric === 'both' ? undefined : undefined,
                    opacity,
                });
            }
            if (wantTq) {
                nextSeries.push({
                    key: `s${idx}:tq`,
                    label: `${run.run_id} (TQ)`,
                    color,
                    width: idx === 0 ? 2 : 1.5,
                    dash: metric === 'both' ? '5 5' : undefined,
                    opacity: metric === 'both' ? 0.65 : opacity,
                });
            }
        });

        // Merge curves by RPM
        const rpmToPoint = new Map<number, Record<string, number>>();

        runs.forEach((run, idx) => {
            const curve = run.power_curve || [];
            curve.forEach((p) => {
                if (typeof p.rpm !== 'number') return;
                const rpm = p.rpm;
                const row = rpmToPoint.get(rpm) || { rpm };
                if (wantHp && typeof p.hp === 'number') row[`s${idx}:hp`] = p.hp;
                if (wantTq && typeof p.tq === 'number') row[`s${idx}:tq`] = p.tq;
                rpmToPoint.set(rpm, row);
            });
        });

        const nextData = Array.from(rpmToPoint.keys())
            .sort((a, b) => a - b)
            .map((rpm) => rpmToPoint.get(rpm)!);

        return { chartData: nextData, series: nextSeries };
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
                                const meta = series.find((s) => s.key === name);
                                return [value.toFixed(1), meta?.label ?? name];
                            }}
                        />
                        <Legend
                            wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }}
                            formatter={(value) => series.find((s) => s.key === value)?.label ?? String(value)}
                        />
                        
                        {/* Render series */}
                        {series.map((s) => (
                            <Line
                                key={s.key}
                                type="monotone"
                                dataKey={s.key}
                                stroke={s.color}
                                strokeWidth={s.width}
                                dot={false}
                                isAnimationActive={false}
                                opacity={s.opacity}
                                strokeDasharray={s.dash}
                            />
                        ))}
                    </LineChart>
                </ResponsiveContainer>
            </CardContent>
        </Card>
    );
}

