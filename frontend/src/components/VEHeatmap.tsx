import { useEffect, useRef, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';

interface VEHeatmapProps {
  data: number[][];
  rpm: number[];
  load: number[];
  title: string;
}

interface TooltipData {
  value: number;
  rpm: number;
  load: number;
  x: number;
  y: number;
}

export default function VEHeatmap({ data, rpm, load, title }: VEHeatmapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [tooltip, setTooltip] = useState<TooltipData | null>(null);

  useEffect(() => {
    if (!canvasRef.current || !data.length) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Set canvas size
    const width = canvas.width;
    const height = canvas.height;
    const cellWidth = width / load.length;
    const cellHeight = height / rpm.length;

    // Clear canvas
    ctx.clearRect(0, 0, width, height);

    // Find min/max for color scaling
    const flatData = data.flat().filter(v => v !== null && !isNaN(v));
    const min = Math.min(...flatData);
    const max = Math.max(...flatData);
    const range = max - min;

    // Draw heatmap
    data.forEach((row, rpmIdx) => {
      row.forEach((value, loadIdx) => {
        if (value === null || isNaN(value)) {
          // Gray for missing data
          ctx.fillStyle = '#374151';
        } else {
          // Color scale from blue (negative) through white (zero) to red (positive)
          const normalized = range > 0 ? (value - min) / range : 0.5;
          
          if (value < 0) {
            // Blue for negative corrections
            const intensity = Math.abs(value) / Math.abs(min);
            ctx.fillStyle = `rgb(${Math.floor(59 * (1 - intensity))}, ${Math.floor(130 * (1 - intensity))}, ${255})`;
          } else if (value > 0) {
            // Red for positive corrections
            const intensity = value / max;
            ctx.fillStyle = `rgb(${255}, ${Math.floor(99 * (1 - intensity))}, ${Math.floor(71 * (1 - intensity))})`;
          } else {
            // White for zero
            ctx.fillStyle = '#ffffff';
          }
        }

        const x = loadIdx * cellWidth;
        const y = rpmIdx * cellHeight;
        ctx.fillRect(x, y, cellWidth, cellHeight);

        // Draw cell border
        ctx.strokeStyle = '#1f2937';
        ctx.lineWidth = 1;
        ctx.strokeRect(x, y, cellWidth, cellHeight);

        // Draw value text
        if (value !== null && !isNaN(value)) {
          ctx.fillStyle = Math.abs(value) > (max - min) / 2 ? '#ffffff' : '#000000';
          ctx.font = '12px monospace';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(
            value.toFixed(1),
            x + cellWidth / 2,
            y + cellHeight / 2
          );
        }
      });
    });

  }, [data, rpm, load]);

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!canvasRef.current) return;

    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const cellWidth = canvas.width / load.length;
    const cellHeight = canvas.height / rpm.length;

    const loadIdx = Math.floor(x / cellWidth);
    const rpmIdx = Math.floor(y / cellHeight);

    if (
      loadIdx >= 0 && loadIdx < load.length &&
      rpmIdx >= 0 && rpmIdx < rpm.length &&
      data[rpmIdx] && data[rpmIdx][loadIdx] !== null && !isNaN(data[rpmIdx][loadIdx])
    ) {
      setTooltip({
        value: data[rpmIdx][loadIdx],
        rpm: rpm[rpmIdx],
        load: load[loadIdx],
        x: e.clientX,
        y: e.clientY,
      });
    } else {
      setTooltip(null);
    }
  };

  const handleMouseLeave = () => {
    setTooltip(null);
  };

  return (
    <Card className="overflow-visible">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <div ref={containerRef} className="relative min-w-[670px]" style={{ paddingLeft: '70px', paddingTop: '40px' }}>
            {/* Y-axis labels (RPM) */}
            <div className="absolute left-0 top-[40px] w-[60px] h-[400px] flex flex-col justify-between text-xs text-muted-foreground font-mono pr-2 border-r border-border">
              {rpm.map((val, i) => (
                <div key={i} className="flex-1 flex items-center justify-end">
                  {val}
                </div>
              ))}
            </div>

            {/* X-axis labels (Load) */}
            <div className="absolute left-[70px] top-[10px] w-[600px] h-[25px] flex justify-between text-xs text-muted-foreground font-mono border-b border-border">
              {load.map((val, i) => (
                <div key={i} className="flex-1 flex items-center justify-center">
                  {val}
                </div>
              ))}
            </div>

            <canvas
              ref={canvasRef}
              width={600}
              height={400}
              className="border border-border rounded bg-muted/10 shadow-inner cursor-crosshair"
              onMouseMove={handleMouseMove}
              onMouseLeave={handleMouseLeave}
            />
            
            {/* Axis Titles */}
            <div className="absolute top-0 left-[70px] w-[600px] text-center text-xs font-semibold text-muted-foreground">
              MAP (kPa)
            </div>
            <div className="absolute left-[-10px] top-[40px] h-[400px] flex items-center justify-center">
              <div className="-rotate-90 text-xs font-semibold text-muted-foreground whitespace-nowrap">
                RPM
              </div>
            </div>

            {/* Tooltip */}
            {tooltip && (
              <div
                className="fixed z-[9999] pointer-events-none"
                style={{
                  left: `${tooltip.x + 15}px`,
                  top: `${tooltip.y - 10}px`,
                }}
              >
                <div className="bg-popover border border-border rounded-lg shadow-xl px-3 py-2 text-sm animate-in fade-in zoom-in-95 duration-100">
                  <div className="font-semibold text-foreground mb-1">
                    Correction: {tooltip.value > 0 ? '+' : ''}{tooltip.value.toFixed(2)}%
                  </div>
                  <div className="text-xs text-muted-foreground space-y-0.5">
                    <div>RPM: {tooltip.rpm}</div>
                    <div>Load: {tooltip.load} kPa</div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
        
        {/* Legend */}
        <div className="mt-6 flex items-center justify-center space-x-6 text-sm text-muted-foreground">
          <div className="flex items-center space-x-2">
            <div className="w-3 h-3 bg-blue-500 rounded-sm"></div>
            <span>Lean (Negative)</span>
          </div>
          <div className="flex items-center space-x-2">
            <div className="w-3 h-3 bg-white border border-gray-300 rounded-sm"></div>
            <span>Target (Zero)</span>
          </div>
          <div className="flex items-center space-x-2">
            <div className="w-3 h-3 bg-red-500 rounded-sm"></div>
            <span>Rich (Positive)</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
