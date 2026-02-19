/**
 * NextGen Analysis Panel
 * 
 * Displays physics-informed ECU analysis results including:
 * - Spark valley findings
 * - Cause tree hypotheses
 * - Next test recommendations
 * - Spark/knock surface heatmaps
 */

import React, { useState, useEffect, useRef } from 'react';
import {
  Loader2,
  AlertCircle,
  Zap,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  Copy,
  Check,
  Gauge,
  Car,
  ClipboardList,
  MapPin,
  TrendingDown,
  Target,
  Info,
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

  // Track if we've attempted auto-generation for this runId
  const autoGenerateAttempted = useRef<string | null>(null);
  const [isCollapsed, setIsCollapsed] = useState(false);

  // Auto-generate analysis when data exists but analysis doesn't
  // Only attempt once per runId to avoid infinite loops on error
  useEffect(() => {
    if (
      runId &&
      isNotGenerated &&
      !isGenerating &&
      !generateError &&
      autoGenerateAttempted.current !== runId
    ) {
      autoGenerateAttempted.current = runId;
      // Small delay to let the UI settle
      const timer = setTimeout(() => {
        generate({});
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [runId, isNotGenerated, isGenerating, generateError, generate]);

  // Reset auto-generate tracker when runId changes
  useEffect(() => {
    if (autoGenerateAttempted.current && autoGenerateAttempted.current !== runId) {
      autoGenerateAttempted.current = null;
    }
  }, [runId]);

  // Loading state - more informative for operators
  if (isLoading || (isGenerating && !data)) {
    return (
      <Card className={cn("border-amber-500/30 bg-amber-500/5", className)}>
        <CardContent className="py-8">
          <div className="flex flex-col items-center gap-4">
            <div className="relative">
              <div className="absolute inset-0 animate-ping opacity-20">
                <Zap className="h-10 w-10 text-amber-500" />
              </div>
              <Zap className="h-10 w-10 text-amber-500" />
            </div>
            <div className="text-center space-y-1">
              <p className="font-medium text-zinc-200">
                {isGenerating ? 'Analyzing Dyno Data...' : 'Loading Analysis...'}
              </p>
              <p className="text-sm text-muted-foreground">
                {isGenerating 
                  ? 'Detecting modes, building surfaces, planning next tests'
                  : 'Retrieving analysis results'}
              </p>
            </div>
            {isGenerating && (
              <div className="w-48">
                <Progress value={undefined} className="h-1" />
              </div>
            )}
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

  // Helper to parse error and provide user-friendly guidance
  const getErrorGuidance = (err: Error | unknown) => {
    const message = err instanceof Error ? err.message : String(err);
    
    // 400 error typically means missing input data
    if (message.includes('400') || message.toLowerCase().includes('bad request')) {
      return {
        title: 'Input Data Required',
        message: 'This run does not have the required dyno log data for NextGen analysis.',
        suggestions: [
          'Select a run that has completed data capture (e.g., from a dyno pull)',
          'Upload a CSV file with RPM, MAP, AFR, and spark timing channels',
          'Runs from the JetStream simulator include sample data'
        ],
        isDataMissing: true,
      };
    }
    
    // 404 means analysis not generated yet (normal state)
    if (message.includes('404')) {
      return null; // Not an error, just not generated
    }
    
    // Generic error
    return {
      title: 'Analysis Failed',
      message: message,
      suggestions: ['Check that the backend is running', 'Try refreshing the page'],
      isDataMissing: false,
    };
  };

  const errorGuidance = generateError ? getErrorGuidance(generateError) : null;

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
            {/* Show helpful error guidance if generation failed */}
            {errorGuidance ? (
              <div className="w-full max-w-md space-y-3">
                <div className="flex items-start gap-3 p-4 rounded-lg bg-amber-500/10 border border-amber-500/30">
                  <AlertTriangle className="h-5 w-5 text-amber-500 flex-shrink-0 mt-0.5" />
                  <div className="space-y-2">
                    <p className="font-medium text-amber-200">{errorGuidance.title}</p>
                    <p className="text-sm text-muted-foreground">{errorGuidance.message}</p>
                  </div>
                </div>
                
                {errorGuidance.suggestions.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                      What to do:
                    </p>
                    <ul className="space-y-1.5">
                      {errorGuidance.suggestions.map((suggestion, idx) => (
                        <li key={idx} className="flex items-start gap-2 text-sm text-muted-foreground">
                          <CheckCircle2 className="h-4 w-4 text-emerald-500 flex-shrink-0 mt-0.5" />
                          <span>{suggestion}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {!errorGuidance.isDataMissing && (
                  <Button
                    onClick={() => generate({})}
                    disabled={isGenerating}
                    variant="outline"
                    className="gap-2 mt-2"
                  >
                    <RefreshCw className="h-4 w-4" />
                    Retry Analysis
                  </Button>
                )}
              </div>
            ) : (
              <>
                <p className="text-sm text-muted-foreground text-center max-w-md">
                  Run NextGen analysis to detect spark timing valleys, generate causal hypotheses,
                  and receive intelligent next-test recommendations.
                </p>
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
              </>
            )}
          </div>
        </CardContent>
      </Card>
    );
  }

  // Extract the ONE most important action
  const dynoPulls = data.next_tests?.steps?.filter(s => s.test_type === 'wot_pull') || [];
  const nextDynoTest = dynoPulls[0];
  const totalPulls = dynoPulls.length;
  const coverageGaps = data.next_tests?.coverage_gaps_detailed || [];
  const gapCount = coverageGaps.length;
  const isComplete = gapCount === 0;

  // Has data - render SIMPLE operator-focused panel
  return (
    <Card className={cn("border-zinc-700 bg-zinc-900", className)}>
      {/* Simple header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800">
        <div className="flex items-center gap-3">
          <Zap className="h-6 w-6 text-amber-500" />
          <span className="text-lg font-semibold text-white">Next Test</span>
        </div>
        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="text-sm text-zinc-400 hover:text-white flex items-center gap-1"
        >
          {isCollapsed ? 'Show Details' : 'Hide Details'}
          {isCollapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </button>
      </div>

      {/* MAIN ACTION - Big, clear, one thing */}
      <div className="p-6">
        {isComplete ? (
          // All done state
          <div className="text-center py-8">
            <CheckCircle2 className="h-16 w-16 text-emerald-500 mx-auto mb-4" />
            <h2 className="text-2xl font-bold text-white mb-2">Coverage Complete</h2>
            <p className="text-zinc-400">All critical regions have sufficient data</p>
          </div>
        ) : nextDynoTest ? (
          // Dyno pull needed
          <DynoActionCard 
            test={nextDynoTest} 
            gapCount={gapCount} 
            pullNumber={1} 
            totalPulls={totalPulls}
          />
        ) : (
          // Street logging needed
          <div className="text-center py-8">
            <Car className="h-16 w-16 text-blue-500 mx-auto mb-4" />
            <h2 className="text-2xl font-bold text-white mb-2">Street Logging Needed</h2>
            <p className="text-zinc-400">{gapCount} coverage gaps to fill</p>
          </div>
        )}
      </div>

      {/* Expandable details - hidden by default */}
      {!isCollapsed && (
        <div className="border-t border-zinc-800 p-6 space-y-6 bg-zinc-950/50">
          {/* Coverage Gaps - simple list */}
          {gapCount > 0 && (
            <SimpleGapsList gaps={coverageGaps} />
          )}
          
          {/* Additional pulls if any */}
          {data.next_tests.steps.filter(s => s.test_type === 'wot_pull').length > 1 && (
            <AdditionalPullsList steps={data.next_tests.steps.filter(s => s.test_type === 'wot_pull').slice(1)} />
          )}

          {/* Street tests */}
          {data.next_tests.steps.filter(s => s.test_type !== 'wot_pull').length > 0 && (
            <StreetTestsList steps={data.next_tests.steps.filter(s => s.test_type !== 'wot_pull')} />
          )}
        </div>
      )}
    </Card>
  );
}

// =============================================================================
// SIMPLE OPERATOR-FOCUSED COMPONENTS
// =============================================================================

/** The ONE big action card - dyno pull with all operator features */
function DynoActionCard({ test, gapCount, pullNumber = 1, totalPulls = 1 }: { 
  test: NextGenTestStep; 
  gapCount: number;
  pullNumber?: number;
  totalPulls?: number;
}) {
  const { copyToClipboard, copiedId } = useCopyToClipboard();
  const [cooldownSeconds, setCooldownSeconds] = useState(0);
  const [showSuccess, setShowSuccess] = useState(false);
  const [lastPullTime, setLastPullTime] = useState<Date | null>(null);
  
  const startRpm = test.rpm_range ? Math.max(1500, test.rpm_range[0] - 500) : 2000;
  const endRpm = test.rpm_range ? test.rpm_range[1] + 500 : 6000;
  
  const scriptText = `${test.name}
Start: ${startRpm} RPM
End: ${endRpm} RPM  
Gear: 4th or 5th
${test.risk_notes ? `\nWARNING: ${test.risk_notes}` : ''}`;

  // Cooldown timer effect
  useEffect(() => {
    if (cooldownSeconds > 0) {
      const timer = setTimeout(() => setCooldownSeconds(cooldownSeconds - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [cooldownSeconds]);

  // Handle "Pull Complete" action
  const handlePullComplete = () => {
    setShowSuccess(true);
    setLastPullTime(new Date());
    setCooldownSeconds(45); // 45 second cooldown
    
    // Hide success after 3 seconds
    setTimeout(() => setShowSuccess(false), 3000);
  };

  // Format time ago
  const getTimeAgo = (date: Date) => {
    const seconds = Math.floor((new Date().getTime() - date.getTime()) / 1000);
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.floor(seconds / 60);
    return `${minutes}m ago`;
  };

  // Success overlay
  if (showSuccess) {
    return (
      <div className="text-center py-12 animate-pulse">
        <CheckCircle2 className="h-24 w-24 text-emerald-500 mx-auto mb-4" />
        <h2 className="text-3xl font-bold text-emerald-400 mb-2">Good Pull!</h2>
        <p className="text-xl text-zinc-400">Data captured successfully</p>
      </div>
    );
  }

  // Cooling down state
  if (cooldownSeconds > 0) {
    return (
      <div className="text-center py-8 space-y-6">
        {/* Cooldown timer - big and obvious */}
        <div className="relative w-32 h-32 mx-auto">
          <svg className="w-32 h-32 transform -rotate-90">
            <circle
              cx="64"
              cy="64"
              r="56"
              stroke="currentColor"
              strokeWidth="8"
              fill="none"
              className="text-zinc-800"
            />
            <circle
              cx="64"
              cy="64"
              r="56"
              stroke="currentColor"
              strokeWidth="8"
              fill="none"
              strokeDasharray={352}
              strokeDashoffset={352 - (352 * cooldownSeconds) / 45}
              className="text-amber-500 transition-all duration-1000"
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-4xl font-bold text-amber-400">{cooldownSeconds}</span>
          </div>
        </div>
        
        <div>
          <h2 className="text-2xl font-bold text-amber-400 mb-2">Cooling Down</h2>
          <p className="text-zinc-400">Wait before next pull</p>
        </div>

        {/* Skip button */}
        <Button
          variant="outline"
          onClick={() => setCooldownSeconds(0)}
          className="text-zinc-400"
        >
          Skip Cooldown
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Pull counter - prominent */}
      <div className="text-center">
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-cyan-500/20 border border-cyan-500/30">
          <span className="text-lg font-bold text-cyan-400">Pull {pullNumber}</span>
          <span className="text-zinc-500">of</span>
          <span className="text-lg font-bold text-cyan-400">{totalPulls}</span>
        </div>
      </div>

      {/* Big RPM display - TAPPABLE for touch screens */}
      <button
        onClick={() => copyToClipboard(scriptText, 'main-action')}
        className="w-full p-6 rounded-2xl bg-zinc-800/50 border-2 border-zinc-700 hover:border-cyan-500/50 transition-all active:scale-[0.98] cursor-pointer"
      >
        <div className="flex items-center justify-center gap-8">
          <div className="text-center">
            <div className="text-sm text-zinc-500 uppercase tracking-wider mb-1">Start</div>
            <div className="text-6xl font-bold text-cyan-400">{startRpm}</div>
            <div className="text-xl text-zinc-500">RPM</div>
          </div>
          
          <div className="text-5xl text-zinc-600">→</div>
          
          <div className="text-center">
            <div className="text-sm text-zinc-500 uppercase tracking-wider mb-1">End</div>
            <div className="text-6xl font-bold text-cyan-400">{endRpm}</div>
            <div className="text-xl text-zinc-500">RPM</div>
          </div>
        </div>

        {/* Gear - inside tappable area */}
        <div className="text-center mt-4">
          <span className="text-2xl text-white">Gear: </span>
          <span className="text-2xl font-bold text-white">4th or 5th</span>
        </div>

        {/* Tap hint */}
        <div className="text-center mt-4 text-sm text-zinc-600">
          {copiedId === 'main-action' ? (
            <span className="text-emerald-400">✓ Copied to clipboard</span>
          ) : (
            <span>Tap to copy instructions</span>
          )}
        </div>
      </button>

      {/* Warning if any */}
      {test.risk_notes && (
        <div className="flex items-center justify-center gap-3 p-4 rounded-xl bg-yellow-500/10 border border-yellow-500/30">
          <AlertTriangle className="h-6 w-6 text-yellow-500 flex-shrink-0" />
          <span className="text-lg text-yellow-200">{test.risk_notes}</span>
        </div>
      )}

      {/* BIG "Pull Complete" button - for after the pull */}
      <Button
        size="lg"
        onClick={handlePullComplete}
        className="w-full gap-3 text-xl py-8 h-auto bg-emerald-600 hover:bg-emerald-500 active:scale-[0.98]"
      >
        <CheckCircle2 className="h-8 w-8" />
        Pull Complete
      </Button>

      {/* Last pull info */}
      {lastPullTime && (
        <p className="text-center text-zinc-500">
          Last pull: {getTimeAgo(lastPullTime)}
        </p>
      )}

      {/* Gap count - subtle */}
      <p className="text-center text-zinc-500">
        {gapCount} coverage gap{gapCount !== 1 ? 's' : ''} remaining
      </p>
    </div>
  );
}

/** Simple gaps list */
function SimpleGapsList({ gaps }: { gaps: NextGenCoverageGap[] }) {
  return (
    <div>
      <h3 className="text-lg font-semibold text-white mb-3">Coverage Gaps</h3>
      <div className="space-y-2">
        {gaps.slice(0, 4).map((gap, idx) => (
          <div key={idx} className="flex items-center justify-between p-3 bg-zinc-800 rounded-lg">
            <span className="text-white">{gap.rpm_range?.[0]}-{gap.rpm_range?.[1]} RPM @ {gap.map_range?.[0]}-{gap.map_range?.[1]} kPa</span>
            <span className="text-zinc-400">{gap.coverage_pct?.toFixed(0)}% covered</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Additional pulls list */
function AdditionalPullsList({ steps }: { steps: NextGenTestStep[] }) {
  return (
    <div>
      <h3 className="text-lg font-semibold text-white mb-3">Additional Pulls</h3>
      <div className="space-y-2">
        {steps.slice(0, 3).map((step, idx) => (
          <div key={idx} className="flex items-center justify-between p-3 bg-zinc-800 rounded-lg">
            <span className="text-white">{step.name}</span>
            <span className="text-cyan-400 font-mono">
              {step.rpm_range?.[0]}-{step.rpm_range?.[1]} RPM
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Street tests list */
function StreetTestsList({ steps }: { steps: NextGenTestStep[] }) {
  return (
    <div>
      <h3 className="text-lg font-semibold text-white mb-3">Street Logging</h3>
      <div className="space-y-2">
        {steps.slice(0, 3).map((step, idx) => (
          <div key={idx} className="p-3 bg-zinc-800 rounded-lg">
            <div className="text-white font-medium">{step.name}</div>
            <div className="text-zinc-400 text-sm mt-1">{step.goal}</div>
          </div>
        ))}
      </div>
    </div>
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
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-3 text-base font-semibold hover:text-primary transition-colors text-left"
        >
          {expanded ? <ChevronDown className="h-5 w-5" /> : <ChevronRight className="h-5 w-5" />}
          <Gauge className="h-5 w-5 text-orange-500" />
          <span>Dyno Pull Script ({dynoSteps.length} pulls)</span>
        </button>
        <Button
          variant="outline"
          size="default"
          onClick={() => copyToClipboard(generateAllPullsScript(), 'all-pulls')}
          className="gap-2"
        >
          {copiedId === 'all-pulls' ? (
            <>
              <Check className="h-4 w-4 text-green-500" />
              Copied!
            </>
          ) : (
            <>
              <Copy className="h-4 w-4" />
              Copy All
            </>
          )}
        </Button>
      </div>

      {expanded && (
        <div className="space-y-4 pl-2">
          {/* Tips box - larger text */}
          <div className="bg-orange-500/10 border border-orange-500/30 rounded-lg p-4">
            <p className="font-semibold text-orange-400 text-base mb-2">
              Inertia Dyno Tips:
            </p>
            <ul className="text-zinc-300 space-y-1 text-sm">
              <li>• Keep gear consistent across all pulls</li>
              <li>• Allow 30-60s cool-down between pulls</li>
              <li>• Monitor knock and abort if excessive</li>
            </ul>
          </div>

          {/* Pull cards - much larger and clearer */}
          <div className="space-y-4">
            {dynoSteps.map((step, idx) => (
              <div
                key={idx}
                className="bg-zinc-800/70 border border-zinc-700 rounded-xl p-5 space-y-4"
              >
                {/* Header row */}
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-4">
                    <div className="w-12 h-12 rounded-full bg-orange-500/20 flex items-center justify-center flex-shrink-0">
                      <span className="text-xl font-bold text-orange-400">#{idx + 1}</span>
                    </div>
                    <div>
                      <h5 className="font-semibold text-lg text-zinc-100">{step.name}</h5>
                      <p className="text-sm text-zinc-400 mt-1">{step.goal}</p>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => copyToClipboard(generatePullScript(step, idx), `pull-${idx}`)}
                    className="h-10 w-10"
                  >
                    {copiedId === `pull-${idx}` ? (
                      <Check className="h-5 w-5 text-green-500" />
                    ) : (
                      <Copy className="h-5 w-5" />
                    )}
                  </Button>
                </div>

                {/* RPM and Gear info - large and clear */}
                <div className="grid grid-cols-3 gap-4">
                  {step.rpm_range && (
                    <>
                      <div className="bg-zinc-900/50 rounded-lg p-3">
                        <span className="text-xs text-zinc-500 uppercase tracking-wide block mb-1">Start</span>
                        <span className="text-xl font-bold text-cyan-400">{Math.max(1500, step.rpm_range[0] - 500)} RPM</span>
                      </div>
                      <div className="bg-zinc-900/50 rounded-lg p-3">
                        <span className="text-xs text-zinc-500 uppercase tracking-wide block mb-1">End</span>
                        <span className="text-xl font-bold text-cyan-400">{step.rpm_range[1] + 500} RPM</span>
                      </div>
                    </>
                  )}
                  <div className="bg-zinc-900/50 rounded-lg p-3">
                    <span className="text-xs text-zinc-500 uppercase tracking-wide block mb-1">Gear</span>
                    <span className="text-xl font-bold text-white">
                      {step.rpm_range && step.rpm_range[1] <= 4000 
                        ? '4th or 5th' 
                        : step.rpm_range && step.rpm_range[1] <= 5500 
                          ? '4th or 5th' 
                          : '4th or 5th'}
                    </span>
                  </div>
                </div>

                {/* Warning - prominent */}
                {step.risk_notes && (
                  <div className="flex items-center gap-3 p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/30">
                    <AlertTriangle className="h-5 w-5 text-yellow-500 flex-shrink-0" />
                    <span className="text-sm text-yellow-200">{step.risk_notes}</span>
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
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-3 text-base font-semibold hover:text-primary transition-colors text-left"
        >
          {expanded ? <ChevronDown className="h-5 w-5" /> : <ChevronRight className="h-5 w-5" />}
          <Car className="h-5 w-5 text-blue-500" />
          <span>Street Logging Script ({streetSteps.length} segments)</span>
        </button>
        <Button
          variant="outline"
          size="default"
          onClick={() => copyToClipboard(generateStreetScript(), 'all-street')}
          className="gap-2"
        >
          {copiedId === 'all-street' ? (
            <>
              <Check className="h-4 w-4 text-green-500" />
              Copied!
            </>
          ) : (
            <>
              <Copy className="h-4 w-4" />
              Copy All
            </>
          )}
        </Button>
      </div>

      {expanded && (
        <div className="space-y-4 pl-2">
          {/* Tips box - larger text */}
          <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-4">
            <p className="font-semibold text-blue-400 text-base mb-2">
              Street Logging Tips:
            </p>
            <ul className="text-zinc-300 space-y-1 text-sm">
              <li>• Find a safe route with minimal traffic</li>
              <li>• Engine should be at operating temperature</li>
              <li>• Consistent throttle rates for tip-in/out</li>
            </ul>
          </div>

          {/* Street segment cards - larger and clearer */}
          <div className="space-y-4">
            {streetSteps.map((step, idx) => (
              <div
                key={idx}
                className="bg-zinc-800/70 border border-zinc-700 rounded-xl p-5 space-y-4"
              >
                {/* Header row */}
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-4">
                    <div className="w-12 h-12 rounded-full bg-blue-500/20 flex items-center justify-center flex-shrink-0">
                      <span className="text-xl font-bold text-blue-400">#{idx + 1}</span>
                    </div>
                    <div>
                      <div className="flex items-center gap-3 flex-wrap">
                        <h5 className="font-semibold text-lg text-zinc-100">{step.name}</h5>
                        <Badge className="bg-blue-500/20 text-blue-300 border-blue-500/30 text-sm px-3">
                          {getStepIcon(step.test_type)}
                        </Badge>
                      </div>
                      <p className="text-sm text-zinc-400 mt-1">{step.goal}</p>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => copyToClipboard(
                      `${step.name}\n${step.goal}\n\n${step.constraints}\n\nSuccess: ${step.success_criteria}`,
                      `street-${idx}`
                    )}
                    className="h-10 w-10"
                  >
                    {copiedId === `street-${idx}` ? (
                      <Check className="h-5 w-5 text-green-500" />
                    ) : (
                      <Copy className="h-5 w-5" />
                    )}
                  </Button>
                </div>

                {/* Instructions - prominent */}
                <div className="text-base text-zinc-200 bg-zinc-900/70 rounded-lg p-4 border border-zinc-700/50">
                  {step.constraints}
                </div>

                {/* RPM/MAP info */}
                {step.rpm_range && step.map_range && (
                  <div className="flex gap-6 text-sm">
                    <div>
                      <span className="text-zinc-500">RPM:</span>
                      <span className="ml-2 font-semibold text-cyan-400">{step.rpm_range[0]}-{step.rpm_range[1]}</span>
                    </div>
                    <div>
                      <span className="text-zinc-500">MAP:</span>
                      <span className="ml-2 font-semibold text-cyan-400">{step.map_range[0]}-{step.map_range[1]} kPa</span>
                    </div>
                  </div>
                )}

                {/* Warning - prominent */}
                {step.risk_notes && (
                  <div className="flex items-center gap-3 p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/30">
                    <AlertTriangle className="h-5 w-5 text-yellow-500 flex-shrink-0" />
                    <span className="text-sm text-yellow-200">{step.risk_notes}</span>
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
