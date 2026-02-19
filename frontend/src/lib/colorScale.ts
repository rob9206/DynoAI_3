/**
 * Color scale utility for VE heatmap visualization
 * Maps correction percentages to colors:
 * - Negative corrections (lean): Blue shades
 * - Zero/near-zero: White/neutral
 * - Positive corrections (rich): Red shades
 * - Clamped values: Special indicator (yellow border or icon)
 */

export interface ColorScaleOptions {
  minValue?: number;      // Default: -15 (analysis mode max)
  maxValue?: number;      // Default: +15
  clampLimit?: number;    // Default: 7 (production mode)
  neutralRange?: number;  // Values within this range shown as neutral (default: 0.5)
}

const DEFAULT_OPTIONS: Required<ColorScaleOptions> = {
  minValue: -15,
  maxValue: 15,
  clampLimit: 7,
  neutralRange: 0.5,
};

/**
 * Interpolate between two colors
 */
function interpolateColor(color1: [number, number, number], color2: [number, number, number], t: number): string {
  const r = Math.round(color1[0] + (color2[0] - color1[0]) * t);
  const g = Math.round(color1[1] + (color2[1] - color1[1]) * t);
  const b = Math.round(color1[2] + (color2[2] - color1[2]) * t);
  return `rgb(${r}, ${g}, ${b})`;
}

/**
 * Get color for a VE correction value
 * Color scheme:
 * - -15% to -7%: Dark blue to medium blue
 * - -7% to -1%: Light blue
 * - -1% to +1%: White/neutral gray
 * - +1% to +7%: Light red/pink
 * - +7% to +15%: Medium red to dark red
 */
export function getColorForValue(value: number, options?: ColorScaleOptions): string {
  const opts = { ...DEFAULT_OPTIONS, ...options };
  const { minValue, maxValue, neutralRange } = opts;
  
  // Handle null/NaN values
  if (value === null || Number.isNaN(value)) {
    return 'rgb(75, 85, 99)'; // Gray for missing data
  }
  
  // Clamp value to range
  const clampedValue = Math.max(minValue, Math.min(maxValue, value));
  
  // Neutral range - use green for OK/on-target values
  if (Math.abs(clampedValue) <= neutralRange) {
    return 'rgb(34, 197, 94)'; // Green-500 for OK values
  }
  
  // Define color stops
  const darkBlue: [number, number, number] = [30, 64, 175];    // Blue-800
  const mediumBlue: [number, number, number] = [59, 130, 246]; // Blue-500
  const lightBlue: [number, number, number] = [191, 219, 254]; // Blue-200
  const white: [number, number, number] = [255, 255, 255];
  const lightRed: [number, number, number] = [254, 202, 202];  // Red-200
  const mediumRed: [number, number, number] = [239, 68, 68];   // Red-500
  const darkRed: [number, number, number] = [153, 27, 27];     // Red-800
  
  if (clampedValue < 0) {
    // Negative values: blue shades
    if (clampedValue <= -7) {
      // -15 to -7: Dark blue to medium blue
      const t = (clampedValue - minValue) / (-7 - minValue);
      return interpolateColor(darkBlue, mediumBlue, t);
    } else {
      // -7 to -neutralRange: Medium blue to light blue to white
      const t = (clampedValue - (-7)) / (-neutralRange - (-7));
      if (t < 0.5) {
        return interpolateColor(mediumBlue, lightBlue, t * 2);
      } else {
        return interpolateColor(lightBlue, white, (t - 0.5) * 2);
      }
    }
  } else {
    // Positive values: red shades
    if (clampedValue >= 7) {
      // +7 to +15: Medium red to dark red
      const t = (clampedValue - 7) / (maxValue - 7);
      return interpolateColor(mediumRed, darkRed, t);
    } else {
      // +neutralRange to +7: White to light red to medium red
      const t = (clampedValue - neutralRange) / (7 - neutralRange);
      if (t < 0.5) {
        return interpolateColor(white, lightRed, t * 2);
      } else {
        return interpolateColor(lightRed, mediumRed, (t - 0.5) * 2);
      }
    }
  }
}

/**
 * Returns 'black' or 'white' for optimal text contrast against background
 */
export function getTextColorForBackground(bgColor: string): string {
  // Parse RGB from string
  const match = /rgb\((\d+),\s*(\d+),\s*(\d+)\)/.exec(bgColor);
  if (!match) {
    return 'black';
  }
  
  const r = parseInt(match[1], 10);
  const g = parseInt(match[2], 10);
  const b = parseInt(match[3], 10);
  
  // Calculate relative luminance
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  
  return luminance > 0.5 ? 'black' : 'white';
}

/**
 * Check if a value would be clamped in production mode
 */
export function isValueClamped(value: number, clampLimit: number): boolean {
  return Math.abs(value) > clampLimit;
}

/**
 * Generate an array of colors for a legend/gradient
 */
export function getColorScale(steps: number, options?: ColorScaleOptions): string[] {
  const opts = { ...DEFAULT_OPTIONS, ...options };
  const { minValue, maxValue } = opts;
  
  const colors: string[] = [];
  for (let i = 0; i < steps; i++) {
    const value = minValue + (maxValue - minValue) * (i / (steps - 1));
    colors.push(getColorForValue(value, options));
  }
  
  return colors;
}
