import React, { useState, useCallback, useRef } from 'react';
import { cn } from '@/lib/utils';
import { getColorForValue, getTextColorForBackground, isValueClamped } from '@/lib/colorScale';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface VEHeatmapProps {
  data: number[][];              // 2D array of VE correction values
  rowLabels: string[];           // RPM values (e.g., ["1000", "1500", "2000", ...])
  colLabels: string[];           // TPS/Load values (e.g., ["0", "10", "20", ...])
  clampLimit?: number;           // Default: 7 for production mode
  showClampIndicators?: boolean; // Show visual indicator for clamped cells
  showValues?: boolean;          // Show numeric values in cells (default: true)
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
  clampLimit = 7,
  showClampIndicators = true,
  showValues = true,
  onCellClick,
  onCellHover,
  highlightCell,
  title,
  className
}: VEHeatmapProps): React.JSX.Element {
  const [hoveredCell, setHoveredCell] = useState<{ row: number; col: number } | null>(null);
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

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
    <div className="overflow-x-auto relative" ref={containerRef}>
      <div className="inline-block min-w-max">
        {/* Column headers */}
        <div className="flex">
          {/* Empty corner cell */}
          <div className="w-12 h-6 flex-shrink-0" />
          {/* Column labels */}
          {colLabels.map((label, colIndex) => (
            <div
              key={colIndex}
              className="min-w-[32px] w-8 h-6 flex items-center justify-center text-[10px] font-mono text-muted-foreground"
            >
              {label}
            </div>
          ))}
        </div>

        {/* Rows */}
        {data.map((row, rowIndex) => (
          <div key={rowIndex} className="flex">
            {/* Row label */}
            <div className="w-12 h-8 flex-shrink-0 flex items-center justify-end pr-2 text-[10px] font-mono text-muted-foreground">
              {rowLabels[rowIndex]}
            </div>

            {/* Cells */}
            {row.map((value, colIndex) => {
              const bgColor = getColorForValue(value, { clampLimit });
              const textColor = getTextColorForBackground(bgColor);
              const isClamped = showClampIndicators && isValueClamped(value, clampLimit);
              const highlighted = isHighlighted(rowIndex, colIndex);
              const hovered = isHovered(rowIndex, colIndex);

              return (
                <div
                  key={colIndex}
                  className={cn(
                    'min-w-[32px] w-8 h-8 flex items-center justify-center cursor-pointer transition-transform duration-150 relative border border-border/30',
                    hovered && 'scale-110 z-10 shadow-lg',
                    highlighted && 'ring-2 ring-primary ring-offset-1',
                    onCellClick && 'hover:scale-105'
                  )}
                  style={{
                    backgroundColor: bgColor,
                    color: textColor
                  }}
                  onClick={() => handleCellClick(rowIndex, colIndex, value)}
                  onMouseEnter={(e) => handleCellMouseEnter(rowIndex, colIndex, value, e)}
                  onMouseLeave={handleCellMouseLeave}
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
                  {showValues && value !== null && !Number.isNaN(value) && (
                    <span className="text-[9px] font-mono leading-none">
                      {value.toFixed(1)}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        ))}

        {/* Axis labels */}
        <div className="flex mt-2">
          <div className="w-12 flex-shrink-0" />
          <div className="flex-1 text-center text-xs text-muted-foreground">
            TPS/Load
          </div>
        </div>
      </div>

      {/* Y-axis label */}
      <div
        className="absolute left-0 top-1/2 text-xs text-muted-foreground"
        style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg) translateY(50%) translateX(8px)' }}
      >
        <span>RPM</span>
      </div>

      {/* Shared tooltip - using fixed positioning to prevent clipping */}
      {tooltip && (
        <div
          className="fixed z-[9999] bg-popover border border-border px-3 py-2 text-xs rounded-lg shadow-xl pointer-events-none animate-in fade-in zoom-in-95 duration-100"
          style={{
            left: tooltip.x,
            top: tooltip.y,
            transform: 'translate(-50%, -100%)'
          }}
        >
          <div className="space-y-1">
            <div className="font-semibold text-foreground">
              Correction: {tooltip.value > 0 ? '+' : ''}{tooltip.value?.toFixed(2) ?? 'N/A'}%
            </div>
            <div className="text-muted-foreground space-y-0.5">
              <div>RPM: {rowLabels[tooltip.row]}</div>
              <div>Load: {colLabels[tooltip.col]} kPa</div>
            </div>
            {showClampIndicators && isValueClamped(tooltip.value, clampLimit) && (
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
      <Card className={cn('overflow-visible', className)}>
        <CardHeader>
          <CardTitle>{title}</CardTitle>
        </CardHeader>
        <CardContent className="relative overflow-x-auto">
          {content}
        </CardContent>
      </Card>
    );
  }

  return (
    <div className={cn('relative overflow-x-auto', className)}>
      {content}
    </div>
  );
}
