import React, { useMemo } from 'react';
import { cn } from '@/lib/utils';

interface CellTargetHeatmapProps {
  /** Hit count matrix from coverage (empty cells = targets) */
  hitCount: number[][];
  /** RPM axis labels */
  rowLabels: string[];
  /** MAP axis labels */
  colLabels: string[];
  /** Minimum hits threshold (default: 5) */
  minHits?: number;
  /** Show only high-priority regions (default: false) */
  highlightOnly?: boolean;
  /** Title for the heatmap */
  title?: string;
  /** Optional className */
  className?: string;
  /** Optional callback when a cell is clicked */
  onCellClick?: (row: number, col: number, priority: number) => void;
}

interface CellPriority {
  priority: number; // 0 = covered, 1 = high, 2 = medium, 3 = low
  label: string;
  color: string;
}

/**
 * CellTargetHeatmap
 * 
 * Visual overlay showing which cells to target next based on coverage gaps.
 * - Red = high priority (high-impact regions with low coverage)
 * - Yellow = medium priority
 * - Blue = already covered
 */
export function CellTargetHeatmap({
  hitCount,
  rowLabels,
  colLabels,
  minHits = 5,
  highlightOnly = false,
  title = "Target Cells",
  className,
  onCellClick,
}: CellTargetHeatmapProps): React.JSX.Element {
  
  // Define high-impact regions
  const highImpactRegions = useMemo(() => {
    return [
      {
        name: "high_map_midrange",
        rpmRange: [2500, 4500],
        mapRange: [80, 100],
        priority: 1,
      },
      {
        name: "tip_in_zone",
        rpmRange: [2000, 4500],
        mapRange: [50, 85],
        priority: 1,
      },
      {
        name: "idle_low_map",
        rpmRange: [500, 1500],
        mapRange: [20, 40],
        priority: 2,
      },
    ];
  }, []);
  
  // Compute cell priority matrix
  const priorityMatrix = useMemo(() => {
    const rows = hitCount.length;
    const cols = hitCount[0]?.length || 0;
    
    const matrix: CellPriority[][] = [];
    
    for (let i = 0; i < rows; i++) {
      matrix[i] = [];
      for (let j = 0; j < cols; j++) {
        const hits = hitCount[i][j] || 0;
        
        // Estimate RPM/MAP from indices (rough mapping)
        const rpm = 500 + (i * 7500 / rows);
        const map = 20 + (j * 80 / cols);
        
        // Check if in high-impact region
        let inHighImpact = false;
        let regionPriority = 3;
        
        for (const region of highImpactRegions) {
          if (
            rpm >= region.rpmRange[0] &&
            rpm <= region.rpmRange[1] &&
            map >= region.mapRange[0] &&
            map <= region.mapRange[1]
          ) {
            inHighImpact = true;
            regionPriority = Math.min(regionPriority, region.priority);
          }
        }
        
        // Determine cell priority
        let cellPriority: CellPriority;
        
        if (hits >= minHits) {
          // Already covered
          cellPriority = {
            priority: 0,
            label: "Covered",
            color: "bg-blue-100 border-blue-300",
          };
        } else if (inHighImpact) {
          // High priority gap
          cellPriority = {
            priority: regionPriority,
            label: regionPriority === 1 ? "High Priority" : "Medium Priority",
            color: regionPriority === 1 
              ? "bg-red-400 border-red-600" 
              : "bg-yellow-300 border-yellow-500",
          };
        } else {
          // Low priority gap
          cellPriority = {
            priority: 3,
            label: "Low Priority",
            color: "bg-gray-200 border-gray-400",
          };
        }
        
        matrix[i][j] = cellPriority;
      }
    }
    
    return matrix;
  }, [hitCount, minHits, highImpactRegions]);
  
  // Filter cells if highlightOnly
  const visibleMatrix = useMemo(() => {
    if (!highlightOnly) return priorityMatrix;
    
    // Only show high/medium priority targets
    return priorityMatrix.map(row =>
      row.map(cell => 
        cell.priority <= 2 ? cell : { ...cell, color: "bg-transparent border-transparent" }
      )
    );
  }, [priorityMatrix, highlightOnly]);
  
  return (
    <div className={cn("flex flex-col gap-2", className)}>
      {title && (
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-semibold text-gray-700">{title}</h4>
          <div className="flex items-center gap-2 text-xs">
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 bg-red-400 border border-red-600 rounded" />
              <span>High Priority</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 bg-yellow-300 border border-yellow-500 rounded" />
              <span>Medium</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 bg-blue-100 border border-blue-300 rounded" />
              <span>Covered</span>
            </div>
          </div>
        </div>
      )}
      
      <div className="overflow-auto border border-gray-300 rounded bg-white">
        <table className="border-collapse">
          <thead>
            <tr>
              <th className="border border-gray-300 bg-gray-100 px-2 py-1 text-xs font-semibold">
                MAP (kPa)
              </th>
              {colLabels.map((label, idx) => (
                <th
                  key={idx}
                  className="border border-gray-300 bg-gray-100 px-2 py-1 text-xs font-semibold"
                >
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibleMatrix.map((row, rowIdx) => (
              <tr key={rowIdx}>
                <td className="border border-gray-300 bg-gray-100 px-2 py-1 text-xs font-semibold">
                  {rowLabels[rowIdx]}
                </td>
                {row.map((cell, colIdx) => (
                  <td
                    key={colIdx}
                    className={cn(
                      "border cursor-pointer transition-opacity hover:opacity-75",
                      cell.color
                    )}
                    style={{ width: '32px', height: '32px' }}
                    onClick={() => onCellClick?.(rowIdx, colIdx, cell.priority)}
                    title={`${rowLabels[rowIdx]} RPM, ${colLabels[colIdx]} kPa - ${cell.label} (${hitCount[rowIdx][colIdx]} hits)`}
                  >
                    {/* Empty cell - color shows priority */}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      
      <p className="text-xs text-gray-600">
        Click cells to filter test suggestions for that region
      </p>
    </div>
  );
}
