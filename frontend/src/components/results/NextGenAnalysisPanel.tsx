/**
 * NextGen Analysis Panel
 * 
 * Displays physics-informed ECU analysis results including:
 * - Spark valley findings
 * - Cause tree hypotheses
 * - Next test recommendations
 * - Spark/knock surface heatmaps
 */

import React, { useState } from 'react';
import {
  Loader2,
  AlertCircle,
  Zap,
  Target,
  ClipboardList,
  TrendingDown,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  CheckCircle2,
  Info,
  RefreshCw,
  Copy,
  Check,
  Gauge,
  Car,
  MapPin,
  BookOpen,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';
import { useNextGen } from '@/hooks/useNextGenAnalysis';
import { VEHeatmap } from './VEHeatmap';
import { CellTargetHeatmap } from './CellTargetHeatmap';
import { PlannerConstraintsPanel } from './PlannerConstraintsPanel';
import type {
  NextGenAnalysisPayload,
  NextGenSurface,
  SparkValleyFinding,
  NextGenHypothesis,
  NextGenTestStep,
  NextGenCoverageGap,
  NextGenChannelReadiness,
} from '@/lib/api';

interface NextGenAnalysisPanelProps {
  runId: string;
  className?: string;
}

export function NextGenAnalysisPanel({ runId, className }: NextGenAnalysisPanelProps) {
  const {
    data,
    isLoading,
    error,
    hasAnalysis,
    isNotGenerated,
    generate,
    isGenerating,
    generateError,
  } = useNextGen(runId);

  // Loading state
  if (isLoading) {
    return (
      <Card className={className}>
        <CardContent className="py-12">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <p className="text-sm text-muted-foreground">Loading NextGen analysis...</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Error state (not 404)
  if (error && !isNotGenerated) {
    return (
      <Card className={cn("border-destructive/50", className)}>
        <CardContent className="py-12">
          <div className="flex flex-col items-center gap-3 text-center">
            <AlertCircle className="h-8 w-8 text-destructive" />
            <p className="text-sm text-destructive">
              Failed to load NextGen analysis: {error instanceof Error ? error.message : 'Unknown error'}
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Not generated yet - show generate button
  if (isNotGenerated || !hasAnalysis || !data) {
    return (
      <Card className={cn("border-dashed border-2", className)}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Zap className="h-5 w-5 text-amber-500" />
            NextGen Analysis
          </CardTitle>
          <CardDescription>
            Physics-informed ECU reasoning: spark valleys, causal diagnosis, and intelligent test planning
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col items-center gap-4 py-6">
            <p className="text-sm text-muted-foreground text-center max-w-md">
              Run NextGen analysis to detect spark timing valleys, generate causal hypotheses,
              and receive intelligent next-test recommendations.
            </p>
            {generateError && (
              <div className="text-sm text-destructive flex items-center gap-2">
                <AlertCircle className="h-4 w-4" />
                {generateError instanceof Error ? generateError.message : 'Generation failed'}
              </div>
            )}
            <Button
              onClick={() => generate({})}
              disabled={isGenerating}
              className="gap-2"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Generating...
                </>
              ) : (
                <>
                  <Zap className="h-4 w-4" />
                  Generate NextGen Analysis
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Has data - render full panel (data is guaranteed to be non-null here)
  return (
    <Card className={cn("border-amber-500/30 bg-amber-500/5", className)}>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Zap className="h-5 w-5 text-amber-500" />
              NextGen Analysis
            </CardTitle>
            <CardDescription>
              Generated {new Date(data.generated_at).toLocaleString()}
            </CardDescription>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => generate({ force: true })}
            disabled={isGenerating}
            className="gap-2"
          >
            <RefreshCw className={cn("h-4 w-4", isGenerating && "animate-spin")} />
            Regenerate
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Channel Readiness Checklist */}
        {data.channel_readiness && (
          <ChannelReadinessPanel readiness={data.channel_readiness} />
        )}

        {/* Warnings */}
        {data.notes_warnings.length > 0 && (
          <WarningsSection warnings={data.notes_warnings} />
        )}

        {/* Mode Distribution Summary (compact) */}
        <ModeDistributionSummary modeSummary={data.mode_summary} />

        {/* Coverage Gaps Panel - PROMINENT */}
        {data.next_tests.coverage_gaps_detailed && data.next_tests.coverage_gaps_detailed.length > 0 && (
          <CoverageGapsPanel 
            gaps={data.next_tests.coverage_gaps_detailed}
            steps={data.next_tests.steps}
          />
        )}
        
        {/* Test Planner Constraints */}
        <PlannerConstraintsPanel vehicleId="default" className="mt-4" />
        
        {/* Cell Target Heatmap - Show which cells to hit next */}
        {data.surfaces && Object.keys(data.surfaces).length > 0 && (
          <CellTargetHeatmapSection surfaces={data.surfaces} />
        )}

        {/* Dyno Pull Script - PROMINENT */}
        <DynoPullScriptSection steps={data.next_tests.steps} />

        {/* Street Script - PROMINENT */}
        <StreetScriptSection steps={data.next_tests.steps} />

        {/* Spark Valley Findings (collapsed by default) */}
        {data.spark_valley.length > 0 && (
          <SparkValleySection findings={data.spark_valley} />
        )}

        {/* Heatmaps (simplified, 2-3 default) */}
        <SurfacesSection surfaces={data.surfaces} />

        {/* Cause Tree Hypotheses (collapsed by default, minimal) */}
        {data.cause_tree.hypotheses.length > 0 && (
          <HypothesesSection
            hypotheses={data.cause_tree.hypotheses}
            summary={data.cause_tree.summary}
          />
        )}

        {/* ECU Model Notes (collapsed by default) */}
        {data.ecu_model_notes && data.ecu_model_notes.length > 0 && (
          <ECUModelNotesSection notes={data.ecu_model_notes} />
        )}
      </CardContent>
    </Card>
  );
}

// =============================================================================
// Clipboard Utility
// =============================================================================

function useCopyToClipboard() {
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const copyToClipboard = async (text: string, id: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  return { copyToClipboard, copiedId };
}

// =============================================================================
// Sub-components
// =============================================================================

function WarningsSection({ warnings }: { warnings: string[] }) {
  return (
    <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4">
      <div className="flex items-start gap-3">
        <AlertTriangle className="h-5 w-5 text-yellow-500 flex-shrink-0 mt-0.5" />
        <div className="space-y-1">
          <p className="font-medium text-yellow-600 dark:text-yellow-400">Analysis Warnings</p>
          <ul className="text-sm text-muted-foreground space-y-1">
            {warnings.map((warning, idx) => (
              <li key={idx}>• {warning}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

function ChannelReadinessPanel({ readiness }: { readiness: NextGenChannelReadiness }) {
  const [expanded, setExpanded] = useState(false);

  if (!readiness) return null;

  const severityColors: Record<string, string> = {
    error: 'text-red-500',
    warning: 'text-yellow-500',
    info: 'text-blue-500',
  };

  const getConfidenceColor = (score: number): string => {
    if (score >= 0.8) return 'text-green-500';
    if (score >= 0.6) return 'text-yellow-500';
    if (score >= 0.4) return 'text-orange-500';
    return 'text-red-500';
  };

  const getConfidenceLabel = (score: number): string => {
    if (score >= 0.8) return 'Excellent';
    if (score >= 0.6) return 'Good';
    if (score >= 0.4) return 'Moderate';
    return 'Limited';
  };

  return (
    <div className="space-y-3">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-sm font-medium hover:text-primary transition-colors w-full text-left"
      >
        {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        <ClipboardList className="h-4 w-4 text-green-500" />
        <span>Channel Readiness</span>
        <span className="text-xs text-muted-foreground ml-2">
          ({readiness.required_present}/{readiness.required_total} required, {readiness.recommended_present}/{readiness.recommended_total} recommended)
        </span>
        <Badge 
          variant="outline" 
          className={cn("ml-auto text-xs", getConfidenceColor(readiness.confidence_score))}
        >
          {getConfidenceLabel(readiness.confidence_score)} ({Math.round(readiness.confidence_score * 100)}%)
        </Badge>
      </button>

      {expanded && (
        <div className="space-y-4 pl-6">
          {/* Trust Summary */}
          <div className="bg-muted/50 rounded-lg p-3">
            <p className="text-sm">{readiness.trust_summary}</p>
          </div>

          {/* Required Channels */}
          <div>
            <h5 className="text-xs font-medium text-muted-foreground mb-2">Required Channels</h5>
            <div className="grid grid-cols-2 gap-2">
              {readiness.required_channels.map((channel) => (
                <div
                  key={channel.name}
                  className={cn(
                    "flex items-center gap-2 text-sm p-2 rounded",
                    channel.present ? "bg-green-500/10" : "bg-red-500/10"
                  )}
                >
                  {channel.present ? (
                    <CheckCircle2 className="h-4 w-4 text-green-500" />
                  ) : (
                    <AlertCircle className="h-4 w-4 text-red-500" />
                  )}
                  <span>{channel.label}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Recommended Channels */}
          <div>
            <h5 className="text-xs font-medium text-muted-foreground mb-2">Recommended Channels</h5>
            <div className="grid grid-cols-2 gap-2">
              {readiness.recommended_channels.map((channel) => (
                <div
                  key={channel.name}
                  className={cn(
                    "flex items-center gap-2 text-sm p-2 rounded",
                    channel.present ? "bg-green-500/10" : "bg-yellow-500/10"
                  )}
                >
                  {channel.present ? (
                    <CheckCircle2 className="h-4 w-4 text-green-500" />
                  ) : (
                    <AlertTriangle className="h-4 w-4 text-yellow-500" />
                  )}
                  <div className="flex-1">
                    <span>{channel.label}</span>
                    {channel.note && (
                      <span className="text-xs text-muted-foreground ml-1">({channel.note})</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Feature Availability */}
          <div className="grid grid-cols-3 gap-3">
            {readiness.features_available.length > 0 && (
              <div>
                <h5 className="text-xs font-medium text-green-500 mb-1">Available</h5>
                <ul className="text-xs text-muted-foreground space-y-0.5">
                  {readiness.features_available.slice(0, 5).map((f, i) => (
                    <li key={i} className="flex items-center gap-1">
                      <CheckCircle2 className="h-3 w-3 text-green-500" />
                      {f}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {readiness.features_degraded.length > 0 && (
              <div>
                <h5 className="text-xs font-medium text-yellow-500 mb-1">Degraded</h5>
                <ul className="text-xs text-muted-foreground space-y-0.5">
                  {readiness.features_degraded.map((f, i) => (
                    <li key={i} className="flex items-center gap-1">
                      <AlertTriangle className="h-3 w-3 text-yellow-500" />
                      {f}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {readiness.features_disabled.length > 0 && (
              <div>
                <h5 className="text-xs font-medium text-red-500 mb-1">Disabled</h5>
                <ul className="text-xs text-muted-foreground space-y-0.5">
                  {readiness.features_disabled.map((f, i) => (
                    <li key={i} className="flex items-center gap-1">
                      <AlertCircle className="h-3 w-3 text-red-500" />
                      {f}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Warnings with codes */}
          {readiness.warnings.length > 0 && (
            <div>
              <h5 className="text-xs font-medium text-muted-foreground mb-2">Warnings</h5>
              <div className="space-y-1">
                {readiness.warnings.map((warning, idx) => (
                  <div
                    key={idx}
                    className="flex items-start gap-2 text-xs bg-muted/30 rounded p-2"
                  >
                    <AlertTriangle className={cn("h-3 w-3 flex-shrink-0 mt-0.5", severityColors[warning.severity])} />
                    <div className="flex-1">
                      <span>{warning.message}</span>
                      {warning.feature_impact && (
                        <span className="text-muted-foreground ml-1">({warning.feature_impact})</span>
                      )}
                    </div>
                    <code className="text-xs text-muted-foreground bg-muted px-1 rounded">
                      {warning.code}
                    </code>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ModeDistributionSummary({ modeSummary }: { modeSummary: Record<string, number> }) {
  const total = Object.values(modeSummary).reduce((a, b) => a + b, 0);
  if (total === 0) return null;

  const modes = [
    { key: 'wot', label: 'WOT', color: 'bg-red-500' },
    { key: 'cruise', label: 'Cruise', color: 'bg-blue-500' },
    { key: 'idle', label: 'Idle', color: 'bg-green-500' },
    { key: 'tip_in', label: 'Tip-In', color: 'bg-orange-500' },
    { key: 'tip_out', label: 'Tip-Out', color: 'bg-purple-500' },
    { key: 'decel', label: 'Decel', color: 'bg-cyan-500' },
    { key: 'heat_soak', label: 'Heat Soak', color: 'bg-yellow-500' },
  ];

  return (
    <div className="space-y-3">
      <h4 className="text-sm font-medium">Operating Mode Distribution</h4>
      <div className="flex gap-4 flex-wrap">
        {modes.map(({ key, label, color }) => {
          const count = modeSummary[key] ?? 0;
          const pct = total > 0 ? (count / total * 100).toFixed(1) : '0';
          if (count === 0) return null;
          return (
            <div key={key} className="flex items-center gap-2 text-sm">
              <div className={cn("w-3 h-3 rounded", color)} />
              <span className="text-muted-foreground">{label}:</span>
              <span className="font-medium">{pct}%</span>
            </div>
          );
        })}
      </div>
      <p className="text-xs text-muted-foreground">
        Total samples: {total.toLocaleString()}
      </p>
    </div>
  );
}

function CoverageGapsPanel({ 
  gaps, 
  steps 
}: { 
  gaps: NextGenCoverageGap[];
  steps: NextGenTestStep[];
}) {
  const [expanded, setExpanded] = useState(true);
  const { copyToClipboard, copiedId } = useCopyToClipboard();

  if (!gaps || gaps.length === 0) return null;

  const topGaps = gaps.slice(0, 8);

  const impactColors: Record<string, string> = {
    high: 'bg-red-500/20 text-red-500 border-red-500/30',
    medium: 'bg-yellow-500/20 text-yellow-500 border-yellow-500/30',
    low: 'bg-blue-500/20 text-blue-500 border-blue-500/30',
  };

  const regionLabels: Record<string, string> = {
    high_map_midrange: 'High Load (Dyno)',
    idle_low_map: 'Idle/Low Load',
    tip_in: 'Tip-In Zone',
    general: 'General',
  };

  const getTestTypeForGap = (gap: NextGenCoverageGap): string => {
    if (gap.region_type === 'high_map_midrange') return 'WOT Pull';
    if (gap.region_type === 'tip_in') return 'Roll-On';
    if (gap.region_type === 'idle_low_map') return 'Street Cruise';
    return 'Steady State';
  };

  const generateGapScript = (gap: NextGenCoverageGap): string => {
    const testType = getTestTypeForGap(gap);
    const lines = [
      `=== ${testType} ===`,
      `Target: ${gap.rpm_range[0]}-${gap.rpm_range[1]} RPM @ ${gap.map_range[0]}-${gap.map_range[1]} kPa`,
      `Coverage: ${gap.coverage_pct.toFixed(0)}% (${gap.empty_cells} cells need data)`,
    ];
    
    if (gap.region_type === 'high_map_midrange') {
      lines.push('Gear: 3rd or 4th (keep consistent)');
      lines.push(`Start: ${Math.max(1500, gap.rpm_range[0] - 500)} RPM`);
      lines.push(`End: ${gap.rpm_range[1] + 500} RPM`);
      lines.push('Notes: Full WOT, consistent ramp rate');
    } else if (gap.region_type === 'tip_in') {
      lines.push('Type: Controlled roll-on from cruise');
      lines.push('Throttle: 2-3 second tip-in to 70-80%');
    } else {
      lines.push('Type: Steady cruise hold');
      lines.push('Duration: 5+ seconds per point');
    }
    
    return lines.join('\n');
  };

  return (
    <div className="space-y-3">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-sm font-medium hover:text-primary transition-colors w-full text-left"
      >
        {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        <MapPin className="h-4 w-4 text-red-500" />
        Coverage Gaps ({gaps.length} regions need data)
      </button>

      {expanded && (
        <div className="space-y-3 pl-6">
          <p className="text-sm text-muted-foreground">
            These regions have insufficient data. Fill them to improve analysis accuracy.
          </p>

          <div className="grid gap-2">
            {topGaps.map((gap, idx) => (
              <div
                key={idx}
                className="bg-muted/50 rounded-lg p-3 space-y-2"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge
                        variant="outline"
                        className={cn("text-xs", impactColors[gap.impact])}
                      >
                        {gap.impact.toUpperCase()}
                      </Badge>
                      <Badge variant="secondary" className="text-xs">
                        {regionLabels[gap.region_type] || gap.region_type}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        {getTestTypeForGap(gap)}
                      </span>
                    </div>
                    <div className="mt-1 text-sm font-medium">
                      {gap.rpm_range[0]}-{gap.rpm_range[1]} RPM @ {gap.map_range[0]}-{gap.map_range[1]} kPa
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {gap.coverage_pct.toFixed(0)}% covered ({gap.empty_cells} cells need data)
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => copyToClipboard(generateGapScript(gap), `gap-${idx}`)}
                    className="text-xs h-8 px-2"
                  >
                    {copiedId === `gap-${idx}` ? (
                      <Check className="h-3 w-3 text-green-500" />
                    ) : (
                      <Copy className="h-3 w-3" />
                    )}
                  </Button>
                </div>
              </div>
            ))}
          </div>

          {gaps.length > 8 && (
            <p className="text-xs text-muted-foreground">
              + {gaps.length - 8} more coverage gaps...
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function DynoPullScriptSection({ steps }: { steps: NextGenTestStep[] }) {
  const [expanded, setExpanded] = useState(true);
  const { copyToClipboard, copiedId } = useCopyToClipboard();

  // Filter to only WOT pull steps
  const dynoSteps = steps.filter(s => s.test_type === 'wot_pull').slice(0, 4);

  if (dynoSteps.length === 0) return null;

  const generatePullScript = (step: NextGenTestStep, index: number): string => {
    const lines = [
      `Pull ${index + 1}: ${step.name}`,
      `Goal: ${step.goal}`,
    ];
    
    if (step.rpm_range) {
      const startRpm = Math.max(1500, step.rpm_range[0] - 500);
      lines.push(`Start RPM: ${startRpm}`);
      lines.push(`End RPM: ${step.rpm_range[1] + 500}`);
    }
    
    // Gear suggestion based on RPM range
    if (step.rpm_range) {
      if (step.rpm_range[1] <= 4000) {
        lines.push('Gear: 3rd or 4th (lower gear = faster ramp)');
      } else if (step.rpm_range[1] <= 5500) {
        lines.push('Gear: 4th or 5th');
      } else {
        lines.push('Gear: 5th or 6th (higher gear for top end)');
      }
    } else {
      lines.push('Gear: Choose 3rd or 4th; keep consistent');
    }
    
    lines.push('');
    lines.push('Notes:');
    lines.push('- Maintain consistent ramp rate');
    lines.push('- Full WOT required');
    if (step.required_channels.length > 0) {
      lines.push(`- Log: ${step.required_channels.slice(0, 4).join(', ')}`);
    }
    if (step.risk_notes) {
      lines.push(`- Warning: ${step.risk_notes}`);
    }
    
    return lines.join('\n');
  };

  const generateAllPullsScript = (): string => {
    const header = [
      '=== INERTIA DYNO PULL SCRIPT ===',
      `Generated: ${new Date().toLocaleString()}`,
      '',
      'General Setup:',
      '- Engine at operating temperature',
      '- Cool 30-60s between pulls',
      '- Monitor knock sensor throughout',
      '- Abort if IAT > 130°F or excessive knock',
      '',
      '---',
      '',
    ];
    
    const pullScripts = dynoSteps.map((step, idx) => generatePullScript(step, idx));
    
    return header.join('\n') + pullScripts.join('\n\n---\n\n');
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-2 text-sm font-medium hover:text-primary transition-colors text-left"
        >
          {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          <Gauge className="h-4 w-4 text-orange-500" />
          Dyno Pull Script ({dynoSteps.length} pulls)
        </button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => copyToClipboard(generateAllPullsScript(), 'all-pulls')}
          className="text-xs h-7 gap-1"
        >
          {copiedId === 'all-pulls' ? (
            <>
              <Check className="h-3 w-3 text-green-500" />
              Copied!
            </>
          ) : (
            <>
              <Copy className="h-3 w-3" />
              Copy All
            </>
          )}
        </Button>
      </div>

      {expanded && (
        <div className="space-y-3 pl-6">
          <div className="bg-orange-500/10 border border-orange-500/30 rounded-lg p-3 text-xs">
            <p className="font-medium text-orange-600 dark:text-orange-400 mb-1">
              Inertia Dyno Tips:
            </p>
            <ul className="text-muted-foreground space-y-0.5">
              <li>• Keep gear consistent across all pulls</li>
              <li>• Allow 30-60s cool-down between pulls</li>
              <li>• Monitor knock and abort if excessive</li>
            </ul>
          </div>

          <div className="space-y-2">
            {dynoSteps.map((step, idx) => (
              <div
                key={idx}
                className="bg-muted/50 rounded-lg p-3 space-y-2"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-lg font-bold text-orange-500">#{idx + 1}</span>
                    <div>
                      <h5 className="font-medium text-sm">{step.name}</h5>
                      <p className="text-xs text-muted-foreground">{step.goal}</p>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => copyToClipboard(generatePullScript(step, idx), `pull-${idx}`)}
                    className="text-xs h-7 px-2"
                  >
                    {copiedId === `pull-${idx}` ? (
                      <Check className="h-3 w-3 text-green-500" />
                    ) : (
                      <Copy className="h-3 w-3" />
                    )}
                  </Button>
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs">
                  {step.rpm_range && (
                    <>
                      <div>
                        <span className="text-muted-foreground">Start:</span>
                        <span className="ml-1 font-medium">{Math.max(1500, step.rpm_range[0] - 500)} RPM</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">End:</span>
                        <span className="ml-1 font-medium">{step.rpm_range[1] + 500} RPM</span>
                      </div>
                    </>
                  )}
                  <div className="col-span-2">
                    <span className="text-muted-foreground">Gear:</span>
                    <span className="ml-1 font-medium">
                      {step.rpm_range && step.rpm_range[1] <= 4000 
                        ? '3rd or 4th' 
                        : step.rpm_range && step.rpm_range[1] <= 5500 
                          ? '4th or 5th' 
                          : '5th or 6th'}
                    </span>
                  </div>
                </div>

                {step.risk_notes && (
                  <div className="flex items-center gap-1 text-xs text-yellow-500">
                    <AlertTriangle className="h-3 w-3" />
                    <span>{step.risk_notes}</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function StreetScriptSection({ steps }: { steps: NextGenTestStep[] }) {
  const [expanded, setExpanded] = useState(true);
  const { copyToClipboard, copiedId } = useCopyToClipboard();

  // Filter to street-appropriate steps (non-WOT)
  const streetSteps = steps.filter(s => 
    s.test_type === 'transient_rolloff' || 
    s.test_type === 'steady_state_sweep' ||
    s.test_type === 'general'
  ).slice(0, 5);

  if (streetSteps.length === 0) return null;

  const getStepIcon = (testType: string): string => {
    switch (testType) {
      case 'transient_rolloff': return 'Roll-On/Off';
      case 'steady_state_sweep': return 'Cruise';
      default: return 'General';
    }
  };

  const generateStreetScript = (): string => {
    const header = [
      '=== STREET LOGGING SCRIPT ===',
      `Generated: ${new Date().toLocaleString()}`,
      '',
      'Safety First:',
      '- Obey all traffic laws',
      '- Use safe roads with minimal traffic',
      '- Keep eyes on the road, not the logger',
      '- Have a passenger operate the logger if possible',
      '',
      '---',
      '',
    ];

    const stepScripts = streetSteps.map((step, idx) => {
      const lines = [
        `Step ${idx + 1}: ${step.name}`,
        `Type: ${getStepIcon(step.test_type)}`,
        `Goal: ${step.goal}`,
        '',
        'Instructions:',
        step.constraints,
      ];
      
      if (step.rpm_range) {
        lines.push(`RPM Target: ${step.rpm_range[0]}-${step.rpm_range[1]}`);
      }
      if (step.success_criteria) {
        lines.push(`Success: ${step.success_criteria}`);
      }
      if (step.risk_notes) {
        lines.push(`Note: ${step.risk_notes}`);
      }
      
      return lines.join('\n');
    });

    return header.join('\n') + stepScripts.join('\n\n---\n\n');
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-2 text-sm font-medium hover:text-primary transition-colors text-left"
        >
          {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          <Car className="h-4 w-4 text-blue-500" />
          Street Logging Script ({streetSteps.length} segments)
        </button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => copyToClipboard(generateStreetScript(), 'all-street')}
          className="text-xs h-7 gap-1"
        >
          {copiedId === 'all-street' ? (
            <>
              <Check className="h-3 w-3 text-green-500" />
              Copied!
            </>
          ) : (
            <>
              <Copy className="h-3 w-3" />
              Copy All
            </>
          )}
        </Button>
      </div>

      {expanded && (
        <div className="space-y-3 pl-6">
          <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-3 text-xs">
            <p className="font-medium text-blue-600 dark:text-blue-400 mb-1">
              Street Logging Tips:
            </p>
            <ul className="text-muted-foreground space-y-0.5">
              <li>• Find a safe route with minimal traffic</li>
              <li>• Engine should be at operating temperature</li>
              <li>• Consistent throttle rates for tip-in/out</li>
            </ul>
          </div>

          <div className="space-y-2">
            {streetSteps.map((step, idx) => (
              <div
                key={idx}
                className="bg-muted/50 rounded-lg p-3 space-y-2"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-lg font-bold text-blue-500">#{idx + 1}</span>
                    <div>
                      <div className="flex items-center gap-2">
                        <h5 className="font-medium text-sm">{step.name}</h5>
                        <Badge variant="secondary" className="text-xs">
                          {getStepIcon(step.test_type)}
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground">{step.goal}</p>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => copyToClipboard(
                      `${step.name}\n${step.goal}\n\n${step.constraints}\n\nSuccess: ${step.success_criteria}`,
                      `street-${idx}`
                    )}
                    className="text-xs h-7 px-2"
                  >
                    {copiedId === `street-${idx}` ? (
                      <Check className="h-3 w-3 text-green-500" />
                    ) : (
                      <Copy className="h-3 w-3" />
                    )}
                  </Button>
                </div>

                <div className="text-xs text-muted-foreground bg-background/50 rounded p-2">
                  {step.constraints}
                </div>

                {step.rpm_range && step.map_range && (
                  <div className="flex gap-4 text-xs text-muted-foreground">
                    <span>RPM: {step.rpm_range[0]}-{step.rpm_range[1]}</span>
                    <span>MAP: {step.map_range[0]}-{step.map_range[1]} kPa</span>
                  </div>
                )}

                {step.risk_notes && (
                  <div className="flex items-center gap-1 text-xs text-yellow-500">
                    <AlertTriangle className="h-3 w-3" />
                    <span>{step.risk_notes}</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function SparkValleySection({ findings }: { findings: SparkValleyFinding[] }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="space-y-3">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-sm font-medium hover:text-primary transition-colors w-full text-left"
      >
        {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        <TrendingDown className="h-4 w-4 text-amber-500" />
        Spark Valley Findings ({findings.length})
      </button>

      {expanded && (
        <div className="space-y-3 pl-6">
          {findings.map((finding, idx) => (
            <div
              key={idx}
              className="bg-muted/50 rounded-lg p-4 space-y-3"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Badge variant="secondary" className="capitalize">
                    {finding.cylinder}
                  </Badge>
                  <span className="text-sm font-medium">
                    Valley at {finding.rpm_center} RPM
                  </span>
                </div>
                <Badge
                  variant={finding.confidence >= 0.7 ? 'default' : 'outline'}
                  className="text-xs"
                >
                  {(finding.confidence * 100).toFixed(0)}% confidence
                </Badge>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                <div>
                  <span className="text-muted-foreground">Depth:</span>
                  <span className="ml-2 font-medium">{finding.depth_deg.toFixed(1)}°</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Valley Min:</span>
                  <span className="ml-2 font-medium">{finding.valley_min_deg.toFixed(1)}°</span>
                </div>
                <div>
                  <span className="text-muted-foreground">RPM Band:</span>
                  <span className="ml-2 font-medium">
                    {finding.rpm_band[0]}-{finding.rpm_band[1]}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground">MAP Band:</span>
                  <span className="ml-2 font-medium">{finding.map_band_used.toFixed(0)} kPa</span>
                </div>
              </div>

              {finding.evidence.length > 0 && (
                <div className="text-xs text-muted-foreground border-t border-border pt-2 mt-2">
                  {finding.evidence.slice(0, 3).map((e, i) => (
                    <div key={i}>• {e}</div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function HypothesesSection({
  hypotheses,
  summary,
}: {
  hypotheses: NextGenHypothesis[];
  summary: string;
}) {
  const [expanded, setExpanded] = useState(false); // Collapsed by default
  const [showAll, setShowAll] = useState(false);

  const sortedHypotheses = [...hypotheses].sort((a, b) => b.confidence - a.confidence);
  const displayHypotheses = showAll ? sortedHypotheses : sortedHypotheses.slice(0, 5);

  const categoryColors: Record<string, string> = {
    transient: 'bg-orange-500/20 text-orange-500',
    load_signal: 'bg-blue-500/20 text-blue-500',
    knock_limit: 'bg-red-500/20 text-red-500',
    temp_trim: 'bg-yellow-500/20 text-yellow-500',
    fuel_model: 'bg-green-500/20 text-green-500',
    data_quality: 'bg-gray-500/20 text-gray-500',
  };

  return (
    <div className="space-y-3">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-sm font-medium hover:text-primary transition-colors w-full text-left"
      >
        {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        <Target className="h-4 w-4 text-amber-500" />
        Causal Hypotheses ({hypotheses.length})
      </button>

      {expanded && (
        <div className="space-y-3 pl-6">
          <p className="text-sm text-muted-foreground">{summary}</p>

          {displayHypotheses.map((hyp, idx) => (
            <HypothesisCard key={hyp.hypothesis_id} hypothesis={hyp} rank={idx + 1} categoryColors={categoryColors} />
          ))}

          {sortedHypotheses.length > 5 && !showAll && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowAll(true)}
              className="text-xs"
            >
              Show {sortedHypotheses.length - 5} more...
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

function HypothesisCard({
  hypothesis,
  rank,
  categoryColors,
}: {
  hypothesis: NextGenHypothesis;
  rank: number;
  categoryColors: Record<string, string>;
}) {
  const [showDetails, setShowDetails] = useState(false);

  const confidenceColor =
    hypothesis.confidence >= 0.7
      ? 'text-green-500'
      : hypothesis.confidence >= 0.5
        ? 'text-yellow-500'
        : 'text-muted-foreground';

  return (
    <div className="bg-muted/50 rounded-lg p-4 space-y-2">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <span className="text-lg font-bold text-muted-foreground">#{rank}</span>
          <div>
            <h5 className="font-medium text-sm">{hypothesis.title}</h5>
            <div className="flex items-center gap-2 mt-1">
              <Badge
                variant="outline"
                className={cn("text-xs capitalize", categoryColors[hypothesis.category])}
              >
                {hypothesis.category.replace('_', ' ')}
              </Badge>
              <span className={cn("text-xs font-medium", confidenceColor)}>
                {(hypothesis.confidence * 100).toFixed(0)}% confidence
              </span>
            </div>
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setShowDetails(!showDetails)}
          className="text-xs"
        >
          {showDetails ? 'Less' : 'More'}
        </Button>
      </div>

      {showDetails && (
        <div className="space-y-3 pt-2 border-t border-border">
          {hypothesis.evidence.length > 0 && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1">Evidence:</p>
              <ul className="text-xs space-y-0.5">
                {hypothesis.evidence.map((e, i) => (
                  <li key={i} className="flex items-start gap-1">
                    <CheckCircle2 className="h-3 w-3 text-green-500 flex-shrink-0 mt-0.5" />
                    <span>{e}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {hypothesis.distinguishing_checks.length > 0 && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1">
                Distinguishing Checks:
              </p>
              <ul className="text-xs space-y-0.5">
                {hypothesis.distinguishing_checks.map((check, i) => (
                  <li key={i} className="flex items-start gap-1">
                    <Info className="h-3 w-3 text-blue-500 flex-shrink-0 mt-0.5" />
                    <span>{check}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function TestPlanSection({ testPlan }: { testPlan: NextGenAnalysisPayload['next_tests'] }) {
  const [expanded, setExpanded] = useState(true);

  const priorityColors: Record<number, string> = {
    1: 'bg-red-500',
    2: 'bg-orange-500',
    3: 'bg-yellow-500',
  };

  return (
    <div className="space-y-3">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-sm font-medium hover:text-primary transition-colors w-full text-left"
      >
        {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        <ClipboardList className="h-4 w-4 text-amber-500" />
        Next Test Plan ({testPlan.steps.length} steps)
      </button>

      {expanded && (
        <div className="space-y-3 pl-6">
          <p className="text-sm text-muted-foreground">{testPlan.priority_rationale}</p>

          {testPlan.coverage_gaps.length > 0 && (
            <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-3">
              <p className="text-xs font-medium text-blue-500 mb-1">Coverage Gaps:</p>
              <ul className="text-xs text-muted-foreground space-y-0.5">
                {testPlan.coverage_gaps.slice(0, 3).map((gap, i) => (
                  <li key={i}>• {gap}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="space-y-2">
            {testPlan.steps.slice(0, 5).map((step, idx) => (
              <TestStepCard
                key={idx}
                step={step}
                priorityColors={priorityColors}
              />
            ))}
          </div>

          {testPlan.steps.length > 5 && (
            <p className="text-xs text-muted-foreground">
              + {testPlan.steps.length - 5} more test steps...
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function TestStepCard({
  step,
  priorityColors,
}: {
  step: NextGenTestStep;
  priorityColors: Record<number, string>;
}) {
  return (
    <div className="bg-muted/50 rounded-lg p-3 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-2 flex-1">
          <div
            className={cn(
              "w-2 h-2 rounded-full flex-shrink-0 mt-1.5",
              priorityColors[step.priority] ?? 'bg-gray-500'
            )}
          />
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <h5 className="font-medium text-sm">{step.name}</h5>
              {step.efficiency_score !== undefined && (
                <Badge 
                  variant="outline" 
                  className={cn(
                    "text-xs",
                    step.efficiency_score >= 0.7 ? "bg-green-50 text-green-700 border-green-300" :
                    step.efficiency_score >= 0.4 ? "bg-yellow-50 text-yellow-700 border-yellow-300" :
                    "bg-gray-50 text-gray-700 border-gray-300"
                  )}
                >
                  {step.efficiency_score >= 0.7 ? "High Efficiency" :
                   step.efficiency_score >= 0.4 ? "Medium Efficiency" : "Low Efficiency"}
                </Badge>
              )}
            </div>
            <p className="text-xs text-muted-foreground">{step.goal}</p>
            {step.expected_coverage_gain !== undefined && step.expected_coverage_gain > 0 && (
              <p className="text-xs text-green-600 mt-1">
                +{step.expected_coverage_gain.toFixed(1)}% coverage
              </p>
            )}
          </div>
        </div>
        <Badge variant="outline" className="text-xs">
          P{step.priority}
        </Badge>
      </div>

      {(step.rpm_range || step.map_range) && (
        <div className="flex gap-4 text-xs text-muted-foreground">
          {step.rpm_range && (
            <span>RPM: {step.rpm_range[0]}-{step.rpm_range[1]}</span>
          )}
          {step.map_range && (
            <span>MAP: {step.map_range[0]}-{step.map_range[1]} kPa</span>
          )}
        </div>
      )}

      {step.risk_notes && (
        <div className="flex items-center gap-1 text-xs text-yellow-500">
          <AlertTriangle className="h-3 w-3" />
          <span>{step.risk_notes}</span>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// ECU Model Notes Section
// =============================================================================

function ECUModelNotesSection({ notes }: { notes: string[] }) {
  const [expanded, setExpanded] = useState(false); // Collapsed by default

  if (!notes || notes.length === 0) return null;

  return (
    <div className="space-y-3">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-sm font-medium hover:text-primary transition-colors w-full text-left"
      >
        {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        <BookOpen className="h-4 w-4 text-blue-500" />
        ECU Interaction Notes
      </button>

      {expanded && (
        <div className="pl-6 space-y-2">
          <p className="text-xs text-muted-foreground mb-3">
            Understanding how the ECU works helps interpret findings:
          </p>
          <ul className="space-y-2">
            {notes.map((note, idx) => (
              <li key={idx} className="flex items-start gap-2 text-sm">
                <span className="text-blue-500 mt-0.5 shrink-0">•</span>
                <span className="text-muted-foreground">{note}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function SurfacesSection({ surfaces }: { surfaces: Record<string, NextGenSurface> }) {
  const [expanded, setExpanded] = useState(true);
  const [selectedSurface, setSelectedSurface] = useState<string | null>(null);

  // Prioritize: afr_error first (most actionable), then spark, then knock
  // Only show 2-3 default surfaces to keep UI clean
  const priorityOrder = [
    'afr_error_front', 'afr_error_rear', 'afr_error_global',  // AFR error most actionable
    'spark_front', 'spark_rear', 'spark_global',              // Spark timing
    'knock_activity',                                          // Knock if present
  ];
  
  // Get available surfaces in priority order (max 3 by default)
  const availableSurfaces = priorityOrder.filter((id) => id in surfaces);
  
  // Pick default surfaces: 1 AFR error, 1 spark, 1 knock (if available)
  const defaultSurfaces: string[] = [];
  const afrSurface = availableSurfaces.find(id => id.includes('afr_error'));
  const sparkSurface = availableSurfaces.find(id => id.includes('spark'));
  const knockSurface = availableSurfaces.find(id => id.includes('knock'));
  
  if (afrSurface) defaultSurfaces.push(afrSurface);
  if (sparkSurface) defaultSurfaces.push(sparkSurface);
  if (knockSurface) defaultSurfaces.push(knockSurface);
  
  // If we have fewer than 3, add more from available
  for (const id of availableSurfaces) {
    if (defaultSurfaces.length >= 3) break;
    if (!defaultSurfaces.includes(id)) {
      defaultSurfaces.push(id);
    }
  }

  if (defaultSurfaces.length === 0) return null;

  const displaySurface = selectedSurface ?? defaultSurfaces[0];
  const surface = surfaces[displaySurface];

  // Graceful handling if selected surface doesn't exist
  if (!surface) return null;

  return (
    <div className="space-y-3">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-sm font-medium hover:text-primary transition-colors w-full text-left"
      >
        {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        <Zap className="h-4 w-4 text-amber-500" />
        Heatmaps ({defaultSurfaces.length})
      </button>

      {expanded && (
        <div className="space-y-4 pl-6">
          {/* Surface selector - only show default surfaces */}
          <div className="flex flex-wrap gap-2">
            {defaultSurfaces.map((id) => {
              const s = surfaces[id];
              if (!s) return null;
              return (
                <Button
                  key={id}
                  variant={displaySurface === id ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setSelectedSurface(id)}
                  className="text-xs"
                >
                  {s.title}
                </Button>
              );
            })}
          </div>

          {/* Selected surface */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h5 className="font-medium text-sm">{surface.title}</h5>
                <p className="text-xs text-muted-foreground">{surface.description}</p>
              </div>
              <Badge variant="outline" className="text-xs">
                {surface.stats.coverage_pct.toFixed(0)}% coverage
              </Badge>
            </div>

            {/* Render heatmap */}
            <SurfaceHeatmap surface={surface} />
          </div>
        </div>
      )}
    </div>
  );
}

function SurfaceHeatmap({ surface }: { surface: NextGenSurface }) {
  // Convert surface data to heatmap format
  // Values can be null, replace with 0 for display (or handle in VEHeatmap)
  const data = surface.values.map((row) =>
    row.map((val) => val ?? NaN)
  );

  const rowLabels = surface.rpm_axis.bins.map(String);
  const colLabels = surface.map_axis.bins.map(String);

  // Determine color mode based on surface type
  const isSparkOrTiming = surface.surface_id.includes('spark');
  const colorMode = isSparkOrTiming ? 'sequential' : 'diverging';

  return (
    <VEHeatmap
      data={data}
      rowLabels={rowLabels}
      colLabels={colLabels}
      colorMode={colorMode}
      showValues={true}
      valueDecimals={1}
      valueLabel={isSparkOrTiming ? 'Timing (°)' : 'AFR Error'}
      tooltipLoadUnit="kPa"
      showClampIndicators={!isSparkOrTiming}
      clampLimit={5}
    />
  );
}

// =============================================================================
// Cell Target Heatmap Section
// =============================================================================

function CellTargetHeatmapSection({ surfaces }: { surfaces: Record<string, NextGenSurface> }) {
  const [expanded, setExpanded] = useState(false);
  
  // Find a surface with hit_count data (prefer spark or afr_error)
  const surfaceWithHitCount = Object.values(surfaces).find(s => 
    s.hit_count && s.hit_count.length > 0 && s.hit_count[0].length > 0
  );
  
  if (!surfaceWithHitCount) return null;
  
  const rowLabels = surfaceWithHitCount.rpm_axis.bins.map(String);
  const colLabels = surfaceWithHitCount.map_axis.bins.map(String);
  
  return (
    <div className="space-y-3">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-sm font-medium hover:text-primary transition-colors w-full text-left"
      >
        {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        <Target className="h-4 w-4 text-red-500" />
        Hit These Cells Next
      </button>

      {expanded && (
        <div className="pl-6">
          <CellTargetHeatmap
            hitCount={surfaceWithHitCount.hit_count}
            rowLabels={rowLabels}
            colLabels={colLabels}
            minHits={3}
            highlightOnly={false}
          />
        </div>
      )}
    </div>
  );
}

export default NextGenAnalysisPanel;
