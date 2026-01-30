/**
 * ApplyPreviewPanel - Before/after comparison with warnings
 *
 * Shows a preview of what applying corrections will do:
 * - Base VE vs Applied VE comparison
 * - Per-cell confidence badges
 * - Block conditions and warnings
 * - Coverage and balance reports
 */

import { useMemo, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle,
  XCircle,
  ChevronDown,
  ChevronUp,
  Info,
  Target,
  Gauge,
  Scale,
} from 'lucide-react';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import {
  ApplyReport,
  VEBoundsPreset,
  DualCylinderVE,
  DualCylinderCorrections,
  DualCylinderHits,
} from '../../types/veApplyTypes';
import {
  calculateApply,
  getApplySummary,
  getCoverageGrade,
  getBalanceSummary,
  getBoundsPresetInfo,
  VE_BOUNDS_PRESETS,
} from '../../utils/veApply';
import { ConfidenceBadge, ConfidenceLegend } from './ConfidenceBadge';

interface ApplyPreviewPanelProps {
  baseVE: DualCylinderVE | null;
  corrections: DualCylinderCorrections;
  hitCounts: DualCylinderHits;
  rpmAxis: number[];
  mapAxis: number[];
  boundsPreset?: VEBoundsPreset;
  onBoundsPresetChange?: (preset: VEBoundsPreset) => void;
  onApply?: (report: ApplyReport) => void;
  onCancel?: () => void;
}

