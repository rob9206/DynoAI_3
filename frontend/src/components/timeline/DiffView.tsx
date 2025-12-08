/**
 * VE Table Time Machine - Diff View Component
 * 
 * Shows cell-by-cell differences between two VE table states.
 */

import { useMemo } from 'react';
import { ArrowRight, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import type { DiffResponse, CellChange } from '@/api/timeline';

// ============================================================================
// Color Scale for Diff Values
// ============================================================================

function getDiffColor(value: number, maxAbsValue: number): string {
  if (Math.abs(value) < 0.001) return 'bg-muted';
  
  const intensity = Math.min(Math.abs(value) / maxAbsValue, 1);
  
  if (value > 0) {
    // Positive changes: green scale
    if (intensity > 0.7) return 'bg-green-500 text-white';
    if (intensity > 0.4) return 'bg-green-400 text-white';
    if (intensity > 0.2) return 'bg-green-300 text-green-900';
    return 'bg-green-200 text-green-800';
  } else {
    // Negative changes: red scale
    if (intensity > 0.7) return 'bg-red-500 text-white';
    if (intensity > 0.4) return 'bg-red-400 text-white';
    if (intensity > 0.2) return 'bg-red-300 text-red-900';
    return 'bg-red-200 text-red-800';
  }
}

// ============================================================================
// Diff Heatmap
// ============================================================================

interface DiffHeatmapProps {
  diff: DiffResponse;
  className?: string;
}

export function DiffHeatmap({ diff, className }: DiffHeatmapProps) {
  const { rpm, load, diff: diffData, summary } = diff;

  // Calculate max absolute value for color scaling
  const maxAbsValue = useMemo(() => {
    let max = 0;
    for (const row of diffData) {
      for (const val of row) {
        max = Math.max(max, Math.abs(val));
      }
    }
    return max || 1;
  }, [diffData]);

  return (
    <div className={cn('overflow-auto', className)}>
      <table className="w-full border-collapse text-xs">
        <thead>
          <tr>
            <th className="p-1 border border-border bg-muted text-muted-foreground font-medium sticky left-0 z-10">
              RPM / kPa
            </th>
            {load.map((kpa) => (
              <th
                key={kpa}
                className="p-1 border border-border bg-muted text-muted-foreground font-medium min-w-[50px]"
              >
                {kpa}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rpm.map((rpmVal, i) => (
            <tr key={rpmVal}>
              <td className="p-1 border border-border bg-muted text-muted-foreground font-medium sticky left-0 z-10">
                {rpmVal}
              </td>
              {diffData[i].map((val, j) => (
                <TooltipProvider key={`${i}-${j}`}>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <td
                        className={cn(
                          'p-1 border border-border text-center font-mono cursor-help transition-colors',
                          getDiffColor(val, maxAbsValue)
                        )}
                      >
                        {val === 0 ? '–' : val > 0 ? `+${val.toFixed(2)}` : val.toFixed(2)}
                      </td>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p className="font-mono">
                        {rpmVal} RPM @ {load[j]} kPa
                      </p>
                      <p className="font-semibold">
                        Change: {val > 0 ? '+' : ''}{val.toFixed(4)}%
                      </p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ============================================================================
// Diff Summary Stats
// ============================================================================

interface DiffSummaryStatsProps {
  summary: DiffResponse['summary'];
}

function DiffSummaryStats({ summary }: DiffSummaryStatsProps) {
  const percentChanged = ((summary.cells_changed / summary.total_cells) * 100).toFixed(1);

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
      <div className="text-center p-3 bg-muted/50 rounded-lg">
        <p className="text-2xl font-bold text-primary">{summary.cells_changed}</p>
        <p className="text-xs text-muted-foreground">Cells Changed</p>
      </div>
      <div className="text-center p-3 bg-muted/50 rounded-lg">
        <p className="text-2xl font-bold">{percentChanged}%</p>
        <p className="text-xs text-muted-foreground">of Table</p>
      </div>
      <div className="text-center p-3 bg-muted/50 rounded-lg">
        <p className="text-2xl font-bold text-blue-500">
          {summary.avg_change > 0 ? '+' : ''}{summary.avg_change.toFixed(2)}%
        </p>
        <p className="text-xs text-muted-foreground">Avg Change</p>
      </div>
      <div className="text-center p-3 bg-muted/50 rounded-lg">
        <p className="text-2xl font-bold text-green-500">
          +{summary.max_change.toFixed(2)}%
        </p>
        <p className="text-xs text-muted-foreground">Max Increase</p>
      </div>
      <div className="text-center p-3 bg-muted/50 rounded-lg">
        <p className="text-2xl font-bold text-red-500">
          {summary.min_change.toFixed(2)}%
        </p>
        <p className="text-xs text-muted-foreground">Max Decrease</p>
      </div>
    </div>
  );
}

// ============================================================================
// Top Changes List
// ============================================================================

interface TopChangesListProps {
  changes: CellChange[];
  maxItems?: number;
}

function TopChangesList({ changes, maxItems = 10 }: TopChangesListProps) {
  const displayChanges = changes.slice(0, maxItems);

  if (displayChanges.length === 0) {
    return (
      <p className="text-sm text-muted-foreground text-center py-4">
        No significant changes detected
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {displayChanges.map((change, index) => (
        <div
          key={`${change.rpm}-${change.load}`}
          className="flex items-center justify-between p-2 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors"
        >
          <div className="flex items-center gap-3">
            <span className="text-xs text-muted-foreground font-mono w-6">
              #{index + 1}
            </span>
            <div>
              <p className="text-sm font-medium">
                {change.rpm} RPM @ {change.load} kPa
              </p>
              <p className="text-xs text-muted-foreground font-mono">
                {change.from.toFixed(2)} <ArrowRight className="h-3 w-3 inline mx-1" /> {change.to.toFixed(2)}
              </p>
            </div>
          </div>
          <Badge
            variant={change.delta > 0 ? 'default' : 'destructive'}
            className="font-mono"
          >
            {change.delta > 0 ? (
              <TrendingUp className="h-3 w-3 mr-1" />
            ) : (
              <TrendingDown className="h-3 w-3 mr-1" />
            )}
            {change.delta > 0 ? '+' : ''}{change.delta.toFixed(2)}%
          </Badge>
        </div>
      ))}
    </div>
  );
}

// ============================================================================
// Main Diff View Component
// ============================================================================

interface DiffViewProps {
  diff: DiffResponse;
  fromLabel?: string;
  toLabel?: string;
  className?: string;
}

export function DiffView({
  diff,
  fromLabel = 'Before',
  toLabel = 'After',
  className,
}: DiffViewProps) {
  const hasChanges = diff.summary.cells_changed > 0;

  return (
    <div className={cn('space-y-6', className)}>
      {/* Header */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                What Changed
                {hasChanges ? (
                  <Badge variant="default">{diff.summary.cells_changed} cells</Badge>
                ) : (
                  <Badge variant="secondary">No changes</Badge>
                )}
              </CardTitle>
              <CardDescription className="flex items-center gap-2 mt-1">
                <span className="font-medium">{fromLabel}</span>
                <ArrowRight className="h-4 w-4" />
                <span className="font-medium">{toLabel}</span>
              </CardDescription>
            </div>
          </div>
        </CardHeader>
      </Card>

      {hasChanges ? (
        <>
          {/* Summary Stats */}
          <DiffSummaryStats summary={diff.summary} />

          {/* Diff Heatmap */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Change Heatmap</CardTitle>
              <CardDescription className="text-xs">
                Green = increased, Red = decreased, Darker = larger change
              </CardDescription>
            </CardHeader>
            <CardContent>
              <DiffHeatmap diff={diff} />
            </CardContent>
          </Card>

          {/* Top Changes */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Largest Changes</CardTitle>
              <CardDescription className="text-xs">
                Cells with the most significant corrections
              </CardDescription>
            </CardHeader>
            <CardContent>
              <TopChangesList changes={diff.changes} />
            </CardContent>
          </Card>
        </>
      ) : (
        <Card className="py-8">
          <CardContent className="text-center">
            <Minus className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <p className="text-lg font-medium">No Changes Detected</p>
            <p className="text-sm text-muted-foreground mt-1">
              The VE table is identical between these two states.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default DiffView;

