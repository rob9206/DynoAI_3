/**
 * ConfidenceBadge - Compact confidence score display for JetDrive Command Center
 * 
 * Shows letter grade and score in a compact format suitable for the
 * command center's dense layout.
 */

import { Award, Info } from 'lucide-react';
import { Badge } from '../ui/badge';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../ui/tooltip';
import type { ConfidenceReport } from '../../lib/api';

interface ConfidenceBadgeProps {
    confidence: ConfidenceReport | null;
    compact?: boolean;
    className?: string;
}

export function ConfidenceBadge({ confidence, compact = false, className = '' }: ConfidenceBadgeProps) {
    if (!confidence) return null;

    const getGradeColor = (grade: string) => {
        switch (grade) {
            case 'A':
                return 'bg-green-500/20 text-green-400 border-green-500/30 hover:bg-green-500/30';
            case 'B':
                return 'bg-blue-500/20 text-blue-400 border-blue-500/30 hover:bg-blue-500/30';
            case 'C':
                return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30 hover:bg-yellow-500/30';
            case 'D':
                return 'bg-red-500/20 text-red-400 border-red-500/30 hover:bg-red-500/30';
            default:
                return 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30';
        }
    };

    const getScoreEmoji = (score: number) => {
        if (score >= 85) return '🏆';
        if (score >= 70) return '✨';
        if (score >= 50) return '⚡';
        return '⚠️';
    };

    if (compact) {
        return (
            <TooltipProvider>
                <Tooltip>
                    <TooltipTrigger asChild>
                        <Badge className={`${getGradeColor(confidence.letter_grade)} ${className} cursor-help`}>
                            <Award className="w-3 h-3 mr-1" />
                            {confidence.letter_grade} {confidence.overall_score.toFixed(0)}%
                        </Badge>
                    </TooltipTrigger>
                    <TooltipContent side="bottom" className="max-w-xs">
                        <div className="space-y-1 text-xs">
                            <p className="font-semibold">{confidence.grade_description}</p>
                            <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 mt-2 text-[10px]">
                                <span className="text-muted-foreground">Coverage:</span>
                                <span className="font-mono">{confidence.component_scores.coverage.score.toFixed(0)}</span>
                                <span className="text-muted-foreground">Consistency:</span>
                                <span className="font-mono">{confidence.component_scores.consistency.score.toFixed(0)}</span>
                                <span className="text-muted-foreground">Anomalies:</span>
                                <span className="font-mono">{confidence.component_scores.anomalies.score.toFixed(0)}</span>
                                <span className="text-muted-foreground">Clamping:</span>
                                <span className="font-mono">{confidence.component_scores.clamping.score.toFixed(0)}</span>
                            </div>
                        </div>
                    </TooltipContent>
                </Tooltip>
            </TooltipProvider>
        );
    }

    // Full display mode
    return (
        <div className={`flex items-center gap-2 ${className}`}>
            <TooltipProvider>
                <Tooltip>
                    <TooltipTrigger asChild>
                        <div className="flex items-center gap-2 cursor-help">
                            <span className="text-xl">{getScoreEmoji(confidence.overall_score)}</span>
                            <Badge className={`${getGradeColor(confidence.letter_grade)} text-sm font-bold px-3 py-1`}>
                                {confidence.letter_grade}
                            </Badge>
                            <div className="text-left">
                                <div className="text-sm font-bold text-white">
                                    {confidence.overall_score.toFixed(1)}%
                                </div>
                                <div className="text-[10px] text-zinc-500">
                                    Confidence
                                </div>
                            </div>
                        </div>
                    </TooltipTrigger>
                    <TooltipContent side="bottom" className="max-w-sm">
                        <div className="space-y-2 text-xs">
                            <p className="font-semibold text-foreground">{confidence.grade_description}</p>

                            <div className="grid grid-cols-2 gap-x-4 gap-y-1 pt-2 border-t border-border">
                                <div>
                                    <span className="text-muted-foreground">Coverage:</span>
                                    <span className="ml-2 font-mono font-semibold">{confidence.component_scores.coverage.score.toFixed(0)}</span>
                                </div>
                                <div>
                                    <span className="text-muted-foreground">Consistency:</span>
                                    <span className="ml-2 font-mono font-semibold">{confidence.component_scores.consistency.score.toFixed(0)}</span>
                                </div>
                                <div>
                                    <span className="text-muted-foreground">Anomalies:</span>
                                    <span className="ml-2 font-mono font-semibold">{confidence.component_scores.anomalies.score.toFixed(0)}</span>
                                </div>
                                <div>
                                    <span className="text-muted-foreground">Clamping:</span>
                                    <span className="ml-2 font-mono font-semibold">{confidence.component_scores.clamping.score.toFixed(0)}</span>
                                </div>
                            </div>

                            {confidence.recommendations.length > 0 && (
                                <div className="pt-2 border-t border-border">
                                    <p className="text-muted-foreground mb-1">Top Recommendation:</p>
                                    <p className="text-foreground text-[11px] leading-relaxed">
                                        {confidence.recommendations[0]}
                                    </p>
                                </div>
                            )}
                        </div>
                    </TooltipContent>
                </Tooltip>
            </TooltipProvider>
        </div>
    );
}

