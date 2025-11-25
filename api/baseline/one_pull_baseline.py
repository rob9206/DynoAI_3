"""
One-Pull Baseline™ — Predictive VE Table Generation

CRITICAL: This module does NOT modify any existing DynoAI math.
It is a NEW prediction system that generates estimated starting points.

All outputs are clearly marked as PREDICTED vs MEASURED.
"""

import numpy as np
from typing import List, Tuple, Optional
import logging

from .models import (
    CellType,
    BaselineResult,
    FDCAnalysis,
    InputValidationResult
)
from .validation import validate_input_data
from .confidence import calculate_fdc_analysis, calculate_cell_confidence

logger = logging.getLogger(__name__)

# Safety limits - MORE CONSERVATIVE than main engine
PREDICTION_CLAMP = 5.0           # Max ±5% for predicted cells (vs ±7% engine)
CONSERVATIVE_BIAS = 0.85         # Reduce prediction magnitudes by 15%


class OnePullBaseline:
    """
    Generate a complete VE baseline from a single partial-throttle pull.

    This is a PREDICTIVE system. Outputs should be validated with
    subsequent full-throttle verification pulls.

    Usage:
        baseline = OnePullBaseline()
        result = baseline.generate(rpm, map, afr_cmd, afr_meas)
    """

    # Standard HD VE grid dimensions
    DEFAULT_RPM_BINS = [
        1000, 1250, 1500, 1750, 2000, 2250, 2500, 2750,
        3000, 3250, 3500, 3750, 4000, 4250, 4500, 4750,
        5000, 5250, 5500, 5750, 6000, 6250, 6500
    ]
    DEFAULT_MAP_BINS = [20, 30, 40, 50, 60, 70, 80, 90, 100, 110]

    def __init__(
        self,
        rpm_bins: List[int] = None,
        map_bins: List[int] = None,
        prediction_clamp: float = PREDICTION_CLAMP,
        conservative_bias: float = CONSERVATIVE_BIAS
    ):
        self.rpm_bins = np.array(rpm_bins or self.DEFAULT_RPM_BINS)
        self.map_bins = np.array(map_bins or self.DEFAULT_MAP_BINS)
        self.prediction_clamp = prediction_clamp
        self.conservative_bias = conservative_bias

        self.n_rpm = len(self.rpm_bins)
        self.n_map = len(self.map_bins)

    def generate(
        self,
        rpm_data: np.ndarray,
        map_data: np.ndarray,
        afr_commanded: np.ndarray,
        afr_measured: np.ndarray,
        torque_data: Optional[np.ndarray] = None
    ) -> BaselineResult:
        """
        Generate baseline VE table from partial-throttle data.

        Args:
            rpm_data: RPM values from the pull
            map_data: MAP values (kPa) from the pull
            afr_commanded: Commanded AFR values
            afr_measured: Measured AFR values (wideband)
            torque_data: Optional torque for weighting

        Returns:
            BaselineResult with predictions, confidence, and diagnostics

        Raises:
            ValueError: If input data fails validation
        """
        warnings = []
        recommendations = []

        # === Step 1: Validate Input Data ===
        validation = validate_input_data(
            rpm_data, map_data,
            afr_commanded, afr_measured,
            self.map_bins, torque_data
        )

        if not validation.is_valid:
            error_msgs = [e.message for e in validation.errors]
            raise ValueError(f"Input validation failed: {'; '.join(error_msgs)}")

        # Add warnings from validation
        for issue in validation.warnings:
            warnings.append(issue.message)

        # === Step 2: Calculate AFR Errors ===
        # Using standard formula (same as main engine)
        afr_errors = (afr_commanded - afr_measured) / afr_measured * 100

        # === Step 3: Bin to VE Grid ===
        measured_grid, count_grid = self._bin_to_grid(
            rpm_data, map_data, afr_errors, torque_data
        )

        # === Step 4: Analyze FDC Stability ===
        fdc_analysis = calculate_fdc_analysis(
            measured_grid, count_grid, self.map_bins
        )

        if fdc_analysis.instability_warning:
            warnings.append(fdc_analysis.instability_warning)

        # === Step 5: Extrapolate Full Grid ===
        ve_grid, conf_grid, type_grid = self._extrapolate_grid(
            measured_grid, count_grid, fdc_analysis
        )

        # === Step 6: Apply Safety Adjustments ===
        ve_grid = self._apply_safety(ve_grid, type_grid)

        # === Step 7: Generate Statistics & Recommendations ===
        measured_count = int(np.sum(type_grid == CellType.MEASURED.value))
        interpolated_count = int(np.sum(type_grid == CellType.INTERPOLATED.value))
        extrapolated_count = int(np.sum(type_grid == CellType.EXTRAPOLATED.value))

        avg_confidence = float(np.mean(conf_grid))
        min_confidence = float(np.min(conf_grid))

        # Generate recommendations
        recommendations.append("Validate with full-throttle pull before applying")

        if min_confidence < 50:
            recommendations.append(
                "Some cells have <50% confidence. Focus verification on those areas."
            )

        if extrapolated_count > measured_count:
            recommendations.append(
                "More cells extrapolated than measured. Consider additional partial pull."
            )

        low_conf_count = np.sum(conf_grid < 60)
        if low_conf_count > 0:
            recommendations.append(
                f"{low_conf_count} cells have <60% confidence (highlighted in UI)"
            )

        return BaselineResult(
            ve_corrections=ve_grid.tolist(),
            confidence_map=conf_grid.tolist(),
            cell_types=type_grid.tolist(),
            rpm_axis=self.rpm_bins.tolist(),
            map_axis=self.map_bins.tolist(),
            measured_cells=measured_count,
            interpolated_cells=interpolated_count,
            extrapolated_cells=extrapolated_count,
            avg_confidence=round(avg_confidence, 1),
            min_confidence=round(min_confidence, 1),
            fdc=fdc_analysis,
            input_validation=validation,
            warnings=warnings,
            recommendations=recommendations
        )

    def _bin_to_grid(
        self,
        rpm_data: np.ndarray,
        map_data: np.ndarray,
        afr_errors: np.ndarray,
        torque_data: Optional[np.ndarray]
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Bin measured data into VE grid with torque weighting."""
        measured = np.full((self.n_rpm, self.n_map), np.nan)
        counts = np.zeros((self.n_rpm, self.n_map), dtype=int)
        sums = np.zeros((self.n_rpm, self.n_map))
        weights = np.zeros((self.n_rpm, self.n_map))

        for i in range(len(rpm_data)):
            rpm_idx = np.argmin(np.abs(self.rpm_bins - rpm_data[i]))
            map_idx = np.argmin(np.abs(self.map_bins - map_data[i]))

            # Torque weighting if available
            w = 1.0
            if torque_data is not None and i < len(torque_data) and torque_data[i] > 0:
                w = torque_data[i]

            sums[rpm_idx, map_idx] += afr_errors[i] * w
            weights[rpm_idx, map_idx] += w
            counts[rpm_idx, map_idx] += 1

        mask = weights > 0
        measured[mask] = sums[mask] / weights[mask]

        return measured, counts

    def _extrapolate_grid(
        self,
        measured: np.ndarray,
        counts: np.ndarray,
        fdc_analysis: FDCAnalysis
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Fill unmeasured cells via interpolation/extrapolation."""
        ve = measured.copy()
        conf = np.zeros((self.n_rpm, self.n_map))
        types = np.empty((self.n_rpm, self.n_map), dtype=object)

        for ri in range(self.n_rpm):
            for mi in range(self.n_map):
                if counts[ri, mi] > 0:
                    # Directly measured
                    cell_type = CellType.MEASURED
                    cell_conf = calculate_cell_confidence(
                        cell_type, ri, mi, counts, fdc_analysis
                    )
                    conf[ri, mi] = cell_conf.total
                    types[ri, mi] = cell_type.value
                else:
                    # Need to predict
                    val, cell_type, pred_values = self._predict_cell(
                        ri, mi, measured, counts, fdc_analysis
                    )
                    ve[ri, mi] = val

                    cell_conf = calculate_cell_confidence(
                        cell_type, ri, mi, counts, fdc_analysis, pred_values
                    )
                    conf[ri, mi] = cell_conf.total
                    types[ri, mi] = cell_type.value

        return ve, conf, types

    def _predict_cell(
        self,
        rpm_idx: int,
        map_idx: int,
        measured: np.ndarray,
        counts: np.ndarray,
        fdc_analysis: FDCAnalysis
    ) -> Tuple[float, CellType, List[float]]:
        """
        Predict a single unmeasured cell using multiple methods.

        Returns:
            (predicted_value, cell_type, list_of_prediction_values)
        """
        predictions = []  # (value, confidence_weight, method)

        # === Method 1: Neighbor Interpolation ===
        neighbors = []
        for dr in [-1, 0, 1]:
            for dm in [-1, 0, 1]:
                if dr == 0 and dm == 0:
                    continue
                nr, nm = rpm_idx + dr, map_idx + dm
                if 0 <= nr < self.n_rpm and 0 <= nm < self.n_map:
                    if counts[nr, nm] > 0:
                        dist = abs(dr) + abs(dm)
                        neighbors.append((measured[nr, nm], 1.0 / dist))

        if len(neighbors) >= 2:
            vals, weights = zip(*neighbors)
            interp_val = np.average(vals, weights=weights)
            predictions.append((interp_val, 3.0, 'interpolation'))

        # === Method 2: Row Interpolation (same RPM, different MAP) ===
        row = measured[rpm_idx, :]
        valid_in_row = ~np.isnan(row)
        if np.sum(valid_in_row) >= 2:
            valid_maps = self.map_bins[valid_in_row]
            valid_vals = row[valid_in_row]
            target_map = self.map_bins[map_idx]

            if valid_maps[0] <= target_map <= valid_maps[-1]:
                # Interpolate
                row_val = np.interp(target_map, valid_maps, valid_vals)
                predictions.append((row_val, 2.0, 'row_interp'))
            elif target_map > valid_maps[-1]:
                # Extrapolate using FDC
                base_val = valid_vals[-1]
                delta = target_map - valid_maps[-1]
                extrap_val = base_val + fdc_analysis.overall_fdc * delta
                predictions.append((extrap_val, 1.0, 'row_extrap'))

        # === Method 3: Column Interpolation (same MAP, different RPM) ===
        col = measured[:, map_idx]
        valid_in_col = ~np.isnan(col)
        if np.sum(valid_in_col) >= 2:
            valid_rpms = self.rpm_bins[valid_in_col]
            valid_vals = col[valid_in_col]
            target_rpm = self.rpm_bins[rpm_idx]

            if valid_rpms[0] <= target_rpm <= valid_rpms[-1]:
                col_val = np.interp(target_rpm, valid_rpms, valid_vals)
                predictions.append((col_val, 2.0, 'col_interp'))
            else:
                # Linear extrapolation along RPM
                if len(valid_rpms) >= 2:
                    coeffs = np.polyfit(valid_rpms, valid_vals, 1)
                    col_val = np.polyval(coeffs, target_rpm)
                    predictions.append((col_val, 1.0, 'col_extrap'))

        # === Method 4: FDC Projection (for high-MAP WOT cells) ===
        if map_idx > self.n_map // 2:
            # Look for nearest measured cell in same RPM row
            for search_mi in range(map_idx - 1, -1, -1):
                if counts[rpm_idx, search_mi] > 0:
                    base_val = measured[rpm_idx, search_mi]
                    delta_map = self.map_bins[map_idx] - self.map_bins[search_mi]
                    fdc_val = base_val + fdc_analysis.overall_fdc * delta_map
                    predictions.append((fdc_val, 1.5, 'fdc_projection'))
                    break

        # === Combine Predictions ===
        if predictions:
            # Weighted average of predictions
            vals, weights, _ = zip(*predictions)
            pred_values = list(vals)
            final_val = np.average(vals, weights=weights)

            # Determine cell type
            methods = [m for _, _, m in predictions]
            if any('interp' in m for m in methods):
                cell_type = CellType.INTERPOLATED
            else:
                cell_type = CellType.EXTRAPOLATED

            return final_val, cell_type, pred_values

        # === Fallback: Global Mean ===
        global_mean = np.nanmean(measured)
        return (
            global_mean if not np.isnan(global_mean) else 0.0,
            CellType.EXTRAPOLATED,
            []
        )

    def _apply_safety(
        self,
        ve: np.ndarray,
        types: np.ndarray
    ) -> np.ndarray:
        """Apply conservative bias and clamps to predictions."""
        result = ve.copy()

        for ri in range(self.n_rpm):
            for mi in range(self.n_map):
                if types[ri, mi] != CellType.MEASURED.value:
                    val = result[ri, mi]

                    # Apply conservative bias (reduce magnitudes)
                    val *= self.conservative_bias

                    # Apply tighter clamp for predictions
                    val = np.clip(val, -self.prediction_clamp, self.prediction_clamp)

                    result[ri, mi] = val

        return result
