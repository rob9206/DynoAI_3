/**
 * PreflightCheckPanel - Pre-session validation for JetDrive
 *
 * Runs comprehensive checks before starting a dyno session:
 * - Provider connectivity
 * - Required channel presence
 * - Data health thresholds
 * - Semantic validation (detects mislabeled channels)
 *
 * Prevents wasted dyno time by catching configuration issues upfront.
 */

import { useState } from "react";
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Loader2,
  Play,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Info,
  Wrench,
  Radio,
  Activity,
  Gauge,
  Zap,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "../ui/card";
import { Button } from "../ui/button";
import { Badge } from "../ui/badge";
import { Progress } from "../ui/progress";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "../ui/collapsible";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "../ui/tooltip";
import { cn } from "../../lib/utils";

// =============================================================================
// Types
// =============================================================================

interface PreflightCheck {
  name: string;
  status: "passed" | "warning" | "failed" | "skipped";
  message: string;
  fix_suggestion: string | null;
  details: Record<string, unknown>;
}

interface MislabelSuspicion {
  channel_name: string;
  expected_type: string;
  observed_behavior: string;
  confidence: number;
  fix_suggestion: string;
}

interface PreflightResult {
  passed: boolean;
  provider_id: number | null;
  provider_name: string | null;
  provider_host: string | null;
  checks: PreflightCheck[];
  missing_channels: string[];
  suspected_mislabels: MislabelSuspicion[];
  can_override: boolean;
  mode: string;
  sample_seconds: number;
  timestamp: number;
  error?: string;
}

interface PreflightCheckPanelProps {
  apiUrl?: string;
  onPreflightComplete?: (result: PreflightResult) => void;
  className?: string;
}

// =============================================================================
// Status Icons
// =============================================================================

const StatusIcon = ({ status }: { status: string }) => {
  switch (status) {
    case "passed":
      return <CheckCircle2 className="h-4 w-4 text-green-500" />;
    case "warning":
      return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
    case "failed":
      return <XCircle className="h-4 w-4 text-red-500" />;
    case "skipped":
      return <Info className="h-4 w-4 text-gray-400" />;
    default:
      return <Activity className="h-4 w-4 text-gray-400" />;
  }
};

// =============================================================================
// Check Item Component
// =============================================================================

