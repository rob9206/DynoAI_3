import { memo } from 'react';

interface SparklineProps {
  /** Array of numeric values to render */
  data: number[];
  /** SVG stroke color (CSS color string) */
  color?: string;
  /** Width in px */
  width?: number;
  /** Height in px */
  height?: number;
  className?: string;
}

/**
 * Lightweight inline SVG sparkline for telemetry trends.
 * Renders a single polyline scaled to the data range.
 */
export const Sparkline = memo(function Sparkline({
  data,
  color = 'rgb(249, 115, 22)',
  width = 60,
  height = 20,
  className,
}: SparklineProps) {
  if (data.length < 2) return null;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const points = data
    .map((value, i) => {
      const x = (i / (data.length - 1)) * width;
      const y = height - ((value - min) / range) * (height - 2) - 1; // 1px padding top/bottom
      return `${x},${y}`;
    })
    .join(' ');

  return (
    <svg
      width={width}
      height={height}
      className={className}
      aria-hidden="true"
    >
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
});
