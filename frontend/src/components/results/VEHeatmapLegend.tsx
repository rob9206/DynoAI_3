import { getColorScale } from '@/lib/colorScale';

interface VEHeatmapLegendProps {
  clampLimit?: number;
  showClampIndicator?: boolean;
  orientation?: 'horizontal' | 'vertical';
}

export function VEHeatmapLegend({ 
  clampLimit = 7, 
  showClampIndicator = true, 
  orientation = 'horizontal' 
}: VEHeatmapLegendProps): JSX.Element {
  const colors = getColorScale(100, { minValue: -15, maxValue: 15, clampLimit });
  const gradientStyle = orientation === 'horizontal'
    ? `linear-gradient(to right, ${colors.join(', ')})`
    : `linear-gradient(to top, ${colors.join(', ')})`;
  
  const labels = ['-15%', '-7%', '0%', '+7%', '+15%'];
  const clampIndicatorPosition = clampLimit / 15 * 100; // Position as percentage

  if (orientation === 'vertical') {
    return (
      <div className="flex items-center gap-3">
        <div className="flex flex-col items-end text-xs text-muted-foreground font-mono h-40 justify-between">
          {labels.slice().reverse().map((label, index) => (
            <span key={index}>{label}</span>
          ))}
        </div>
        <div className="relative w-4 h-40 rounded border border-border overflow-hidden">
          <div 
            className="absolute inset-0" 
            style={{ background: gradientStyle }}
          />
          {showClampIndicator && (
            <>
              {/* Upper clamp line */}
              <div 
                className="absolute left-0 right-0 h-px bg-yellow-500" 
                style={{ bottom: `${50 + clampIndicatorPosition / 2}%` }}
              />
              {/* Lower clamp line */}
              <div 
                className="absolute left-0 right-0 h-px bg-yellow-500" 
                style={{ bottom: `${50 - clampIndicatorPosition / 2}%` }}
              />
            </>
          )}
        </div>
        {showClampIndicator && (
          <div className="flex flex-col gap-2 text-xs text-muted-foreground">
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 border-2 border-dashed border-yellow-500 rounded-sm" />
              <span>Clamped (±{clampLimit}%)</span>
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="flex items-center gap-4">
        <span className="text-xs text-muted-foreground">Lean (−)</span>
        <div className="relative w-64 h-4 rounded border border-border overflow-hidden">
          <div 
            className="absolute inset-0" 
            style={{ background: gradientStyle }}
          />
          {showClampIndicator && (
            <>
              {/* Left clamp line */}
              <div 
                className="absolute top-0 bottom-0 w-px bg-yellow-500" 
                style={{ left: `${50 - clampIndicatorPosition / 2}%` }}
              />
              {/* Right clamp line */}
              <div 
                className="absolute top-0 bottom-0 w-px bg-yellow-500" 
                style={{ left: `${50 + clampIndicatorPosition / 2}%` }}
              />
            </>
          )}
        </div>
        <span className="text-xs text-muted-foreground">Rich (+)</span>
      </div>
      <div className="flex justify-between w-64 text-xs text-muted-foreground font-mono">
        {labels.map((label, index) => (
          <span key={index}>{label}</span>
        ))}
      </div>
      {showClampIndicator && (
        <div className="flex items-center gap-4 mt-1">
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 border-2 border-dashed border-yellow-500 rounded-sm" />
            <span className="text-xs text-muted-foreground">Clamped (±{clampLimit}%)</span>
          </div>
        </div>
      )}
    </div>
  );
}
