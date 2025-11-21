import { useEffect, useRef } from 'react';

interface VEHeatmapProps {
  data: number[][];
  rpm: number[];
  load: number[];
  title: string;
}

export default function VEHeatmap({ data, rpm, load, title }: VEHeatmapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

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

  return (
    <div className="bg-gray-900/50 rounded-lg p-6 border border-gray-700">
      <h3 className="text-lg font-semibold text-white mb-4">{title}</h3>
      <div className="overflow-x-auto">
        <div className="relative" style={{ paddingLeft: '70px', paddingTop: '40px' }}>
          {/* Y-axis labels (RPM) */}
          <div className="absolute left-5 top-[40px] w-[40px] h-[400px] flex flex-col justify-between text-xs text-gray-400 font-mono">
            {rpm.map((val, i) => (
              <div key={i} className="flex-1 flex items-center justify-end pr-2">
                {val}
              </div>
            ))}
          </div>

          {/* X-axis labels (Load) */}
          <div className="absolute left-[70px] top-[15px] w-[600px] h-[20px] flex justify-between text-xs text-gray-400 font-mono">
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
            className="border border-gray-700 rounded"
          />
          
          {/* Axis Titles */}
          <div className="absolute top-0 left-[70px] w-[600px] text-center text-xs font-semibold text-gray-300">
            MAP (kPa)
          </div>
          <div className="absolute left-0 top-[40px] h-[400px] flex items-center justify-center -ml-4">
            <div className="-rotate-90 text-xs font-semibold text-gray-300 whitespace-nowrap">
              RPM
            </div>
          </div>
        </div>
      </div>
      
      {/* Legend */}
      <div className="mt-4 flex items-center justify-center space-x-4 text-xs text-gray-400">
        <div className="flex items-center space-x-2">
          <div className="w-4 h-4 bg-blue-500 rounded"></div>
          <span>Lean (Negative)</span>
        </div>
        <div className="flex items-center space-x-2">
          <div className="w-4 h-4 bg-white rounded"></div>
          <span>Target (Zero)</span>
        </div>
        <div className="flex items-center space-x-2">
          <div className="w-4 h-4 bg-red-500 rounded"></div>
          <span>Rich (Positive)</span>
        </div>
      </div>
    </div>
  );
}
