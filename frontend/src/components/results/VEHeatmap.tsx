import React, { useMemo, useState, useCallback, useRef } from 'react';
import { cn } from '@/lib/utils';
import { getColorForValue, getTextColorForBackground, isValueClamped } from '@/lib/colorScale';

interface VEHeatmapProps {
  data: number[][];              // 2D array of VE correction values
  rowLabels: string[];           // RPM values (e.g., ["1000", "1500", "2000", ...])
  colLabels: string[];           // TPS/Load values (e.g., ["0", "10", "20", ...])
  colorMode?: 'diverging' | 'sequential';
  clampLimit?: number;           // Default: 7 for production mode
  showClampIndicators?: boolean; // Show visual indicator for clamped cells
  showValues?: boolean;          // Show numeric values in cells (default: true)
  valueDecimals?: number;        // Default: 1
  valueLabel?: string;           // Default depends on colorMode
  tooltipLoadUnit?: string;      // Default: 'kPa'
  onCellClick?: (row: number, col: number, value: number) => void;
  onCellHover?: (row: number, col: number, value: number) => void;
  highlightCell?: { row: number; col: number };  // Optional cell to highlight
  title?: string;
  className?: string;
}

interface TooltipState {
  row: number;
  col: number;
  value: number;
  x: number;
  y: number;
}

