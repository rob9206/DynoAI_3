import { Clock, MapPin, Info } from 'lucide-react';
import { Card, CardContent, CardHeader } from '../ui/card';
import { Badge } from '../ui/badge';
import type { SessionReplayDecision } from '../../lib/api';

interface DecisionCardProps {
    decision: SessionReplayDecision;
    index: number;
    startTime?: string;
}

const ACTION_COLORS: Record<string, string> = {
    AFR_CORRECTION: 'bg-blue-500/10 text-blue-700 border-blue-500/20',
    SMOOTHING_START: 'bg-purple-500/10 text-purple-700 border-purple-500/20',
    GRADIENT_LIMITING: 'bg-orange-500/10 text-orange-700 border-orange-500/20',
    CLAMPING_START: 'bg-red-500/10 text-red-700 border-red-500/20',
    CLAMPING_APPLIED: 'bg-red-500/10 text-red-700 border-red-500/20',
    ANOMALY_DETECTION_START: 'bg-yellow-500/10 text-yellow-700 border-yellow-500/20',
    ANOMALY_DETECTED: 'bg-yellow-500/10 text-yellow-700 border-yellow-500/20',
};

const formatTimestamp = (timestamp: string): string => {
    try {
        const date = new Date(timestamp);
        return date.toLocaleTimeString('en-US', {
            hour12: false,
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            fractionalSecondDigits: 3,
        });
    } catch {
        return timestamp;
    }
};

const calculateElapsed = (start: string, current: string): string => {
    try {
        const startDate = new Date(start);
        const currentDate = new Date(current);
        const ms = currentDate.getTime() - startDate.getTime();

        if (ms < 1000) {
            return `+${ms.toFixed(1)}ms`;
        }
        return `+${(ms / 1000).toFixed(2)}s`;
    } catch {
        return '';
    }
};

const formatCell = (cell: SessionReplayDecision['cell']): string => {
    if (!cell) return '';

    const parts: string[] = [];
    if (cell.rpm !== undefined) parts.push(`RPM=${cell.rpm}`);
    if (cell.kpa !== undefined) parts.push(`KPA=${cell.kpa}`);
    if (cell.rpm_index !== undefined) parts.push(`RPM[${cell.rpm_index}]`);
    if (cell.kpa_index !== undefined) parts.push(`KPA[${cell.kpa_index}]`);
    if (cell.cylinder) parts.push(`Cyl=${cell.cylinder}`);

    return parts.join(' ');
};

const formatValue = (value: any): string => {
    if (typeof value === 'number') {
        return value.toFixed(3);
    }
    if (typeof value === 'object' && value !== null) {
        return JSON.stringify(value, null, 2);
    }
    return String(value);
};

export function DecisionCard({ decision, index, startTime }: DecisionCardProps) {
    const actionColor = ACTION_COLORS[decision.action] || 'bg-gray-500/10 text-gray-700 border-gray-500/20';
    const elapsed = startTime ? calculateElapsed(startTime, decision.timestamp) : '';
    const cellInfo = formatCell(decision.cell);

    return (
        <Card className="hover:shadow-md transition-shadow">
            <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-4">
                    <div className="flex items-center gap-2">
                        <span className="text-sm font-mono text-muted-foreground">#{index}</span>
                        <Badge className={`${actionColor} font-mono text-xs`}>
                            {decision.action}
                        </Badge>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <Clock className="h-3 w-3" />
                        <span className="font-mono">{formatTimestamp(decision.timestamp)}</span>
                        {elapsed && (
                            <span className="font-mono text-blue-600">({elapsed})</span>
                        )}
                    </div>
                </div>
            </CardHeader>

            <CardContent className="space-y-3">
                {/* Reason */}
                <div className="flex items-start gap-2">
                    <Info className="h-4 w-4 text-muted-foreground mt-0.5 flex-shrink-0" />
                    <p className="text-sm text-foreground">{decision.reason}</p>
                </div>

                {/* Cell Location */}
                {cellInfo && (
                    <div className="flex items-center gap-2">
                        <MapPin className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                        <span className="text-sm font-mono text-muted-foreground">{cellInfo}</span>
                    </div>
                )}

                {/* Values */}
                {decision.values && Object.keys(decision.values).length > 0 && (
                    <div className="mt-3 rounded-md bg-muted/50 p-3">
                        <p className="text-xs font-semibold text-muted-foreground mb-2">VALUES</p>
                        <div className="space-y-1">
                            {Object.entries(decision.values).map(([key, value]) => (
                                <div key={key} className="flex justify-between items-start gap-4 text-xs">
                                    <span className="font-mono text-muted-foreground">{key}:</span>
                                    <span className="font-mono text-foreground text-right">
                                        {formatValue(value)}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}