const CheckItem = ({
  check,
  expanded,
  onToggle,
}: {
  check: PreflightCheck;
  expanded: boolean;
  onToggle: () => void;
}) => {
  const hasDetails =
    check.fix_suggestion || Object.keys(check.details).length > 0;

  return (
    <div
      className={cn(
        "border rounded-lg p-3 transition-colors",
        check.status === "passed" && "border-green-500/30 bg-green-500/5",
        check.status === "warning" && "border-yellow-500/30 bg-yellow-500/5",
        check.status === "failed" && "border-red-500/30 bg-red-500/5",
        check.status === "skipped" && "border-gray-500/30 bg-gray-500/5"
      )}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <StatusIcon status={check.status} />
          <span className="font-medium capitalize">
            {check.name.replace(/_/g, " ")}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Badge
            variant="outline"
            className={cn(
              "text-xs",
              check.status === "passed" && "border-green-500/50 text-green-500",
              check.status === "warning" &&
                "border-yellow-500/50 text-yellow-500",
              check.status === "failed" && "border-red-500/50 text-red-500"
            )}
          >
            {check.status}
          </Badge>
          {hasDetails && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0"
              onClick={onToggle}
            >
              {expanded ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </Button>
          )}
        </div>
      </div>

      <p className="text-sm text-muted-foreground mt-1">{check.message}</p>

      {expanded && hasDetails && (
        <div className="mt-3 pt-3 border-t border-border/50 space-y-2">
          {check.fix_suggestion && (
            <div className="flex items-start gap-2 text-sm">
              <Wrench className="h-4 w-4 text-blue-500 mt-0.5 shrink-0" />
              <div>
                <span className="font-medium text-blue-500">Fix: </span>
                <span className="text-muted-foreground whitespace-pre-line">
                  {check.fix_suggestion}
                </span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// =============================================================================
// Mislabel Warning Component
// =============================================================================

const MislabelWarning = ({ mislabel }: { mislabel: MislabelSuspicion }) => (
  <div className="border border-orange-500/30 bg-orange-500/5 rounded-lg p-3">
    <div className="flex items-start gap-2">
      <AlertTriangle className="h-4 w-4 text-orange-500 mt-0.5 shrink-0" />
      <div className="flex-1">
        <div className="flex items-center justify-between">
          <span className="font-medium text-orange-500">
            {mislabel.channel_name}
          </span>
          <Badge
            variant="outline"
            className="text-xs border-orange-500/50 text-orange-500"
          >
            {(mislabel.confidence * 100).toFixed(0)}% confidence
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground mt-1">
          Expected: <span className="font-medium">{mislabel.expected_type}</span>
        </p>
        <p className="text-sm text-muted-foreground">
          Observed: {mislabel.observed_behavior}
        </p>
        <div className="flex items-start gap-2 mt-2 text-sm">
          <Wrench className="h-4 w-4 text-blue-500 mt-0.5 shrink-0" />
          <span className="text-blue-500">{mislabel.fix_suggestion}</span>
        </div>
      </div>
    </div>
  </div>
);

// =============================================================================
// Main Component
// =============================================================================

export function PreflightCheckPanel({
  apiUrl = "http://127.0.0.1:5001/api/jetdrive",
  onPreflightComplete,
  className,
}: PreflightCheckPanelProps) {
  const [isRunning, setIsRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<PreflightResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedChecks, setExpandedChecks] = useState<Set<string>>(new Set());
  const [showDetails, setShowDetails] = useState(false);

  const formatErrorMessage = async (response: Response) => {
    const base = `HTTP ${response.status}`;

    try {
      const contentType = response.headers.get("content-type") ?? "";
      if (contentType.includes("application/json")) {
        const errorData: unknown = await response.json();
        const errorValue =
          errorData &&
          typeof errorData === "object" &&
          "error" in errorData
            ? (errorData as { error?: unknown }).error
            : errorData;

        if (typeof errorValue === "string" && errorValue.trim().length > 0) {
          return errorValue;
        }

        if (errorValue && typeof errorValue === "object" && "message" in errorValue) {
          const message = (errorValue as { message?: unknown }).message;
          if (typeof message === "string" && message.trim().length > 0) {
            return message;
          }
        }

        if (errorValue != null) {
          return JSON.stringify(errorValue);
        }
      }

      const text = await response.text();
      return text.trim().length > 0 ? text : base;
    } catch {
      return base;
    }
  };

  const getErrorMessage = (err: unknown) => {
    if (err instanceof Error && err.message) {
      return err.message;
    }
    if (typeof err === "string" && err.trim().length > 0) {
      return err;
    }
    try {
      return JSON.stringify(err);
    } catch {
      return "Unknown error";
    }
  };

  const toggleCheckExpanded = (name: string) => {
    setExpandedChecks((prev) => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
      } else {
        next.add(name);
      }
      return next;
    });
  };

  const runPreflight = async () => {
    setIsRunning(true);
    setProgress(0);
    setError(null);
    setResult(null);

    // Simulate progress during the 15-second sample period
    const progressInterval = setInterval(() => {
      setProgress((prev) => Math.min(prev + 6, 95));
    }, 1000);

    try {
      const response = await fetch(`${apiUrl}/preflight/run?mode=blocking&sample_seconds=15`, {
        method: "POST",
      });

      clearInterval(progressInterval);
      setProgress(100);

      if (!response.ok) {
        const errorMessage = await formatErrorMessage(response);
        throw new Error(errorMessage);
      }

      const data: PreflightResult = await response.json();
      setResult(data);

      // Auto-expand failed checks
      const failedChecks = data.checks
        .filter((c) => c.status === "failed" || c.status === "warning")
        .map((c) => c.name);
      setExpandedChecks(new Set(failedChecks));

      if (onPreflightComplete) {
        onPreflightComplete(data);
      }
    } catch (err) {
      clearInterval(progressInterval);
      setError(getErrorMessage(err));
    } finally {
      setIsRunning(false);
    }
  };

  // Count checks by status
  const checkCounts = result
    ? {
        passed: result.checks.filter((c) => c.status === "passed").length,
        warning: result.checks.filter((c) => c.status === "warning").length,
        failed: result.checks.filter((c) => c.status === "failed").length,
      }
    : null;

  return (
    <Card className={cn("", className)}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Gauge className="h-5 w-5 text-blue-500" />
              Preflight Check
            </CardTitle>
            <CardDescription>
              Validate dyno connection and data channels before starting
            </CardDescription>
          </div>
          <Button
            onClick={runPreflight}
            disabled={isRunning}
            variant={result?.passed ? "outline" : "default"}
            className="gap-2"
          >
            {isRunning ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Running...
              </>
            ) : result ? (
              <>
                <RefreshCw className="h-4 w-4" />
                Re-run
              </>
            ) : (
              <>
                <Play className="h-4 w-4" />
                Run Preflight
              </>
            )}
          </Button>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Progress bar during run */}
        {isRunning && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">
                Sampling data for validation...
              </span>
              <span className="text-muted-foreground">{progress}%</span>
            </div>
            <Progress value={progress} className="h-2" />
          </div>
        )}

        {/* Error display */}
        {error && (
          <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-500">
            <XCircle className="h-5 w-5 shrink-0" />
            <span className="text-sm">{error}</span>
          </div>
        )}

        {/* Result display */}
        {result && (
          <>
            {/* Overall status banner */}
            <div
              className={cn(
                "flex items-center justify-between p-4 rounded-lg",
                result.passed
                  ? "bg-green-500/10 border border-green-500/30"
                  : "bg-red-500/10 border border-red-500/30"
              )}
            >
              <div className="flex items-center gap-3">
                {result.passed ? (
                  <CheckCircle2 className="h-8 w-8 text-green-500" />
                ) : (
                  <XCircle className="h-8 w-8 text-red-500" />
                )}
                <div>
                  <div
                    className={cn(
                      "text-lg font-semibold",
                      result.passed ? "text-green-500" : "text-red-500"
                    )}
                  >
                    {result.passed ? "PREFLIGHT PASSED" : "PREFLIGHT FAILED"}
                  </div>
                  {result.provider_name && (
                    <div className="text-sm text-muted-foreground">
                      Connected to {result.provider_name} ({result.provider_host})
                    </div>
                  )}
                </div>
              </div>

              {checkCounts && (
                <div className="flex items-center gap-3">
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <div className="flex items-center gap-1 text-green-500">
                          <CheckCircle2 className="h-4 w-4" />
                          <span className="font-medium">{checkCounts.passed}</span>
                        </div>
                      </TooltipTrigger>
                      <TooltipContent>Passed checks</TooltipContent>
                    </Tooltip>
                  </TooltipProvider>

                  {checkCounts.warning > 0 && (
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <div className="flex items-center gap-1 text-yellow-500">
                            <AlertTriangle className="h-4 w-4" />
                            <span className="font-medium">{checkCounts.warning}</span>
                          </div>
                        </TooltipTrigger>
                        <TooltipContent>Warnings</TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  )}

                  {checkCounts.failed > 0 && (
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <div className="flex items-center gap-1 text-red-500">
                            <XCircle className="h-4 w-4" />
                            <span className="font-medium">{checkCounts.failed}</span>
                          </div>
                        </TooltipTrigger>
                        <TooltipContent>Failed checks</TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  )}
                </div>
              )}
            </div>

            {/* Mislabel warnings (high priority) */}
            {result.suspected_mislabels.length > 0 && (
              <div className="space-y-2">
                <h4 className="font-medium flex items-center gap-2 text-orange-500">
                  <AlertTriangle className="h-4 w-4" />
                  Suspected Channel Mislabels
                </h4>
                {result.suspected_mislabels.map((m, i) => (
                  <MislabelWarning key={i} mislabel={m} />
                ))}
              </div>
            )}

            {/* Missing channels */}
            {result.missing_channels.length > 0 && (
              <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
                <h4 className="font-medium flex items-center gap-2 text-red-500 mb-2">
                  <Radio className="h-4 w-4" />
                  Missing Required Channels
                </h4>
                <div className="flex flex-wrap gap-2">
                  {result.missing_channels.map((ch) => (
                    <Badge key={ch} variant="outline" className="border-red-500/50 text-red-500">
                      {ch}
                    </Badge>
                  ))}
                </div>
                <p className="text-sm text-muted-foreground mt-2">
                  Enable these channels in Power Core JetDrive settings
                </p>
              </div>
            )}

            {/* Check details (collapsible) */}
            <Collapsible open={showDetails} onOpenChange={setShowDetails}>
              <CollapsibleTrigger asChild>
                <Button variant="ghost" className="w-full justify-between">
                  <span className="flex items-center gap-2">
                    <Zap className="h-4 w-4" />
                    Check Details ({result.checks.length} checks)
                  </span>
                  {showDetails ? (
                    <ChevronUp className="h-4 w-4" />
                  ) : (
                    <ChevronDown className="h-4 w-4" />
                  )}
                </Button>
              </CollapsibleTrigger>
              <CollapsibleContent className="space-y-2 mt-2">
                {result.checks.map((check) => (
                  <CheckItem
                    key={check.name}
                    check={check}
                    expanded={expandedChecks.has(check.name)}
                    onToggle={() => toggleCheckExpanded(check.name)}
                  />
                ))}
              </CollapsibleContent>
            </Collapsible>
          </>
        )}

        {/* Initial state - no result yet */}
        {!result && !isRunning && !error && (
          <div className="text-center py-6 text-muted-foreground">
            <Gauge className="h-12 w-12 mx-auto mb-3 opacity-50" />
            <p>Run preflight check to validate your dyno setup</p>
            <p className="text-sm mt-1">
              This will verify connectivity, channels, and data quality
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default PreflightCheckPanel;
