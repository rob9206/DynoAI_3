import { memo } from 'react';
import type { MouseEvent } from 'react';
import { AlertTriangle } from 'lucide-react';
import { cn } from '../../lib/utils';

export interface VECellProps {
  correction: number | null;  // null = no data
  hitCount: number;
  isCurrentCell: boolean;
  isAdjacentCell: boolean;
  isSelected: boolean;
  isClampWarning: boolean;    // |correction| >= 7%
  isClampCritical: boolean;   // |correction| >= 15%
  width: number;
  height: number;
  textSize: string;           // computed by parent based on cell dimensions
  background: string;
  textColor: string;
  display: string;
  showUncertainty: boolean;
  onHover: (event: MouseEvent<HTMLDivElement>) => void;
  onLeave: () => void;
}

/** No-data diagonal hatching pattern at 10% opacity */
const NO_DATA_HATCHING =
  'repeating-linear-gradient(45deg, rgba(161,161,170,0.10) 0px, rgba(161,161,170,0.10) 4px, transparent 4px, transparent 8px)';

/** Uncertainty overlay hatching */
const UNCERTAINTY_HATCHING =
  'repeating-linear-gradient(45deg, rgba(255,255,255,0.15) 0, rgba(255,255,255,0.15) 4px, transparent 4px, transparent 8px)';

export const VECell = memo(function VECell({
  correction,
  hitCount,
  isCurrentCell,
  isAdjacentCell,
  isSelected,
  isClampWarning,
  isClampCritical,
  textSize,
  background,
  textColor,
  display,
  showUncertainty,
  onHover,
  onLeave,
}: VECellProps) {
  const isNoData = correction === null || hitCount === 0;

  // Build background image layers
  const bgImages: string[] = [];
  if (isNoData) bgImages.push(NO_DATA_HATCHING);
  if (showUncertainty) bgImages.push(UNCERTAINTY_HATCHING);

  return (
    <div
      className={cn(
        'relative flex items-center justify-center font-mono tabular-nums',
        textSize,
        // Live cell tracking
        isCurrentCell && 'ring-2 ring-orange-500 animate-pulse',
        isAdjacentCell && !isCurrentCell && 'ring-1 ring-orange-500/30',
        // Selection
        isSelected && !isCurrentCell && 'ring-2 ring-blue-500',
        // Clamp warning rings (spec: amber at ±7%, red at ±15%)
        isClampCritical && 'ring-1 ring-red-500',
        !isClampCritical && isClampWarning && 'ring-1 ring-amber-500',
      )}
      style={{
        backgroundColor: background,
        color: textColor,
        backgroundImage: bgImages.length > 0 ? bgImages.join(', ') : undefined,
      }}
      onMouseEnter={onHover}
      onMouseLeave={onLeave}
    >
      <span>{display}</span>
      {/* Clamp warning icon: amber at ±7%, red at ±15% */}
      {isClampCritical && (
        <AlertTriangle className="absolute right-0.5 top-0.5 h-3 w-3 text-red-500" />
      )}
      {!isClampCritical && isClampWarning && (
        <AlertTriangle className="absolute right-0.5 top-0.5 h-3 w-3 text-amber-500" />
      )}
    </div>
  );
}, (prev, next) => {
  // Shallow compare ONLY these props — skip width/height if unchanged
  return prev.correction === next.correction
    && prev.isCurrentCell === next.isCurrentCell
    && prev.isSelected === next.isSelected
    && prev.hitCount === next.hitCount
    && prev.width === next.width
    && prev.height === next.height
    && prev.isClampWarning === next.isClampWarning
    && prev.isClampCritical === next.isClampCritical
    && prev.showUncertainty === next.showUncertainty
    && prev.background === next.background;
});
