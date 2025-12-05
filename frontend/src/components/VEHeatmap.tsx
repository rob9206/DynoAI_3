import { useEffect, useRef, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';

interface VEHeatmapProps {
  data: number[][];
  rpm: number[];
  load: number[];
  title: string;
  colorMode?: 'diverging' | 'sequential'; // diverging for corrections, sequential for coverage
}

interface TooltipData {
  value: number;
  rpm: number;
  load: number;
  x: number;
  y: number;
}

export default function VEHeatmap({ data, rpm, load, title, colorMode = 'diverging' }: VEHeatmapProps) {
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

    // Draw heatmap
    data.forEach((row, rpmIdx) => {
      row.forEach((value, loadIdx) => {
        if (value === null || isNaN(value)) {
          // Gray for missing data
          ctx.fillStyle = '#374151';
        } else if (colorMode === 'sequential') {
          // Sequential color scale for coverage data (0 to max)
          // Gradient: white -> cyan -> green -> yellow -> orange -> red
          const normalized = max > 0 ? value / max : 0;

          if (value === 0) {
            // White/light gray for no data
            ctx.fillStyle = '#f3f4f6';
          } else if (normalized < 0.2) {
            // Light blue to cyan
            const t = normalized / 0.2;
            ctx.fillStyle = `rgb(${Math.floor(200 + (100 - 200) * t)}, ${Math.floor(220 + (220 - 220) * t)}, ${Math.floor(255)})`;
          } else if (normalized < 0.4) {
            // Cyan to green
            const t = (normalized - 0.2) / 0.2;
            ctx.fillStyle = `rgb(${Math.floor(100 - 100 * t)}, ${Math.floor(220 - 20 * t)}, ${Math.floor(255 - 55 * t)})`;
          } else if (normalized < 0.6) {
            // Green to yellow-green
            const t = (normalized - 0.4) / 0.2;
            ctx.fillStyle = `rgb(${Math.floor(100 * t)}, ${Math.floor(200 + 55 * t)}, ${Math.floor(200 - 200 * t)})`;
          } else if (normalized < 0.8) {
            // Yellow to orange
            const t = (normalized - 0.6) / 0.2;
            ctx.fillStyle = `rgb(${Math.floor(100 + 155 * t)}, ${Math.floor(255 - 100 * t)}, ${0})`;
          } else {
            // Orange to red
            const t = (normalized - 0.8) / 0.2;
            ctx.fillStyle = `rgb(${255}, ${Math.floor(155 - 155 * t)}, ${0})`;
          }
        } else {
          // Diverging color scale for VE corrections (negative to positive)
          // Blue (negative) through white (zero) to red (positive)
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
          // Choose text color based on background brightness
          if (colorMode === 'sequential') {
            const normalized = max > 0 ? value / max : 0;
            // Use white text for darker backgrounds (high values), black for lighter
            ctx.fillStyle = normalized > 0.5 ? '#ffffff' : '#000000';
          } else {
            // For diverging scale, use white text for extreme values
            const absValue = Math.abs(value);
            const maxAbs = Math.max(Math.abs(min), Math.abs(max));
            ctx.fillStyle = absValue > maxAbs / 2 ? '#ffffff' : '#000000';
          }
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

  }, [data, rpm, load, colorMode]);

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
      data[rpmIdx]?.[loadIdx] != null && !isNaN(data[rpmIdx][loadIdx])
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
        <div className="mt-6 flex items-center justify-center space-x-6 text-sm text-muted-foreground flex-wrap gap-2">
          {colorMode === 'sequential' ? (
            <>
              <div className="flex items-center space-x-2">
                <div className="w-3 h-3 bg-gray-100 border border-gray-300 rounded-sm"></div>
                <span>No Data</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-3 h-3 bg-cyan-400 rounded-sm"></div>
                <span>Low</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-3 h-3 bg-green-500 rounded-sm"></div>
                <span>Medium</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-3 h-3 bg-yellow-500 rounded-sm"></div>
                <span>High</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-3 h-3 bg-red-500 rounded-sm"></div>
                <span>Very High</span>
              </div>
            </>
          ) : (
            <>
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
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
