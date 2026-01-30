/**
 * ConfidenceBadge - Multi-purpose confidence indicator
 *
 * Supports two interfaces:
 * 1. VE Apply confidence (high/medium/low/skip) - used in ApplyPreviewPanel
 * 2. Confidence Report - used in run results display
 */

import { Confidence } from '../../types/veApplyTypes';
import { getConfidenceBadge as getVEConfidenceBadge } from '../../utils/veApply';
import type { ConfidenceReport } from '../ConfidenceScoreCard';
import { Badge } from '../ui/badge';

// Type guard to check if confidence is a ConfidenceReport
function isConfidenceReport(
  confidence: Confidence | ConfidenceReport | unknown
): confidence is ConfidenceReport {
  return (
    typeof confidence === 'object' &&
    confidence !== null &&
    'letter_grade' in confidence
  );
}

export interface ConfidenceBadgeProps {
  // Accepts either VE Apply Confidence string or full ConfidenceReport
  confidence: Confidence | ConfidenceReport;
  // For ConfidenceReport mode
  compact?: boolean;
  // For VE Apply mode
  size?: 'sm' | 'md' | 'lg';
  showTooltip?: boolean;
}

export function ConfidenceBadge({
  confidence,
  compact = false,
  size = 'sm',
  showTooltip = true,
}: ConfidenceBadgeProps) {
  // Handle ConfidenceReport type (original usage)
  if (isConfidenceReport(confidence)) {
    const getGradeColor = (grade: string) => {
      switch (grade) {
        case 'A':
          return 'border-green-500/30 text-green-400 bg-green-500/10';
        case 'B':
          return 'border-blue-500/30 text-blue-400 bg-blue-500/10';
        case 'C':
          return 'border-yellow-500/30 text-yellow-400 bg-yellow-500/10';
        case 'D':
          return 'border-red-500/30 text-red-400 bg-red-500/10';
        default:
          return 'border-zinc-500/30 text-zinc-400 bg-zinc-500/10';
      }
    };

    if (compact) {
      return (
        <Badge
          variant="outline"
          className={`text-[10px] ${getGradeColor(confidence.letter_grade)}`}
          title={`${confidence.grade_description} (${confidence.overall_score.toFixed(0)}%)`}
        >
          {confidence.letter_grade}
        </Badge>
      );
    }

    return (
      <div className="flex items-center gap-2">
        <Badge
          variant="outline"
          className={`${getGradeColor(confidence.letter_grade)}`}
        >
          Grade: {confidence.letter_grade}
        </Badge>
        <span className="text-xs text-zinc-400">
          {confidence.overall_score.toFixed(0)}%
        </span>
      </div>
    );
  }

  // Handle VE Apply Confidence type (new usage)
  const badge = getVEConfidenceBadge(confidence as Confidence);

  const sizeClasses = {
    sm: 'w-4 h-4 text-[10px]',
    md: 'w-5 h-5 text-xs',
    lg: 'w-6 h-6 text-sm',
  };

  return (
    <span
      className={`
        inline-flex items-center justify-center
        rounded font-bold
        ${sizeClasses[size]}
        ${badge.bgColor}
        ${badge.color}
      `}
      title={showTooltip ? badge.description : undefined}
    >
      {badge.label}
    </span>
  );
}

/**
 * Confidence legend for display in panels
 */
export function ConfidenceLegend() {
  const levels: Confidence[] = ['high', 'medium', 'low', 'skip'];

  return (
    <div className="flex items-center gap-3 text-xs text-zinc-400">
      <span className="text-zinc-500">Confidence:</span>
      {levels.map((level) => {
        const badge = getVEConfidenceBadge(level);
        return (
          <span key={level} className="flex items-center gap-1">
            <ConfidenceBadge confidence={level} showTooltip={false} />
            <span className={badge.color}>{badge.description.split(' ')[0]}</span>
          </span>
        );
      })}
    </div>
  );
}

export default ConfidenceBadge;
