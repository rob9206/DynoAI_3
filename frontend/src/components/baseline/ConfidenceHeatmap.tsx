import { useMemo } from 'react';
import { cn } from '@/lib/utils';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

interface ConfidenceHeatmapProps {
  veCorrections: number[][];
  confidenceMap: number[][];
  cellTypes: string[][];
  rpmAxis: number[];
  mapAxis: number[];
  showConfidence?: boolean;
  onCellClick?: (rpmIdx: number, mapIdx: number) => void;
}

// Color scales
function getVEColor(value: number): string {
  const abs = Math.abs(value);
  if (abs < 1) return 'bg-green-100';
  if (abs < 2) return 'bg-green-200';
  if (abs < 3) return 'bg-yellow-200';
  if (abs < 4) return 'bg-orange-200';
  if (abs < 5) return 'bg-orange-300';
  return 'bg-red-300';
}

function getConfidenceColor(confidence: number): string {
  if (confidence >= 90) return 'bg-green-400';
  if (confidence >= 70) return 'bg-green-300';
  if (confidence >= 60) return 'bg-yellow-300';
  if (confidence >= 50) return 'bg-orange-300';
  return 'bg-red-300';
}

function getCellTypeIcon(cellType: string): string {
  switch (cellType) {
    case 'measured': return '●';
    case 'interpolated': return '◐';
    case 'extrapolated': return '○';
    default: return '?';
  }
}

export function ConfidenceHeatmap({
  veCorrections,
  confidenceMap,
  cellTypes,
  rpmAxis,
  mapAxis,
  showConfidence = false,
  onCellClick,
}: ConfidenceHeatmapProps) {

  const getCellStyle = (rpmIdx: number, mapIdx: number) => {
    const value = veCorrections[rpmIdx][mapIdx];
    const confidence = confidenceMap[rpmIdx][mapIdx];

    if (showConfidence) {
      return getConfidenceColor(confidence);
    }
    return getVEColor(value);
  };

  return (
    <TooltipProvider>
      <div className="overflow-auto">
        {/* Legend */}
        <div className="flex items-center gap-6 mb-4 text-xs">
          <div className="flex items-center gap-2">
            <span className="font-medium">Cell Type:</span>
            <span>● Measured</span>
            <span>◐ Interpolated</span>
            <span>○ Extrapolated</span>
          </div>
          {showConfidence && (
            <div className="flex items-center gap-1">
              <span className="font-medium">Confidence:</span>
              <span className="px-2 bg-green-400 rounded">90%+</span>
              <span className="px-2 bg-yellow-300 rounded">60-90%</span>
              <span className="px-2 bg-red-300 rounded">&lt;60%</span>
            </div>
          )}
        </div>

        {/* Grid */}
        <table className="border-collapse text-xs">
          <thead>
            <tr>
              <th className="p-1 text-right text-muted-foreground">RPM \ kPa</th>
              {mapAxis.map((map) => (
                <th key={map} className="p-1 text-center font-mono w-12">
                  {map}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rpmAxis.map((rpm, rpmIdx) => (
              <tr key={rpm}>
                <td className="p-1 text-right font-mono text-muted-foreground">
                  {rpm}
                </td>
                {mapAxis.map((_, mapIdx) => {
                  const value = veCorrections[rpmIdx][mapIdx];
                  const confidence = confidenceMap[rpmIdx][mapIdx];
                  const cellType = cellTypes[rpmIdx][mapIdx];

                  return (
                    <Tooltip key={mapIdx}>
                      <TooltipTrigger asChild>
                        <td
                          className={cn(
                            'p-1 text-center font-mono cursor-pointer',
                            'border border-gray-200 hover:ring-2 hover:ring-blue-400',
                            'transition-all',
                            getCellStyle(rpmIdx, mapIdx)
                          )}
                          onClick={() => onCellClick?.(rpmIdx, mapIdx)}
                        >
                          <div className="flex flex-col items-center">
                            <span className="text-[10px] text-gray-500">
                              {getCellTypeIcon(cellType)}
                            </span>
                            <span>
                              {value >= 0 ? '+' : ''}{value.toFixed(1)}
                            </span>
                          </div>
                        </td>
                      </TooltipTrigger>
                      <TooltipContent>
                        <div className="text-xs space-y-1">
                          <div><strong>{rpm} RPM @ {mapAxis[mapIdx]} kPa</strong></div>
                          <div>Correction: {value >= 0 ? '+' : ''}{value.toFixed(2)}%</div>
                          <div>Confidence: {confidence.toFixed(0)}%</div>
                          <div>Type: {cellType}</div>
                          {confidence < 60 && (
                            <div className="text-yellow-600 font-medium">
                              ⚠ Low confidence - verify this region
                            </div>
                          )}
                        </div>
                      </TooltipContent>
                    </Tooltip>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </TooltipProvider>
  );
}
