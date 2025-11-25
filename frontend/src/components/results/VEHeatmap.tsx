import { useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { getColorForValue, getTextColorForBackground, isValueClamped } from '@/lib/colorScale';
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip';
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
}: VEHeatmapProps): JSX.Element {
  const [hoveredCell, setHoveredCell] = useState<{ row: number; col: number } | null>(null);

  const handleCellClick = useCallback((row: number, col: number, value: number) => {
    if (onCellClick) {
      onCellClick(row, col, value);
    }
  }, [onCellClick]);

  const handleCellMouseEnter = useCallback((row: number, col: number, value: number) => {
    setHoveredCell({ row, col });
    if (onCellHover) {
      onCellHover(row, col, value);
    }
  }, [onCellHover]);

  const handleCellMouseLeave = useCallback(() => {
    setHoveredCell(null);
  }, []);

  const isHighlighted = useCallback((row: number, col: number) => {
    return highlightCell?.row === row && highlightCell?.col === col;
  }, [highlightCell]);

  const isHovered = useCallback((row: number, col: number) => {
    return hoveredCell?.row === row && hoveredCell?.col === col;
  }, [hoveredCell]);

  const content = (
    <div className="overflow-x-auto">
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
                <Tooltip key={colIndex}>
                  <TooltipTrigger asChild>
                    <div
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
                      onMouseEnter={() => handleCellMouseEnter(rowIndex, colIndex, value)}
                      onMouseLeave={handleCellMouseLeave}
                      role="gridcell"
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
                      {showValues && value !== null && !isNaN(value) && (
                        <span className="text-[9px] font-mono leading-none">
                          {value.toFixed(1)}
                        </span>
                      )}
                    </div>
                  </TooltipTrigger>
                  <TooltipContent side="top" className="text-xs">
                    <div className="space-y-1">
                      <div><strong>RPM:</strong> {rowLabels[rowIndex]}</div>
                      <div><strong>Load:</strong> {colLabels[colIndex]}</div>
                      <div><strong>Correction:</strong> {value?.toFixed(2) ?? 'N/A'}%</div>
                      {isClamped && (
                        <div className="text-yellow-500 font-medium">
                          ⚠ Value clamped (exceeds ±{clampLimit}%)
                        </div>
                      )}
                    </div>
                  </TooltipContent>
                </Tooltip>
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
        className="absolute left-0 top-1/2 -translate-y-1/2 -translate-x-2"
        style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg) translateY(50%)' }}
      >
        <span className="text-xs text-muted-foreground">RPM</span>
      </div>
    </div>
  );

  if (title) {
    return (
      <Card className={cn('overflow-hidden', className)}>
        <CardHeader>
          <CardTitle>{title}</CardTitle>
        </CardHeader>
        <CardContent className="relative">
          {content}
        </CardContent>
      </Card>
    );
  }

  return (
    <div className={cn('relative', className)}>
      {content}
    </div>
  );
}
