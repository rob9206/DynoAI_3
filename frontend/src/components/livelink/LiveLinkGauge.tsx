/**
 * LiveLinkGauge - Real-time gauge display for a single channel
 */

import { motion, AnimatePresence } from 'framer-motion';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

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
    const [trend, setTrend] = useState<'up' | 'down' | 'stable'>('stable');

    // Calculate trend
    useEffect(() => {
        const diff = value - prevValueRef.current;
        if (Math.abs(diff) < 0.1) {
            setTrend('stable');
        } else if (diff > 0) {
            setTrend('up');
        } else {
            setTrend('down');
        }
        prevValueRef.current = value;
    }, [value]);

    // Calculate fill percentage
    const percentage = Math.min(100, Math.max(0, ((value - min) / (max - min)) * 100));

    // Determine color based on thresholds
    const getColor = () => {
        if (color) return color;
        if (criticalThreshold && value >= criticalThreshold) return 'rgb(239, 68, 68)'; // red
        if (warningThreshold && value >= warningThreshold) return 'rgb(245, 158, 11)'; // amber
        return 'rgb(74, 222, 128)'; // green
    };

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
        <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className={`bg-card border border-border rounded-xl ${sizeClasses[size]} relative overflow-hidden`}
        >
            {/* Background gradient based on value */}
            <div
                className="absolute inset-0 opacity-10 transition-all duration-300"
                style={{
                    background: `linear-gradient(135deg, ${getColor()} 0%, transparent 50%)`,
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
                <AnimatePresence mode="wait">
                    <motion.div
                        key={value.toFixed(decimals)}
                        initial={{ opacity: 0, y: -10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: 10 }}
                        transition={{ duration: 0.15 }}
                        className={`${valueSizes[size]} font-mono font-bold tracking-tight`}
                        style={{ color: getColor() }}
                    >
                        {value.toFixed(decimals)}
                    </motion.div>
                </AnimatePresence>

                {/* Units */}
                <span className="text-xs text-muted-foreground">{units}</span>

                {/* Progress bar */}
                <div className="mt-3 h-1.5 bg-muted rounded-full overflow-hidden">
                    <motion.div
                        className="h-full rounded-full"
                        style={{ backgroundColor: getColor() }}
                        initial={{ width: 0 }}
                        animate={{ width: `${percentage}%` }}
                        transition={{ duration: 0.3, ease: 'easeOut' }}
                    />
                </div>

                {/* Min/Max labels */}
                <div className="flex justify-between mt-1 text-[10px] text-muted-foreground/60">
                    <span>{min}</span>
                    <span>{max}</span>
                </div>
            </div>
        </motion.div>
    );
}

export default LiveLinkGauge;

