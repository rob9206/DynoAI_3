/**
 * Power Opportunities Panel Component
 * 
 * Displays "Find Me Power" analysis results with:
 * - Summary of total opportunities and estimated HP gains
 * - Ranked list of specific power opportunities
 * - Detailed suggestions for AFR and timing changes
 * - Safety notes and confidence indicators
 */

import { useState } from 'react';
import { Zap, TrendingUp, Flame, AlertCircle, Download, ChevronDown, ChevronUp } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Progress } from './ui/progress';
import {
    Accordion,
    AccordionContent,
    AccordionItem,
    AccordionTrigger,
} from './ui/accordion';

interface PowerOpportunity {
    type: string;
    rpm: number;
    kpa: number;
    suggestion: string;
    estimated_gain_hp: number;
    confidence: number;
    coverage: number;
    current_hp?: number;
    details: {
        afr_error_pct?: number;
        suggested_change_pct?: number;
        suggested_afr_change_pct?: number;
        advance_deg?: number;
        current_suggestion_deg?: number;
        knock_front: number;
        knock_rear: number;
    };
}

interface PowerOpportunitiesData {
    summary: {
        total_opportunities: number;
        total_estimated_gain_hp: number;
        analysis_date: string;
    };
    opportunities: PowerOpportunity[];
    safety_notes: string[];
}

interface PowerOpportunitiesPanelProps {
    data: PowerOpportunitiesData | null;
    loading?: boolean;
    onDownload?: () => void;
}