export function ApplyPreviewPanel({
  baseVE,
  corrections,
  hitCounts,
  rpmAxis,
  mapAxis,
  boundsPreset = 'na_harley',
  onBoundsPresetChange,
  onApply,
  onCancel,
}: ApplyPreviewPanelProps) {
  const [showDetails, setShowDetails] = useState(false);
  const [selectedCylinder, setSelectedCylinder] = useState<'front' | 'rear'>('front');

  // Calculate apply report
  const report = useMemo(
    () => calculateApply(baseVE, corrections, hitCounts, rpmAxis, mapAxis, boundsPreset),
    [baseVE, corrections, hitCounts, rpmAxis, mapAxis, boundsPreset]
  );

  const summary = getApplySummary(report);
  const coverageGrade = getCoverageGrade(report.coverageReport.weightedCoveragePct);
  const balanceSummary = getBalanceSummary(report.balanceReport);
  const boundsInfo = getBoundsPresetInfo(boundsPreset);

  // Status icon
  const StatusIcon = summary.status === 'blocked' ? XCircle :
    summary.status === 'warnings' ? AlertTriangle : CheckCircle;

  return (
    <div className="bg-zinc-900/80 border border-zinc-800 rounded-lg overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-zinc-800 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-purple-500/20 flex items-center justify-center">
            <Target className="w-4 h-4 text-purple-400" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">Apply Preview</h3>
            <p className="text-[10px] text-zinc-500">Review changes before applying</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <StatusIcon className={`w-5 h-5 ${summary.statusColor}`} />
          <span className={`text-sm font-medium ${summary.statusColor}`}>
            {summary.status === 'blocked' ? 'Blocked' :
              summary.status === 'warnings' ? 'Warnings' : 'Ready'}
          </span>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="px-4 py-3 grid grid-cols-4 gap-4 border-b border-zinc-800 bg-zinc-900/50">
        <div className="text-center">
          <div className="text-lg font-bold text-white">{report.totalCells - report.skippedCells}</div>
          <div className="text-[10px] text-zinc-500">Cells Updated</div>
        </div>
        <div className="text-center">
          <div className="text-lg font-bold text-zinc-400">{report.skippedCells}</div>
          <div className="text-[10px] text-zinc-500">Cells Skipped</div>
        </div>
        <div className="text-center">
          <div className="text-lg font-bold text-yellow-400">{report.clampedCells}</div>
          <div className="text-[10px] text-zinc-500">Cells Clamped</div>
        </div>
        <div className="text-center">
          <div className={`text-lg font-bold ${coverageGrade.color}`}>{coverageGrade.grade}</div>
          <div className="text-[10px] text-zinc-500">Coverage Grade</div>
        </div>
      </div>

      {/* Block Conditions */}
      {report.blockReasons.length > 0 && (
        <div className="px-4 py-3 bg-red-500/10 border-b border-red-500/30">
          <div className="flex items-start gap-2">
            <XCircle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
            <div>
              <div className="text-sm font-medium text-red-400">Cannot Apply</div>
              <ul className="mt-1 space-y-1">
                {report.blockReasons.map((reason, idx) => (
                  <li key={idx} className="text-xs text-red-300">{reason.message}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Warnings */}
      {report.warnings.length > 0 && report.blockReasons.length === 0 && (
        <div className="px-4 py-3 bg-yellow-500/10 border-b border-yellow-500/30">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-yellow-400 mt-0.5 flex-shrink-0" />
            <div>
              <div className="text-sm font-medium text-yellow-400">
                {report.warnings.length} Warning{report.warnings.length > 1 ? 's' : ''}
              </div>
              <ul className="mt-1 space-y-1 max-h-24 overflow-y-auto">
                {report.warnings.slice(0, 5).map((warning, idx) => (
                  <li key={idx} className="text-xs text-yellow-300">{warning}</li>
                ))}
                {report.warnings.length > 5 && (
                  <li className="text-xs text-yellow-500 italic">
                    +{report.warnings.length - 5} more warnings
                  </li>
                )}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Coverage & Balance Cards */}
      <div className="px-4 py-3 grid grid-cols-2 gap-3 border-b border-zinc-800">
        {/* Coverage Card */}
        <div className="bg-zinc-800/50 rounded-lg p-3">
          <div className="flex items-center gap-2 mb-2">
            <Gauge className="w-4 h-4 text-blue-400" />
            <span className="text-xs font-medium text-zinc-300">Coverage</span>
          </div>
          <div className="flex items-baseline gap-1 mb-1">
            <span className={`text-xl font-bold ${coverageGrade.color}`}>
              {report.coverageReport.weightedCoveragePct.toFixed(0)}%
            </span>
            <span className="text-xs text-zinc-500">weighted</span>
          </div>
          <p className="text-[10px] text-zinc-500">{coverageGrade.description}</p>
        </div>

        {/* Balance Card */}
        <div className="bg-zinc-800/50 rounded-lg p-3">
          <div className="flex items-center gap-2 mb-2">
            <Scale className="w-4 h-4 text-purple-400" />
            <span className="text-xs font-medium text-zinc-300">Cylinder Balance</span>
          </div>
          <div className="flex items-baseline gap-1 mb-1">
            <span className={`text-xl font-bold ${
              balanceSummary.status === 'good' ? 'text-green-400' :
              balanceSummary.status === 'warning' ? 'text-yellow-400' : 'text-red-400'
            }`}>
              {balanceSummary.label}
            </span>
          </div>
          <p className="text-[10px] text-zinc-500">{balanceSummary.description}</p>
        </div>
      </div>

      {/* VE Bounds Selector */}
      <div className="px-4 py-3 border-b border-zinc-800">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Info className="w-4 h-4 text-zinc-500" />
            <span className="text-xs text-zinc-400">VE Bounds:</span>
            <span className="text-xs font-medium text-zinc-300">{boundsInfo.name}</span>
            <span className="text-xs text-zinc-500">({boundsInfo.range})</span>
          </div>
          {onBoundsPresetChange && (
            <select
              value={boundsPreset}
              onChange={(e) => onBoundsPresetChange(e.target.value as VEBoundsPreset)}
              className="text-xs bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-zinc-300"
            >
              {(Object.keys(VE_BOUNDS_PRESETS) as VEBoundsPreset[]).map((preset) => {
                const info = getBoundsPresetInfo(preset);
                return (
                  <option key={preset} value={preset}>
                    {info.name} ({info.range})
                  </option>
                );
              })}
            </select>
          )}
        </div>
      </div>

      {/* Expandable Details */}
      <div className="px-4 py-2 border-b border-zinc-800">
        <button
          onClick={() => setShowDetails(!showDetails)}
          className="flex items-center gap-2 text-xs text-zinc-400 hover:text-zinc-300"
        >
          {showDetails ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          {showDetails ? 'Hide' : 'Show'} Zone Breakdown
        </button>
      </div>

      {showDetails && (
        <div className="px-4 py-3 border-b border-zinc-800 bg-zinc-900/30">
          <div className="mb-2 text-xs text-zinc-400">Zone Coverage Breakdown</div>
          <div className="space-y-2">
            {report.coverageReport.zoneBreakdown.map((zone) => (
              <div key={zone.zone} className="flex items-center gap-3">
                <span className="text-xs text-zinc-500 w-20 capitalize">{zone.zone}</span>
                <div className="flex-1 h-2 bg-zinc-800 rounded overflow-hidden">
                  <div
                    className={`h-full ${
                      zone.coveragePct >= 75 ? 'bg-green-500' :
                      zone.coveragePct >= 50 ? 'bg-yellow-500' :
                      zone.coveragePct >= 25 ? 'bg-orange-500' : 'bg-red-500'
                    }`}
                    style={{ width: `${zone.coveragePct}%` }}
                  />
                </div>
                <span className="text-xs text-zinc-400 w-16 text-right">
                  {zone.sufficientCells}/{zone.totalCells}
                </span>
                <span className="text-xs text-zinc-500 w-12 text-right">
                  {zone.coveragePct.toFixed(0)}%
                </span>
              </div>
            ))}
          </div>
          <div className="mt-3">
            <ConfidenceLegend />
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="px-4 py-3 flex items-center justify-between bg-zinc-900/30">
        <Button
          variant="ghost"
          size="sm"
          onClick={onCancel}
          className="text-zinc-400 hover:text-zinc-300"
        >
          Cancel
        </Button>
        <div className="flex items-center gap-2">
          {summary.canApply && (
            <Badge variant="outline" className="text-[10px] border-zinc-700 text-zinc-400">
              {report.totalCells - report.skippedCells} cells will be modified
            </Badge>
          )}
          <Button
            variant={summary.canApply ? 'default' : 'secondary'}
            size="sm"
            disabled={!summary.canApply}
            onClick={() => onApply?.(report)}
            className={summary.canApply ?
              'bg-green-600 hover:bg-green-500 text-white' :
              'opacity-50 cursor-not-allowed'
            }
          >
            {summary.canApply ? 'Apply Corrections' : 'Cannot Apply'}
          </Button>
        </div>
      </div>
    </div>
  );
}

export default ApplyPreviewPanel;
