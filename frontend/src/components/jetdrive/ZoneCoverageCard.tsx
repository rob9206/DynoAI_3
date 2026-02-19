/**
 * ZoneCoverageCard - Zone-weighted coverage display
 *
 * Shows per-zone coverage breakdown with visual progress bars.
 * Provides the canonical "session readiness" signal for auto-advance.
 */

import React from 'react';
import { TrendingUp, Target, Gauge, AlertTriangle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Progress } from '../ui/progress';
import { Badge } from '../ui/badge';
import { cn } from '../../lib/utils';
import type { CoverageReport, CellZone } from '../../types/veApplyTypes';
import { getZoneDisplayInfo } from '../../utils/veApply';

interface ZoneCoverageCardProps {
  coverageReport: CoverageReport | null;
  totalHits: number;
  targetCoverage?: number;
  targetHits?: number;
  compact?: boolean;
  className?: string;
}

const ZONE_COLORS: Record<CellZone, string> = {
  cruise: 'bg-green-500',
  partThrottle: 'bg-blue-500',
  wot: 'bg-red-500',
  decel: 'bg-purple-500',
  edge: 'bg-zinc-500',
};

const ZONE_TEXT_COLORS: Record<CellZone, string> = {
  cruise: 'text-green-400',
  partThrottle: 'text-blue-400',
  wot: 'text-red-400',
  decel: 'text-purple-400',
  edge: 'text-zinc-400',
};

export function ZoneCoverageCard({
  coverageReport,
  totalHits,
  targetCoverage = 60,
  targetHits = 500,
  compact = false,
  className,
}: ZoneCoverageCardProps) {
  if (!coverageReport) {
    return (
      <Card className={cn("bg-zinc-900/50 border-zinc-800", className)}>
        <CardContent className="py-6 text-center text-zinc-500">
          <Gauge className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p>No coverage data yet</p>
          <p className="text-xs mt-1">Start collecting data to see zone coverage</p>
        </CardContent>
      </Card>
    );
  }

  const { weightedCoveragePct, activeCoveragePct, zoneBreakdown, warnings } = coverageReport;
  const isReady = weightedCoveragePct >= targetCoverage && totalHits >= targetHits;

  // Find lowest coverage zone for suggestion
  const lowestZone = [...zoneBreakdown].sort((a, b) => a.coveragePct - b.coveragePct)[0];
  const suggestion = lowestZone && lowestZone.coveragePct < 50
    ? getSuggestionForZone(lowestZone.zone)
    : null;

  if (compact) {
    return (
      <div className={cn("flex items-center gap-4", className)}>
        {/* Main coverage indicator */}
        <div className="flex items-center gap-2">
          <div className={cn(
            "w-3 h-3 rounded-full",
            isReady ? "bg-green-500 animate-pulse" : "bg-yellow-500"
          )} />
          <span className="text-lg font-bold text-white">{weightedCoveragePct.toFixed(0)}%</span>
          <span className="text-xs text-zinc-500">coverage</span>
        </div>

        {/* Zone dots */}
        <div className="flex gap-1">
          {zoneBreakdown.slice(0, 4).map((zone) => (
            <div
              key={zone.zone}
              className={cn(
                "w-2 h-2 rounded-full",
                zone.coveragePct >= 75 ? ZONE_COLORS[zone.zone] :
                zone.coveragePct >= 50 ? "bg-yellow-500" : "bg-zinc-600"
              )}
              title={`${zone.zone}: ${zone.coveragePct.toFixed(0)}%`}
            />
          ))}
        </div>

        {/* Hits counter */}
        <Badge variant="outline" className="text-cyan-400 border-cyan-400/30">
          {totalHits.toLocaleString()} hits
        </Badge>
      </div>
    );
  }

  return (
    <Card className={cn("bg-zinc-900/50 border-zinc-800", className)}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium text-zinc-300 flex items-center gap-2">
            <TrendingUp className="w-4 h-4" />
            Zone Coverage
          </CardTitle>
          <Badge className={cn(
            isReady
              ? "bg-green-500/20 text-green-400"
              : "bg-yellow-500/20 text-yellow-400"
          )}>
            {isReady ? "Ready" : "Collecting"}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Summary stats */}
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <div className="text-2xl font-bold text-white">{weightedCoveragePct.toFixed(0)}%</div>
            <div className="text-xs text-zinc-500">Weighted</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-zinc-400">{activeCoveragePct.toFixed(0)}%</div>
            <div className="text-xs text-zinc-500">Active</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-cyan-400">{totalHits.toLocaleString()}</div>
            <div className="text-xs text-zinc-500">Hits</div>
          </div>
        </div>

        {/* Zone breakdown */}
        <div className="space-y-2">
          {zoneBreakdown.map((zone) => {
            const zoneInfo = getZoneDisplayInfo(zone.zone);
            return (
              <div key={zone.zone} className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className={cn("font-medium", ZONE_TEXT_COLORS[zone.zone])}>
                    {zoneInfo.label}
                  </span>
                  <span className="text-zinc-500">
                    {zone.sufficientCells}/{zone.totalCells} cells • {zone.coveragePct.toFixed(0)}%
                  </span>
                </div>
                <Progress
                  value={zone.coveragePct}
                  className="h-1.5"
                />
              </div>
            );
          })}
        </div>

        {/* Suggestion */}
        {suggestion && (
          <div className="flex items-start gap-2 p-2 bg-zinc-800/50 rounded-lg">
            <Target className="w-4 h-4 text-cyan-400 mt-0.5 flex-shrink-0" />
            <p className="text-xs text-zinc-400">{suggestion}</p>
          </div>
        )}

        {/* Warnings */}
        {warnings.length > 0 && (
          <div className="space-y-1">
            {warnings.slice(0, 2).map((warning, idx) => (
              <div key={idx} className="flex items-start gap-2 text-xs text-yellow-400">
                <AlertTriangle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                <span>{warning}</span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function getSuggestionForZone(zone: CellZone): string {
  switch (zone) {
    case 'wot':
      return "Focus on WOT pulls - run full-throttle sweeps from 3000 to redline";
    case 'cruise':
      return "Need more cruise data - hold steady 2000-4500 RPM at 40-70 kPa";
    case 'partThrottle':
      return "Part-throttle needs attention - roll-on accelerations at 70-95 kPa";
    case 'decel':
      return "Decel zone low - coast down from high RPM with throttle closed";
    case 'edge':
      return "Edge cells need data - include cold starts and high-RPM runs";
    default:
      return "Continue collecting data across all zones";
  }
}

export default ZoneCoverageCard;
