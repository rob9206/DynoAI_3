/**
 * VE Table Resampler
 * 
 * Resamples VE tables from one grid to another using bilinear interpolation.
 * Used when PVV import deduplication changes bin counts, requiring VE table
 * to be resampled to match the new grid dimensions.
 */

/**
 * Resample VE table from original grid to target grid using bilinear interpolation.
 * 
 * This function handles grid dimension mismatches that occur when:
 * - Duplicate bins are removed (e.g., 28 RPM bins → 27 unique)
 * - VE table shape doesn't match bin arrays
 * 
 * @param values - Original VE table values (2D array)
 * @param originalRpmBins - Original RPM bin values
 * @param originalMapBins - Original MAP bin values
 * @param targetRpmBins - Target RPM bin values after deduplication
 * @param targetMapBins - Target MAP bin values after deduplication
 * @returns Resampled VE table matching target grid dimensions
 */
export function resampleVETable(
  values: number[][],
  originalRpmBins: number[],
  originalMapBins: number[],
  targetRpmBins: number[],
  targetMapBins: number[]
): number[][] {
  // Validate inputs
  if (!values || values.length === 0 || values[0]?.length === 0) {
    throw new Error('VE table is empty');
  }
  
  if (originalRpmBins.length !== values.length) {
    throw new Error(
      `Original RPM bins (${originalRpmBins.length}) don't match VE table rows (${values.length})`
    );
  }
  
  if (originalMapBins.length !== values[0].length) {
    throw new Error(
      `Original MAP bins (${originalMapBins.length}) don't match VE table columns (${values[0].length})`
    );
  }
  
  // If grids match, return original (no resampling needed)
  if (
    originalRpmBins.length === targetRpmBins.length &&
    originalMapBins.length === targetMapBins.length &&
    arraysEqual(originalRpmBins, targetRpmBins) &&
    arraysEqual(originalMapBins, targetMapBins)
  ) {
    return values;
  }
  
  // Create output array
  const resampled: number[][] = [];
  
  // For each target grid point, interpolate from original grid
  for (let i = 0; i < targetRpmBins.length; i++) {
    const targetRpm = targetRpmBins[i];
    const row: number[] = [];
    
    for (let j = 0; j < targetMapBins.length; j++) {
      const targetMap = targetMapBins[j];
      
      // Bilinear interpolation
      const interpolatedValue = bilinearInterpolate(
        values,
        originalRpmBins,
        originalMapBins,
        targetRpm,
        targetMap
      );
      
      row.push(interpolatedValue);
    }
    
    resampled.push(row);
  }
  
  return resampled;
}

/**
 * Bilinear interpolation for a single point.
 * 
 * @param grid - 2D grid of values
 * @param rpmBins - RPM axis values
 * @param mapBins - MAP axis values
 * @param targetRpm - Target RPM to interpolate at
 * @param targetMap - Target MAP to interpolate at
 * @returns Interpolated value
 */
function bilinearInterpolate(
  grid: number[][],
  rpmBins: number[],
  mapBins: number[],
  targetRpm: number,
  targetMap: number
): number {
  // Find surrounding indices for RPM
  const rpmIdx = findSurroundingIndices(rpmBins, targetRpm);
  const mapIdx = findSurroundingIndices(mapBins, targetMap);
  
  // Handle edge cases (exact match or extrapolation)
  if (rpmIdx.i0 === rpmIdx.i1 && mapIdx.i0 === mapIdx.i1) {
    // Exact match on both axes
    return grid[rpmIdx.i0][mapIdx.i0];
  }
  
  if (rpmIdx.i0 === rpmIdx.i1) {
    // Exact match on RPM, interpolate MAP only
    return linearInterpolate(
      grid[rpmIdx.i0][mapIdx.i0],
      grid[rpmIdx.i0][mapIdx.i1],
      mapIdx.t
    );
  }
  
  if (mapIdx.i0 === mapIdx.i1) {
    // Exact match on MAP, interpolate RPM only
    return linearInterpolate(
      grid[rpmIdx.i0][mapIdx.i0],
      grid[rpmIdx.i1][mapIdx.i0],
      rpmIdx.t
    );
  }
  
  // Full bilinear interpolation
  // Get four surrounding values
  const v00 = grid[rpmIdx.i0][mapIdx.i0];  // Lower-left
  const v10 = grid[rpmIdx.i1][mapIdx.i0];  // Lower-right
  const v01 = grid[rpmIdx.i0][mapIdx.i1];  // Upper-left
  const v11 = grid[rpmIdx.i1][mapIdx.i1];  // Upper-right
  
  // Interpolate along RPM axis first
  const v0 = linearInterpolate(v00, v10, rpmIdx.t);
  const v1 = linearInterpolate(v01, v11, rpmIdx.t);
  
  // Then interpolate along MAP axis
  return linearInterpolate(v0, v1, mapIdx.t);
}

/**
 * Find surrounding indices and interpolation factor for a target value.
 * 
 * @param bins - Sorted array of bin values
 * @param target - Target value to find
 * @returns Indices and interpolation factor
 */
function findSurroundingIndices(
  bins: number[],
  target: number
): { i0: number; i1: number; t: number } {
  // Handle edge cases
  if (target <= bins[0]) {
    return { i0: 0, i1: 0, t: 0 };
  }
  
  if (target >= bins[bins.length - 1]) {
    const last = bins.length - 1;
    return { i0: last, i1: last, t: 0 };
  }
  
  // Binary search for surrounding indices
  let i0 = 0;
  let i1 = bins.length - 1;
  
  while (i1 - i0 > 1) {
    const mid = Math.floor((i0 + i1) / 2);
    if (bins[mid] <= target) {
      i0 = mid;
    } else {
      i1 = mid;
    }
  }
  
  // Calculate interpolation factor (0 to 1)
  const t = (target - bins[i0]) / (bins[i1] - bins[i0]);
  
  return { i0, i1, t };
}

/**
 * Linear interpolation between two values.
 * 
 * @param v0 - Value at t=0
 * @param v1 - Value at t=1
 * @param t - Interpolation factor (0 to 1)
 * @returns Interpolated value
 */
function linearInterpolate(v0: number, v1: number, t: number): number {
  return v0 + (v1 - v0) * t;
}

/**
 * Check if two arrays are equal.
 */
function arraysEqual(a: number[], b: number[]): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    if (Math.abs(a[i] - b[i]) > 0.001) return false;
  }
  return true;
}
