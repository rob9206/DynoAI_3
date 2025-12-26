/**
 * LiveLinkGauge - Real-time gauge display for a single channel
 */

import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { memo, useEffect, useMemo, useRef } from 'react';

interface LiveLinkGaugeProps {
    name: string;
    value: number;
    units: string;
    min?: number;
    max?: number;
    warningThreshold?: number;
    criticalThreshold?: number;
    decimals?: number;
    size?: 'sm' | 'md' | 'lg';
    showTrend?: boolean;
    color?: string;
}

export function LiveLinkGauge({
    name,
    value,
    units,
    min = 0,
    max = 100,
    warningThreshold,
    criticalThreshold,
    decimals = 1,
    size = 'md',
    showTrend = true,
    color,
}: LiveLinkGaugeProps) {
    const prevValueRef = useRef(value);

    // NOTE: Derive trend without state to avoid an extra render per value tick.
    // On the render after a value update, prevValueRef.current is still the prior value
    // (it gets updated in the effect below).
    const diff = value - prevValueRef.current;
    const trend: 'up' | 'down' | 'stable' =
        Math.abs(diff) < 0.1 ? 'stable' : diff > 0 ? 'up' : 'down';

    useEffect(() => {
        prevValueRef.current = value;
    }, [value]);

    const safeRange = max !== min ? (max - min) : 1;
    const percentage = Math.min(100, Math.max(0, ((value - min) / safeRange) * 100));

    // Determine color based on thresholds
    const resolvedColor = useMemo(() => {
        if (color) return color;
        if (criticalThreshold != null && value >= criticalThreshold) return 'rgb(239, 68, 68)'; // red
        if (warningThreshold != null && value >= warningThreshold) return 'rgb(245, 158, 11)'; // amber
        return 'rgb(74, 222, 128)'; // green
    }, [color, criticalThreshold, warningThreshold, value]);

    const sizeClasses = {
        sm: 'p-3 min-w-[140px]',
        md: 'p-4 min-w-[180px]',
        lg: 'p-5 min-w-[220px]',
    };

    const valueSizes = {
        sm: 'text-2xl',
        md: 'text-3xl',
        lg: 'text-4xl',
    };

    const TrendIcon = trend === 'up' ? TrendingUp : trend === 'down' ? TrendingDown : Minus;
    const trendColor = trend === 'up' ? 'text-green-400' : trend === 'down' ? 'text-red-400' : 'text-muted-foreground';

    return (
        <div className={`bg-card border border-border rounded-xl ${sizeClasses[size]} relative overflow-hidden`}>
            {/* Background gradient based on value */}
            <div
                className="absolute inset-0 opacity-10 transition-all duration-300"
                style={{
                    background: `linear-gradient(135deg, ${resolvedColor} 0%, transparent 50%)`,
                }}
            />

            {/* Content */}
            <div className="relative z-10">
                {/* Header */}
                <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide truncate">
                        {name}
                    </span>
                    {showTrend && (
                        <TrendIcon className={`h-3 w-3 ${trendColor}`} />
                    )}
                </div>

                {/* Value */}
                <div
                    className={`${valueSizes[size]} font-mono font-bold tracking-tight tabular-nums`}
                    style={{ color: resolvedColor }}
                >
                    {value.toFixed(decimals)}
                </div>

                {/* Units */}
                <span className="text-xs text-muted-foreground">{units}</span>

                {/* Progress bar */}
                <div className="mt-3 h-1.5 bg-muted rounded-full overflow-hidden">
                    <div
                        className="h-full rounded-full transition-[width] duration-200 ease-out"
                        style={{ backgroundColor: resolvedColor, width: `${percentage}%` }}
                    />
                </div>

                {/* Min/Max labels */}
                <div className="flex justify-between mt-1 text-[10px] text-muted-foreground/60">
                    <span>{min}</span>
                    <span>{max}</span>
                </div>
            </div>
        </div>
    );
}

export default memo(LiveLinkGauge);