export default function PowerOpportunitiesPanel({ 
    data, 
    loading = false,
    onDownload 
}: PowerOpportunitiesPanelProps) {
    const [expandedOpportunity, setExpandedOpportunity] = useState<number | null>(null);

    if (loading) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center">
                        <Zap className="h-5 w-5 mr-2 text-yellow-500" />
                        Find Me Power Analysis
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="flex items-center justify-center py-8">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                        <span className="ml-3 text-muted-foreground">Analyzing power opportunities...</span>
                    </div>
                </CardContent>
            </Card>
        );
    }

    if (!data || data.opportunities.length === 0) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center">
                        <Zap className="h-5 w-5 mr-2 text-yellow-500" />
                        Find Me Power Analysis
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="text-center py-8">
                        <AlertCircle className="h-12 w-12 mx-auto mb-3 text-muted-foreground/50" />
                        <p className="text-muted-foreground">
                            No power opportunities found. Your tune may already be well optimized, or more dyno coverage is needed.
                        </p>
                    </div>
                </CardContent>
            </Card>
        );
    }

    const getOpportunityIcon = (type: string) => {
        if (type.includes('Combined')) return <Flame className="h-4 w-4" />;
        if (type.includes('Timing')) return <Zap className="h-4 w-4" />;
        return <TrendingUp className="h-4 w-4" />;
    };

    const getOpportunityColor = (type: string) => {
        if (type.includes('Combined')) return 'text-orange-500 bg-orange-500/10 border-orange-500/20';
        if (type.includes('Timing')) return 'text-yellow-500 bg-yellow-500/10 border-yellow-500/20';
        return 'text-blue-500 bg-blue-500/10 border-blue-500/20';
    };

    const getConfidenceColor = (confidence: number) => {
        if (confidence >= 90) return 'text-green-500';
        if (confidence >= 70) return 'text-yellow-500';
        return 'text-orange-500';
    };

    return (
        <div className="space-y-4">
            {/* Summary Card */}
            <Card>
                <CardHeader>
                    <div className="flex items-center justify-between">
                        <div>
                            <CardTitle className="flex items-center">
                                <Zap className="h-5 w-5 mr-2 text-yellow-500" />
                                Find Me Power Analysis
                            </CardTitle>
                            <CardDescription className="mt-1">
                                Safe opportunities to gain additional horsepower
                            </CardDescription>
                        </div>
                        {onDownload && (
                            <Button variant="outline" size="sm" onClick={onDownload}>
                                <Download className="h-4 w-4 mr-2" />
                                Export
                            </Button>
                        )}
                    </div>
                </CardHeader>
                <CardContent>
                    {/* Summary Stats */}
                    <div className="grid grid-cols-2 gap-4 mb-6">
                        <div className="p-4 rounded-lg bg-gradient-to-br from-orange-500/10 to-orange-500/5 border border-orange-500/20">
                            <div className="text-3xl font-bold text-orange-400">
                                {data.summary.total_opportunities}
                            </div>
                            <div className="text-sm text-muted-foreground">Opportunities Found</div>
                        </div>
                        <div className="p-4 rounded-lg bg-gradient-to-br from-green-500/10 to-green-500/5 border border-green-500/20">
                            <div className="text-3xl font-bold text-green-400">
                                +{data.summary.total_estimated_gain_hp.toFixed(1)}
                            </div>
                            <div className="text-sm text-muted-foreground">Estimated HP Gain</div>
                        </div>
                    </div>

                    {/* Safety Banner */}
                    <div className="p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/20 mb-4">
                        <div className="flex items-start space-x-2">
                            <AlertCircle className="h-4 w-4 text-yellow-500 mt-0.5 flex-shrink-0" />
                            <div className="text-xs text-muted-foreground">
                                <span className="font-medium text-yellow-500">Safety First:</span> All suggestions are conservative. 
                                Apply changes incrementally (50% at a time) and test on dyno before proceeding.
                            </div>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Opportunities List */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base">
                        Power Opportunities (Ranked by Estimated Gain)
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                    {data.opportunities.map((opp, index) => (
                        <div
                            key={index}
                            className="rounded-lg border border-border bg-muted/30 hover:bg-muted/50 transition-colors"
                        >
                            {/* Opportunity Header */}
                            <div
                                className="p-4 cursor-pointer"
                                onClick={() => setExpandedOpportunity(expandedOpportunity === index ? null : index)}
                            >
                                <div className="flex items-start justify-between">
                                    <div className="flex-1">
                                        {/* Type Badge */}
                                        <div className="flex items-center gap-2 mb-2">
                                            <Badge className={`${getOpportunityColor(opp.type)} border`}>
                                                {getOpportunityIcon(opp.type)}
                                                <span className="ml-1.5">{opp.type}</span>
                                            </Badge>
                                            <span className="text-xs text-muted-foreground font-mono">
                                                #{index + 1}
                                            </span>
                                        </div>

                                        {/* Location */}
                                        <div className="text-sm font-medium text-foreground mb-1">
                                            {opp.rpm} RPM @ {opp.kpa} kPa
                                        </div>

                                        {/* Suggestion */}
                                        <div className="text-sm text-muted-foreground mb-2">
                                            {opp.suggestion}
                                        </div>

                                        {/* Stats Row */}
                                        <div className="flex items-center gap-4 text-xs">
                                            <div className="flex items-center gap-1">
                                                <TrendingUp className="h-3 w-3 text-green-500" />
                                                <span className="font-bold text-green-400">
                                                    +{opp.estimated_gain_hp.toFixed(2)} HP
                                                </span>
                                            </div>
                                            <div className={`flex items-center gap-1 ${getConfidenceColor(opp.confidence)}`}>
                                                <span className="font-medium">{opp.confidence}%</span>
                                                <span className="text-muted-foreground">confidence</span>
                                            </div>
                                            <div className="text-muted-foreground">
                                                {opp.coverage} hits
                                            </div>
                                            {opp.current_hp && (
                                                <div className="text-muted-foreground">
                                                    Current: {opp.current_hp.toFixed(1)} HP
                                                </div>
                                            )}
                                        </div>
                                    </div>

                                    {/* Expand Icon */}
                                    <div className="ml-4">
                                        {expandedOpportunity === index ? (
                                            <ChevronUp className="h-5 w-5 text-muted-foreground" />
                                        ) : (
                                            <ChevronDown className="h-5 w-5 text-muted-foreground" />
                                        )}
                                    </div>
                                </div>
                            </div>

                            {/* Expanded Details */}
                            {expandedOpportunity === index && (
                                <div className="px-4 pb-4 pt-2 border-t border-border space-y-3">
                                    {/* Confidence Bar */}
                                    <div>
                                        <div className="flex justify-between text-xs mb-1">
                                            <span className="text-muted-foreground">Confidence Level</span>
                                            <span className={getConfidenceColor(opp.confidence)}>
                                                {opp.confidence}%
                                            </span>
                                        </div>
                                        <Progress value={opp.confidence} className="h-2" />
                                    </div>

                                    {/* Technical Details */}
                                    <div className="grid grid-cols-2 gap-3 text-xs">
                                        {opp.details.afr_error_pct !== undefined && (
                                            <div className="p-2 rounded bg-background/50">
                                                <div className="text-muted-foreground">AFR Error</div>
                                                <div className="font-mono font-medium">
                                                    {opp.details.afr_error_pct > 0 ? '+' : ''}
                                                    {opp.details.afr_error_pct.toFixed(2)}%
                                                </div>
                                            </div>
                                        )}
                                        {(opp.details.suggested_change_pct !== undefined || 
                                          opp.details.suggested_afr_change_pct !== undefined) && (
                                            <div className="p-2 rounded bg-background/50">
                                                <div className="text-muted-foreground">Suggested AFR Change</div>
                                                <div className="font-mono font-medium text-blue-400">
                                                    {(opp.details.suggested_change_pct || opp.details.suggested_afr_change_pct || 0) > 0 ? '+' : ''}
                                                    {(opp.details.suggested_change_pct || opp.details.suggested_afr_change_pct || 0).toFixed(2)}%
                                                </div>
                                            </div>
                                        )}
                                        {opp.details.advance_deg !== undefined && (
                                            <div className="p-2 rounded bg-background/50">
                                                <div className="text-muted-foreground">Timing Advance</div>
                                                <div className="font-mono font-medium text-yellow-400">
                                                    +{opp.details.advance_deg.toFixed(1)}°
                                                </div>
                                            </div>
                                        )}
                                        <div className="p-2 rounded bg-background/50">
                                            <div className="text-muted-foreground">Knock Status</div>
                                            <div className="font-mono font-medium text-green-400">
                                                F: {opp.details.knock_front.toFixed(1)}° / R: {opp.details.knock_rear.toFixed(1)}°
                                            </div>
                                        </div>
                                    </div>

                                    {/* Implementation Steps */}
                                    <div className="p-3 rounded-lg bg-blue-500/5 border border-blue-500/20">
                                        <div className="text-xs font-medium text-blue-400 mb-2">
                                            Implementation Steps:
                                        </div>
                                        <ol className="text-xs text-muted-foreground space-y-1 list-decimal list-inside">
                                            <li>Find cell at {opp.rpm} RPM / {opp.kpa} kPa in your table</li>
                                            <li>Apply <strong>50%</strong> of suggested change first</li>
                                            <li>Test on dyno and monitor for knock</li>
                                            <li>If safe, apply remaining 50%</li>
                                        </ol>
                                    </div>
                                </div>
                            )}
                        </div>
                    ))}
                </CardContent>
            </Card>

            {/* Safety Notes */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base flex items-center">
                        <AlertCircle className="h-4 w-4 mr-2 text-yellow-500" />
                        Safety Guidelines
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <ul className="text-sm text-muted-foreground space-y-2">
                        {data.safety_notes.map((note, index) => (
                            <li key={index} className="flex items-start">
                                <span className="text-yellow-500 mr-2 mt-0.5">•</span>
                                <span>{note}</span>
                            </li>
                        ))}
                    </ul>
                </CardContent>
            </Card>
        </div>
    );
}

