"""
DynoAI NextGen Surface Builder

Builds reusable RPM/MAP 2D surfaces from labeled data using the existing
WeightedBinAccumulator utilities.

Provides a unified format for all grid-based analysis including:
- Spark timing surfaces
- AFR error surfaces
- Knock activity surfaces
- Hit count / coverage surfaces

Usage:
    from dynoai.core.surface_builder import build_surface, SurfaceSpec, Surface2D
    from dynoai.core.mode_detection import ModeTag

    spec = SurfaceSpec(
        value_column="spark_f",
        filter_modes=[ModeTag.WOT],
        aggregation="mean",
        min_samples_per_cell=3,
    )

    surface = build_surface(labeled_df, spec)
    print(f"Surface: {surface.title}")
    print(f"Coverage: {surface.stats.non_nan_cells} / {surface.stats.total_cells}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Union

import numpy as np
import pandas as pd

from dynoai.constants import KPA_BINS, RPM_BINS
from dynoai.core.mode_detection import ModeTag
from dynoai.core.weighted_binning import (
    LogarithmicWeighting,
    UniformWeighting,
    WeightedBinAccumulator,
    WeightingStrategy,
)

__all__ = [
    "SurfaceAxis",
    "SurfaceStats",
    "Surface2D",
    "SurfaceSpec",
    "build_surface",
    "build_standard_surfaces",
    "surface_to_dict",
]

# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class SurfaceAxis:
    """Definition of a surface axis."""

    name: str
    unit: str
    bins: List[float]

    def __len__(self) -> int:
        return len(self.bins)

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "unit": self.unit,
            "bins": self.bins,
        }


@dataclass
class SurfaceStats:
    """Statistics for a surface."""

    min: Optional[float] = None
    max: Optional[float] = None
    mean: Optional[float] = None
    p05: Optional[float] = None
    p95: Optional[float] = None
    non_nan_cells: int = 0
    total_cells: int = 0
    total_samples: int = 0

    @property
    def coverage_pct(self) -> float:
        """Percentage of cells with valid data."""
        if self.total_cells == 0:
            return 0.0
        return self.non_nan_cells / self.total_cells * 100

    def to_dict(self) -> Dict:
        return {
            "min": self.min,
            "max": self.max,
            "mean": self.mean,
            "p05": self.p05,
            "p95": self.p95,
            "non_nan_cells": self.non_nan_cells,
            "total_cells": self.total_cells,
            "total_samples": self.total_samples,
            "coverage_pct": round(self.coverage_pct, 1),
        }


@dataclass
class Surface2D:
    """
    A 2D RPM/MAP surface with values and metadata.

    This is the unified format for all NextGen grid-based analysis.
    """

    surface_id: str
    title: str
    description: str
    rpm_axis: SurfaceAxis
    map_axis: SurfaceAxis
    values: List[List[Optional[float]]]  # [rpm_idx][map_idx]
    hit_count: List[List[int]]
    stats: SurfaceStats
    mask_info: Optional[str] = None  # Description of which modes were included

    @property
    def shape(self) -> tuple:
        """Grid shape (rpm_bins, map_bins)."""
        return (len(self.rpm_axis), len(self.map_axis))

    def get_value(self, rpm_idx: int, map_idx: int) -> Optional[float]:
        """Get value at specific cell."""
        if 0 <= rpm_idx < len(self.values) and 0 <= map_idx < len(
                self.values[0]):
            return self.values[rpm_idx][map_idx]
        return None

    def get_hits(self, rpm_idx: int, map_idx: int) -> int:
        """Get hit count at specific cell."""
        if 0 <= rpm_idx < len(self.hit_count) and 0 <= map_idx < len(
                self.hit_count[0]):
            return self.hit_count[rpm_idx][map_idx]
        return 0

    def get_high_map_slice(self, num_bins: int = 2) -> List[Optional[float]]:
        """
        Get values averaged across the top N MAP bins (for spark valley analysis).

        Returns a list of values indexed by RPM bin.
        """
        result = []
        for rpm_idx in range(len(self.rpm_axis)):
            high_map_values = []
            start_map_idx = max(0, len(self.map_axis) - num_bins)
            for map_idx in range(start_map_idx, len(self.map_axis)):
                val = self.values[rpm_idx][map_idx]
                if val is not None:
                    high_map_values.append(val)

            if high_map_values:
                result.append(sum(high_map_values) / len(high_map_values))
            else:
                result.append(None)

        return result

    def to_dict(self) -> Dict:
        """Serialize to JSON-compatible dict."""
        return {
            "surface_id": self.surface_id,
            "title": self.title,
            "description": self.description,
            "rpm_axis": self.rpm_axis.to_dict(),
            "map_axis": self.map_axis.to_dict(),
            "values": self.values,
            "hit_count": self.hit_count,
            "stats": self.stats.to_dict(),
            "mask_info": self.mask_info,
        }


@dataclass
class SurfaceSpec:
    """
    Specification for building a surface.

    Attributes:
        value_column: Column name to aggregate, or callable that computes value
        filter_modes: List of modes to include (None = all modes)
        filter_expr: Additional filter callable (takes row, returns bool)
        aggregation: Aggregation method: "mean", "max", "min", "p95", "rate", "sum"
        weighting: Weighting strategy for binning
        min_samples_per_cell: Minimum samples for a cell to be valid
        surface_id: Unique identifier for the surface
        title: Human-readable title
        description: Longer description
    """

    value_column: Union[str, Callable[[pd.Series], float]]
    filter_modes: Optional[List[ModeTag]] = None
    filter_expr: Optional[Callable[[pd.Series], bool]] = None
    aggregation: str = "mean"
    weighting: Optional[WeightingStrategy] = None
    min_samples_per_cell: int = 3
    surface_id: str = ""
    title: str = ""
    description: str = ""


# =============================================================================
# Core Functions
# =============================================================================


def build_surface(
    df: pd.DataFrame,
    spec: SurfaceSpec,
    rpm_bins: Optional[List[float]] = None,
    map_bins: Optional[List[float]] = None,
) -> Surface2D:
    """
    Build a 2D surface from a labeled DataFrame.

    Uses WeightedBinAccumulator for cell aggregation with configurable
    weighting strategy.

    Args:
        df: Labeled DataFrame (must have 'rpm', 'map_kpa', and 'mode' columns)
        spec: Surface specification
        rpm_bins: RPM axis bins (defaults to RPM_BINS from constants)
        map_bins: MAP axis bins (defaults to KPA_BINS from constants)

    Returns:
        Surface2D with computed values and statistics
    """
    # Use default bins if not provided
    if rpm_bins is None:
        rpm_bins = list(RPM_BINS)
    if map_bins is None:
        map_bins = list(KPA_BINS)

    # Apply mode filter
    filtered_df = df.copy()
    mask_info_parts = []

    if spec.filter_modes is not None and "mode" in df.columns:
        mode_values = [m.value for m in spec.filter_modes]
        filtered_df = filtered_df[filtered_df["mode"].isin(mode_values)]
        mask_info_parts.append(f"modes: {', '.join(mode_values)}")

    # Apply additional filter expression
    if spec.filter_expr is not None:
        filter_mask = filtered_df.apply(spec.filter_expr, axis=1)
        filtered_df = filtered_df[filter_mask]
        mask_info_parts.append("custom filter applied")

    # Get value column
    if callable(spec.value_column):
        values_series = filtered_df.apply(spec.value_column, axis=1)
    else:
        if spec.value_column not in filtered_df.columns:
            raise ValueError(
                f"Column '{spec.value_column}' not found in DataFrame")
        values_series = filtered_df[spec.value_column]

    # Check for required columns
    if "rpm" not in filtered_df.columns:
        raise ValueError("Column 'rpm' not found in DataFrame")
    if "map_kpa" not in filtered_df.columns:
        raise ValueError("Column 'map_kpa' not found in DataFrame")

    # Build accumulator
    weighting = spec.weighting or LogarithmicWeighting()
    accumulator = WeightedBinAccumulator(
        x_axis=rpm_bins,
        y_axis=map_bins,
        weighting=weighting,
        min_hits=spec.min_samples_per_cell,
    )

    # Add samples
    total_samples = 0
    for idx in filtered_df.index:
        rpm = filtered_df.loc[idx, "rpm"]
        map_kpa = filtered_df.loc[idx, "map_kpa"]
        value = values_series.loc[idx]

        if pd.notna(rpm) and pd.notna(map_kpa) and pd.notna(value):
            if accumulator.add_sample(rpm, map_kpa, value):
                total_samples += 1

    # Get results
    raw_table = accumulator.get_table()
    hit_counts = accumulator.get_hit_counts()

    # Apply aggregation if not "mean" (accumulator gives weighted mean by default)
    if spec.aggregation in ["max", "min", "p95", "sum", "rate"]:
        # For non-mean aggregations, we need to recompute
        values_matrix = _compute_aggregated_surface(
            filtered_df,
            values_series,
            rpm_bins,
            map_bins,
            spec.aggregation,
            spec.min_samples_per_cell,
        )
    else:
        values_matrix = raw_table

    # Compute statistics
    flat_values = [v for row in values_matrix for v in row if v is not None]
    stats = SurfaceStats(
        min=min(flat_values) if flat_values else None,
        max=max(flat_values) if flat_values else None,
        mean=sum(flat_values) / len(flat_values) if flat_values else None,
        p05=np.percentile(flat_values, 5) if flat_values else None,
        p95=np.percentile(flat_values, 95) if flat_values else None,
        non_nan_cells=len(flat_values),
        total_cells=len(rpm_bins) * len(map_bins),
        total_samples=total_samples,
    )

    # Build axis objects
    rpm_axis = SurfaceAxis(name="RPM", unit="rpm", bins=rpm_bins)
    map_axis = SurfaceAxis(name="MAP", unit="kPa", bins=map_bins)

    # Build mask info string
    mask_info = "; ".join(mask_info_parts) if mask_info_parts else None

    return Surface2D(
        surface_id=spec.surface_id or f"surface_{spec.value_column}",
        title=spec.title or f"{spec.value_column} Surface",
        description=spec.description or f"2D surface of {spec.value_column}",
        rpm_axis=rpm_axis,
        map_axis=map_axis,
        values=values_matrix,
        hit_count=hit_counts,
        stats=stats,
        mask_info=mask_info,
    )


def _compute_aggregated_surface(
    df: pd.DataFrame,
    values_series: pd.Series,
    rpm_bins: List[float],
    map_bins: List[float],
    aggregation: str,
    min_samples: int,
) -> List[List[Optional[float]]]:
    """
    Compute surface with custom aggregation.

    Used for aggregations other than weighted mean (max, min, p95, etc.).
    """
    n_rpm = len(rpm_bins)
    n_map = len(map_bins)

    # Initialize cell accumulators
    cell_values: List[List[List[float]]] = [[[] for _ in range(n_map)]
                                            for _ in range(n_rpm)]

    def nearest_bin(val: float, bins: List[float]) -> int:
        return min(range(len(bins)), key=lambda i: abs(bins[i] - val))

    # Accumulate values into cells
    for idx in df.index:
        rpm = df.loc[idx, "rpm"]
        map_kpa = df.loc[idx, "map_kpa"]
        value = values_series.loc[idx]

        if pd.notna(rpm) and pd.notna(map_kpa) and pd.notna(value):
            rpm_idx = nearest_bin(rpm, rpm_bins)
            map_idx = nearest_bin(map_kpa, map_bins)
            cell_values[rpm_idx][map_idx].append(value)

    # Aggregate each cell
    result: List[List[Optional[float]]] = []
    for rpm_idx in range(n_rpm):
        row: List[Optional[float]] = []
        for map_idx in range(n_map):
            values = cell_values[rpm_idx][map_idx]
            if len(values) >= min_samples:
                if aggregation == "max":
                    row.append(max(values))
                elif aggregation == "min":
                    row.append(min(values))
                elif aggregation == "p95":
                    row.append(np.percentile(values, 95))
                elif aggregation == "sum":
                    row.append(sum(values))
                elif aggregation == "rate":
                    # Rate = count / time (assuming 1 sample = 10ms for now)
                    row.append(len(values) / 10.0)  # events per second
                else:
                    row.append(sum(values) / len(values))
            else:
                row.append(None)
        result.append(row)

    return result


def build_standard_surfaces(
    df: pd.DataFrame,
    rpm_bins: Optional[List[float]] = None,
    map_bins: Optional[List[float]] = None,
    min_samples: int = 3,
) -> Dict[str, Surface2D]:
    """
    Build a standard set of surfaces from a normalized DataFrame.

    Builds surfaces for:
    - Spark timing (front, rear, or global)
    - AFR error (front, rear, or global)
    - Knock activity (if present)

    Args:
        df: Normalized and mode-labeled DataFrame
        rpm_bins: RPM axis bins
        map_bins: MAP axis bins
        min_samples: Minimum samples per cell

    Returns:
        Dict of surface_id -> Surface2D
    """
    surfaces: Dict[str, Surface2D] = {}

    # Spark surfaces
    if "spark_f" in df.columns:
        spec_spark_f = SurfaceSpec(
            value_column="spark_f",
            filter_modes=[ModeTag.WOT, ModeTag.CRUISE],
            aggregation="mean",
            min_samples_per_cell=min_samples,
            surface_id="spark_front",
            title="Spark Timing - Front",
            description="Spark advance for front cylinder across RPM/MAP",
        )
        surfaces["spark_front"] = build_surface(df, spec_spark_f, rpm_bins,
                                                map_bins)

    if "spark_r" in df.columns:
        spec_spark_r = SurfaceSpec(
            value_column="spark_r",
            filter_modes=[ModeTag.WOT, ModeTag.CRUISE],
            aggregation="mean",
            min_samples_per_cell=min_samples,
            surface_id="spark_rear",
            title="Spark Timing - Rear",
            description="Spark advance for rear cylinder across RPM/MAP",
        )
        surfaces["spark_rear"] = build_surface(df, spec_spark_r, rpm_bins,
                                               map_bins)

    if "spark" in df.columns and "spark_f" not in df.columns:
        spec_spark = SurfaceSpec(
            value_column="spark",
            filter_modes=[ModeTag.WOT, ModeTag.CRUISE],
            aggregation="mean",
            min_samples_per_cell=min_samples,
            surface_id="spark_global",
            title="Spark Timing - Global",
            description="Spark advance (single sensor) across RPM/MAP",
        )
        surfaces["spark_global"] = build_surface(df, spec_spark, rpm_bins,
                                                 map_bins)

    # AFR error surfaces
    if "afr_error_f" in df.columns:
        spec_afr_f = SurfaceSpec(
            value_column="afr_error_f",
            filter_modes=[ModeTag.WOT, ModeTag.CRUISE],
            aggregation="mean",
            min_samples_per_cell=min_samples,
            surface_id="afr_error_front",
            title="AFR Error - Front",
            description="AFR error (measured - commanded) for front cylinder",
        )
        surfaces["afr_error_front"] = build_surface(df, spec_afr_f, rpm_bins,
                                                    map_bins)

    if "afr_error_r" in df.columns:
        spec_afr_r = SurfaceSpec(
            value_column="afr_error_r",
            filter_modes=[ModeTag.WOT, ModeTag.CRUISE],
            aggregation="mean",
            min_samples_per_cell=min_samples,
            surface_id="afr_error_rear",
            title="AFR Error - Rear",
            description="AFR error (measured - commanded) for rear cylinder",
        )
        surfaces["afr_error_rear"] = build_surface(df, spec_afr_r, rpm_bins,
                                                   map_bins)

    if "afr_error" in df.columns and "afr_error_f" not in df.columns:
        spec_afr = SurfaceSpec(
            value_column="afr_error",
            filter_modes=[ModeTag.WOT, ModeTag.CRUISE],
            aggregation="mean",
            min_samples_per_cell=min_samples,
            surface_id="afr_error_global",
            title="AFR Error - Global",
            description="AFR error (single sensor) across RPM/MAP",
        )
        surfaces["afr_error_global"] = build_surface(df, spec_afr, rpm_bins,
                                                     map_bins)

    # Knock surfaces (if present)
    if "knock" in df.columns or "knock_f" in df.columns:
        knock_col = "knock_f" if "knock_f" in df.columns else "knock"
        spec_knock = SurfaceSpec(
            value_column=knock_col,
            filter_modes=[ModeTag.WOT],
            aggregation="mean",
            min_samples_per_cell=min_samples,
            surface_id="knock_activity",
            title="Knock Activity",
            description="Knock sensor activity across RPM/MAP",
        )
        try:
            surfaces["knock_activity"] = build_surface(df, spec_knock,
                                                       rpm_bins, map_bins)
        except Exception:
            pass  # Skip if knock column has issues

    return surfaces


def surface_to_dict(surface: Surface2D) -> Dict:
    """
    Serialize a Surface2D to a JSON-compatible dict.

    Convenience wrapper for Surface2D.to_dict().
    """
    return surface.to_dict()