export function VEHeatmap({
  data,
  rowLabels,
  colLabels,
  colorMode = 'diverging',
  clampLimit = 7,
  showClampIndicators = true,
  showValues = true,
  valueDecimals = 1,
  valueLabel,
  tooltipLoadUnit = 'kPa',
  onCellClick,
  onCellHover,
  highlightCell,
  title,
  className
}: VEHeatmapProps): React.JSX.Element {
  const [hoveredCell, setHoveredCell] = useState<{ row: number; col: number } | null>(null);
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const { sequentialMin, sequentialMax } = useMemo(() => {
    if (colorMode !== 'sequential') return { sequentialMin: 0, sequentialMax: 1 };
    let min = Number.POSITIVE_INFINITY;
    let max = Number.NEGATIVE_INFINITY;
    for (const row of data) {
      for (const v of row) {
        if (v === null || Number.isNaN(v)) continue;
        min = Math.min(min, v);
        max = Math.max(max, v);
      }
    }
    if (!Number.isFinite(min) || !Number.isFinite(max) || min === max) {
      return { sequentialMin: 0, sequentialMax: 1 };
    }
    return { sequentialMin: min, sequentialMax: max };
  }, [colorMode, data]);

  const handleCellClick = useCallback((row: number, col: number, value: number) => {
    if (onCellClick) {
      onCellClick(row, col, value);
    }
  }, [onCellClick]);

  const handleCellMouseEnter = useCallback((
    row: number,
    col: number,
    value: number,
    event: React.MouseEvent<HTMLDivElement>
  ) => {
    setHoveredCell({ row, col });

    // Calculate tooltip position using fixed positioning
    const cellRect = event.currentTarget.getBoundingClientRect();

    setTooltip({
      row,
      col,
      value,
      x: cellRect.left + cellRect.width / 2,
      y: cellRect.top - 8
    });

    if (onCellHover) {
      onCellHover(row, col, value);
    }
  }, [onCellHover]);

  const handleCellMouseLeave = useCallback(() => {
    setHoveredCell(null);
    setTooltip(null);
  }, []);

  const isHighlighted = useCallback((row: number, col: number) => {
    return highlightCell?.row === row && highlightCell?.col === col;
  }, [highlightCell]);

  const isHovered = useCallback((row: number, col: number) => {
    return hoveredCell?.row === row && hoveredCell?.col === col;
  }, [hoveredCell]);

  const content = (
    <div className="overflow-x-auto rounded-lg border border-zinc-800 bg-zinc-900/50 relative" ref={containerRef}>
      <table className="border-collapse w-full text-xs">
        <thead>
          <tr className="bg-zinc-900/80">
            <th className="sticky left-0 z-10 min-w-[75px] w-[75px] h-10 px-3 py-2 text-left font-medium text-zinc-400 bg-zinc-900/80 border-r border-zinc-800/80">
              <div className="flex flex-col items-start">
                <span>RPM →</span>
                <span className="text-[9px] text-zinc-500">MAP ↓</span>
              </div>
            </th>
            {colLabels.map((label, colIndex) => (
              <th
                key={colIndex}
                className="min-w-[48px] w-[48px] h-10 px-1.5 py-2 text-center font-bold text-zinc-300 border-l border-zinc-800/50 whitespace-nowrap"
              >
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, rowIndex) => (
            <tr
              key={rowIndex}
              className={cn(
                rowIndex % 2 === 0 ? 'bg-zinc-900/30' : 'bg-zinc-900/10',
                'border-t border-zinc-800/50'
              )}
            >
              <td
                className={cn(
                  'sticky left-0 z-10 min-w-[75px] w-[75px] px-3 py-2 font-mono font-bold text-zinc-300 border-r border-zinc-800/80',
                  rowIndex % 2 === 0 ? 'bg-zinc-900/30' : 'bg-zinc-900/10'
                )}
              >
                <div className="flex flex-col items-start">
                  <span>{rowLabels[rowIndex]}</span>
                  <span className="text-[9px] text-zinc-500 font-normal">RPM</span>
                </div>
              </td>

              {row.map((value, colIndex) => {
                const bgColor = colorMode === 'sequential'
                  ? getSequentialColor(value, sequentialMin, sequentialMax)
                  : getColorForValue(value, { clampLimit });
                const textColor = getTextColorForBackground(bgColor);
                const isClamped = colorMode === 'diverging' && showClampIndicators && isValueClamped(value, clampLimit);
                const highlighted = isHighlighted(rowIndex, colIndex);
                const hovered = isHovered(rowIndex, colIndex);

                return (
                  <td
                    key={colIndex}
                    className={cn(
                      'min-w-[48px] w-[48px] h-12 px-1 py-1.5 text-center font-mono transition-all duration-75 cursor-pointer border-l border-zinc-800/30 relative align-middle',
                      hovered && 'ring-2 ring-orange-500 ring-inset scale-105 z-20',
                      highlighted && 'ring-2 ring-orange-500 ring-inset bg-orange-500/40 z-20',
                      onCellClick && 'hover:scale-105'
                    )}
                    style={{
                      backgroundColor: bgColor,
                      color: textColor
                    }}
                    onClick={() => handleCellClick(rowIndex, colIndex, value)}
                    onMouseEnter={(e) => handleCellMouseEnter(rowIndex, colIndex, value, e)}
                    onMouseLeave={handleCellMouseLeave}
                    title={`${rowLabels[rowIndex]} RPM @ ${colLabels[colIndex]} ${tooltipLoadUnit}\n${(valueLabel ?? (colorMode === 'sequential' ? 'Value' : 'Correction'))}: ${colorMode === 'sequential' ? '' : (value > 0 ? '+' : '')}${value?.toFixed(2) ?? 'N/A'}${colorMode === 'sequential' ? '' : '%'}`}
                    aria-label={`RPM ${rowLabels[rowIndex]}, Load ${colLabels[colIndex]}: ${value?.toFixed(1) ?? 'N/A'}%`}
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        handleCellClick(rowIndex, colIndex, value);
                      }
                    }}
                  >
                    {/* Clamped indicator triangle */}
                    {isClamped && (
                      <div
                        className="absolute top-0 right-0 w-0 h-0 border-t-[6px] border-t-yellow-500 border-l-[6px] border-l-transparent"
                        aria-label="Clamped value"
                      />
                    )}
                    {/* Value text */}
                    {showValues && value !== null && !Number.isNaN(value) ? (
                      <div className="flex items-center justify-center h-full leading-tight">
                        <div className="text-xs whitespace-nowrap">
                          {colorMode === 'sequential' ? value.toFixed(valueDecimals) : `${value >= 0 ? '+' : ''}${value.toFixed(valueDecimals)}%`}
                        </div>
                      </div>
                    ) : (
                      <div className="flex items-center justify-center h-full text-zinc-700/30 text-base">·</div>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>

      {/* Legend with dot indicators (matching Live VE Table style) */}
      {colorMode === 'diverging' && (
        <div className="flex items-center justify-between text-xs text-zinc-500 px-1 mt-2">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1">
              <div className="w-3 h-3 rounded bg-red-500/50" />
              <span>Lean</span>
            </span>
            <span className="flex items-center gap-1">
              <div className="w-3 h-3 rounded bg-green-500/40" />
              <span>OK</span>
            </span>
            <span className="flex items-center gap-1">
              <div className="w-3 h-3 rounded bg-blue-500/50" />
              <span>Rich</span>
            </span>
          </div>
        </div>
      )}

      {/* Shared tooltip - using fixed positioning to prevent clipping */}
      {tooltip && (
        <div
          className="fixed z-[9999] bg-zinc-800 border border-zinc-700 px-3 py-2 text-xs rounded-lg shadow-xl pointer-events-none animate-in fade-in zoom-in-95 duration-100"
          style={{
            left: tooltip.x,
            top: tooltip.y,
            transform: 'translate(-50%, -100%)'
          }}
        >
          <div className="space-y-1">
            <div className="font-semibold text-zinc-100">
              {(valueLabel ?? (colorMode === 'sequential' ? 'Value' : 'Correction'))}: {colorMode === 'sequential' ? '' : (tooltip.value > 0 ? '+' : '')}
              {tooltip.value?.toFixed(2) ?? 'N/A'}{colorMode === 'sequential' ? '' : '%'}
            </div>
            <div className="text-zinc-400 space-y-0.5">
              <div>RPM: {rowLabels[tooltip.row]}</div>
              <div>Load: {colLabels[tooltip.col]} {tooltipLoadUnit}</div>
            </div>
            {colorMode === 'diverging' && showClampIndicators && isValueClamped(tooltip.value, clampLimit) && (
              <div className="text-yellow-500 font-medium text-xs">
                ⚠ Clamped (±{clampLimit}% limit)
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );

  if (title) {
    return (
      <div className={cn('space-y-3', className)}>
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-white">{title}</h3>
        </div>
        {content}
      </div>
    );
  }

  return (
    <div className={cn('relative', className)}>
      {content}
    </div>
  );
}

function getSequentialColor(value: number, min: number, max: number): string {
  if (value === null || Number.isNaN(value)) {
    return 'rgb(75, 85, 99)'; // Gray for missing data
  }
  const t = Math.max(0, Math.min(1, (value - min) / (max - min)));

  // Soft sequential palette: near-white to deep blue
  const start: [number, number, number] = [255, 255, 255];
  const end: [number, number, number] = [37, 99, 235]; // Blue-600-ish
  const r = Math.round(start[0] + (end[0] - start[0]) * t);
  const g = Math.round(start[1] + (end[1] - start[1]) * t);
  const b = Math.round(start[2] + (end[2] - start[2]) * t);
  return `rgb(${r}, ${g}, ${b})`;
}

