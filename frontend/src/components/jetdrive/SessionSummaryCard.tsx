/**
 * SessionSummaryCard - Final results display for completed tuning sessions
 *
 * Shows comprehensive session statistics including:
 * - Cell breakdown (updated/skipped/clamped/bounded)
 * - Coverage stats per zone
 * - Balance report
 * - Export download links
 */

import React from 'react';
import { Download, FileText, FileJson, CheckCircle2, AlertTriangle, Clock, Zap } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Progress } from '../ui/progress';
import { cn } from '../../lib/utils';
import type { ApplyReport, CoverageReport, BalanceReport } from '../../types/veApplyTypes';

interface SessionSummaryCardProps {
  applyReport: ApplyReport;
  sessionDuration?: number; // in seconds
  pullCount?: number;
  onDownloadPVV?: () => void;
  onDownloadCSV?: () => void;
  onDownloadJSON?: () => void;
  onDownloadAll?: () => void;
  className?: string;
}

export function SessionSummaryCard({
  applyReport,
  sessionDuration,
  pullCount,
  onDownloadPVV,
  onDownloadCSV,
  onDownloadJSON,
  onDownloadAll,
  className,
}: SessionSummaryCardProps) {
  const {
    totalCells,
    skippedCells,
    clampedCells,
    boundedCells,
    coverageReport,
    balanceReport,
    warnings,
  } = applyReport;

  const updatedCells = totalCells - skippedCells;
  const updatePct = totalCells > 0 ? (updatedCells / totalCells) * 100 : 0;

  // Format duration
  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
  };

  return (
    <Card className={cn("bg-zinc-900/50 border-zinc-800", className)}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium text-zinc-300 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-green-400" />
            Session Complete
          </CardTitle>
          <Badge className="bg-green-500/20 text-green-400">
            {updatedCells} cells updated
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Session Stats */}
        {(sessionDuration || pullCount) && (
          <div className="flex items-center gap-6 text-sm text-zinc-400">
            {sessionDuration && (
              <div className="flex items-center gap-1.5">
                <Clock className="w-4 h-4" />
                <span>{formatDuration(sessionDuration)}</span>
              </div>
            )}
            {pullCount && (
              <div className="flex items-center gap-1.5">
                <Zap className="w-4 h-4" />
                <span>{pullCount} pulls</span>
              </div>
            )}
          </div>
        )}

        {/* Cell Breakdown */}
        <div>
          <h4 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">
            Cell Breakdown
          </h4>
          <div className="grid grid-cols-4 gap-4 text-center">
            <div>
              <div className="text-2xl font-bold text-green-400">{updatedCells}</div>
              <div className="text-xs text-zinc-500">Updated</div>
              <div className="text-[10px] text-zinc-600">{updatePct.toFixed(0)}%</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-zinc-500">{skippedCells}</div>
              <div className="text-xs text-zinc-500">Skipped</div>
              <div className="text-[10px] text-zinc-600">low data</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-yellow-400">{clampedCells}</div>
              <div className="text-xs text-zinc-500">Clamped</div>
              <div className="text-[10px] text-zinc-600">limited</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-orange-400">{boundedCells}</div>
              <div className="text-xs text-zinc-500">Bounded</div>
              <div className="text-[10px] text-zinc-600">VE limits</div>
            </div>
          </div>
        </div>

        {/* Coverage Stats */}
        {coverageReport && (
          <div>
            <h4 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">
              Coverage Achieved
            </h4>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm text-zinc-400">Weighted Coverage</span>
                <span className="text-sm font-medium text-white">
                  {coverageReport.weightedCoveragePct.toFixed(0)}%
                </span>
              </div>
              <Progress value={coverageReport.weightedCoveragePct} className="h-2" />

              <div className="grid grid-cols-4 gap-2 mt-3">
                {coverageReport.zoneBreakdown.slice(0, 4).map((zone) => (
                  <div key={zone.zone} className="text-center">
                    <div className="text-xs font-medium text-zinc-300 capitalize">
                      {zone.zone === 'partThrottle' ? 'P/T' : zone.zone}
                    </div>
                    <div className="text-xs text-zinc-500">{zone.coveragePct.toFixed(0)}%</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Balance Report */}
        {balanceReport && (
          <div>
            <h4 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">
              Cylinder Balance
            </h4>
            <div className="flex items-center justify-between p-3 bg-zinc-800/50 rounded-lg">
              <div>
                <div className="text-sm text-zinc-300">Front/Rear Systematic</div>
                <div className="text-xs text-zinc-500">
                  {balanceReport.rawWorstCell && (
                    <>Worst: {balanceReport.rawMaxLocalizedDiffPct.toFixed(1)}% at cell</>
                  )}
                </div>
              </div>
              <Badge className={cn(
                balanceReport.warnings.length === 0
                  ? "bg-green-500/20 text-green-400"
                  : "bg-yellow-500/20 text-yellow-400"
              )}>
                {balanceReport.rawSystematicBiasPct >= 0 ? '+' : ''}
                {balanceReport.rawSystematicBiasPct.toFixed(1)}%
              </Badge>
            </div>
          </div>
        )}

        {/* Warnings */}
        {warnings.length > 0 && (
          <div>
            <h4 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-2">
              Warnings ({warnings.length})
            </h4>
            <div className="space-y-1 max-h-24 overflow-y-auto">
              {warnings.slice(0, 5).map((warning, idx) => (
                <div key={idx} className="flex items-start gap-2 text-xs text-yellow-400">
                  <AlertTriangle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                  <span className="line-clamp-1">{warning}</span>
                </div>
              ))}
              {warnings.length > 5 && (
                <div className="text-xs text-zinc-500">
                  +{warnings.length - 5} more warnings
                </div>
              )}
            </div>
          </div>
        )}

        {/* Download Buttons */}
        <div className="space-y-3 pt-2">
          <Button
            onClick={onDownloadAll || onDownloadPVV}
            className="w-full bg-gradient-to-r from-green-600 to-green-500 hover:from-green-500 hover:to-green-400"
          >
            <Download className="w-4 h-4 mr-2" />
            Download All Formats
          </Button>

          <div className="grid grid-cols-3 gap-2">
            <Button
              onClick={onDownloadPVV}
              variant="outline"
              size="sm"
              className="border-zinc-700"
            >
              <FileText className="w-3 h-3 mr-1" />
              PVV
            </Button>
            <Button
              onClick={onDownloadCSV}
              variant="outline"
              size="sm"
              className="border-zinc-700"
            >
              <FileText className="w-3 h-3 mr-1" />
              CSV
            </Button>
            <Button
              onClick={onDownloadJSON}
              variant="outline"
              size="sm"
              className="border-zinc-700"
            >
              <FileJson className="w-3 h-3 mr-1" />
              JSON
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default SessionSummaryCard;
