"""
Cross-Run Coverage Tracker

Aggregates coverage across multiple runs for the same dyno/vehicle to enable
predictive test planning that learns from previous sessions.

Storage: config/coverage_tracker/<vehicle_id>.json
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Storage location for coverage trackers
TRACKER_DIR = Path("config/coverage_tracker")
try:
    TRACKER_DIR.mkdir(parents=True, exist_ok=True)
except (PermissionError, OSError) as e:
    # Fall back to /tmp in Docker or other restricted environments
    logger.warning(f"Cannot create {TRACKER_DIR}: {e}. Using /tmp fallback.")
    TRACKER_DIR = Path("/tmp/coverage_tracker")
    TRACKER_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class CumulativeCoverage:
    """Aggregated coverage across multiple runs."""
    
    vehicle_id: str
    dyno_signature: str  # From jetdrive_mapping provider signature
    total_runs: int = 0
    run_ids: list[str] = field(default_factory=list)
    aggregated_hit_count: dict[str, list[list[int]]] = field(default_factory=dict)
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON storage."""
        return {
            "vehicle_id": self.vehicle_id,
            "dyno_signature": self.dyno_signature,
            "total_runs": self.total_runs,
            "run_ids": self.run_ids,
            "aggregated_hit_count": self.aggregated_hit_count,
            "last_updated": self.last_updated,
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CumulativeCoverage":
        """Deserialize from dict."""
        return cls(
            vehicle_id=data["vehicle_id"],
            dyno_signature=data["dyno_signature"],
            total_runs=data.get("total_runs", 0),
            run_ids=data.get("run_ids", []),
            aggregated_hit_count=data.get("aggregated_hit_count", {}),
            last_updated=data.get("last_updated", datetime.now().isoformat()),
            created_at=data.get("created_at", datetime.now().isoformat()),
        )


# =============================================================================
# Persistence
# =============================================================================

def get_tracker_path(vehicle_id: str) -> Path:
    """Get path to coverage tracker file for vehicle."""
    safe_id = vehicle_id.replace("/", "_").replace("\\", "_")
    return TRACKER_DIR / f"{safe_id}.json"


def load_cumulative_coverage(vehicle_id: str) -> CumulativeCoverage | None:
    """Load cumulative coverage for vehicle."""
    path = get_tracker_path(vehicle_id)
    
    if not path.exists():
        return None
    
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        return CumulativeCoverage.from_dict(data)
    except Exception as e:
        logger.error(f"Failed to load coverage tracker for {vehicle_id}: {e}")
        return None


def save_cumulative_coverage(coverage: CumulativeCoverage) -> bool:
    """Save cumulative coverage to disk."""
    path = get_tracker_path(coverage.vehicle_id)
    
    try:
        TRACKER_DIR.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w') as f:
            json.dump(coverage.to_dict(), f, indent=2)
        
        logger.info(f"Saved coverage tracker for {coverage.vehicle_id} ({coverage.total_runs} runs)")
        return True
    except Exception as e:
        logger.error(f"Failed to save coverage tracker: {e}")
        return False


# =============================================================================
# Coverage Aggregation
# =============================================================================

def aggregate_run_coverage(
    vehicle_id: str,
    run_id: str,
    surfaces: dict[str, Any],
    dyno_signature: str = "unknown",
) -> CumulativeCoverage:
    """
    Add a run's coverage to the cumulative tracker.
    
    Args:
        vehicle_id: Vehicle identifier
        run_id: Run identifier
        surfaces: Dict of surface_id -> Surface2D dict
        dyno_signature: Provider signature from jetdrive_mapping
    
    Returns:
        Updated CumulativeCoverage
    """
    # Load or create tracker
    coverage = load_cumulative_coverage(vehicle_id)
    
    if coverage is None:
        coverage = CumulativeCoverage(
            vehicle_id=vehicle_id,
            dyno_signature=dyno_signature,
        )
    
    # Update metadata
    coverage.total_runs += 1
    if run_id not in coverage.run_ids:
        coverage.run_ids.append(run_id)
    coverage.last_updated = datetime.now().isoformat()
    
    # Aggregate hit counts from surfaces
    for surface_id, surface_dict in surfaces.items():
        hit_count = surface_dict.get("hit_count", [])
        
        if not hit_count:
            continue
        
        # Initialize aggregated matrix if needed
        if surface_id not in coverage.aggregated_hit_count:
            # Create zero matrix matching shape
            rows = len(hit_count)
            cols = len(hit_count[0]) if rows > 0 else 0
            coverage.aggregated_hit_count[surface_id] = [[0] * cols for _ in range(rows)]
        
        # Add this run's hit counts
        aggregated = coverage.aggregated_hit_count[surface_id]
        for i, row in enumerate(hit_count):
            for j, count in enumerate(row):
                if i < len(aggregated) and j < len(aggregated[i]):
                    aggregated[i][j] += int(count) if count else 0
    
    # Save tracker
    save_cumulative_coverage(coverage)
    
    logger.info(
        f"Aggregated coverage for {vehicle_id}: run {run_id} "
        f"({coverage.total_runs} total runs)"
    )
    
    return coverage


def get_cumulative_gaps(
    vehicle_id: str,
    min_hits: int = 5,
) -> list[dict[str, Any]]:
    """
    Get coverage gaps based on cumulative coverage across all runs.
    
    Args:
        vehicle_id: Vehicle identifier
        min_hits: Minimum hit count threshold (default 5 across all runs)
    
    Returns:
        List of gap dicts with rpm_range, map_range, impact, etc.
    """
    coverage = load_cumulative_coverage(vehicle_id)
    
    if not coverage or not coverage.aggregated_hit_count:
        return []
    
    gaps = []
    
    # Define high-impact regions
    regions = [
        {
            "name": "high_map_midrange",
            "rpm_range": (2500, 4500),
            "map_range": (80, 100),
            "impact": "high",
            "description": "High-load midrange - knock-sensitive and torque peak region",
        },
        {
            "name": "idle_low_map",
            "rpm_range": (500, 1500),
            "map_range": (20, 40),
            "impact": "medium",
            "description": "Idle and low-load - stability and sensor quality critical",
        },
        {
            "name": "tip_in_zone",
            "rpm_range": (2000, 4500),
            "map_range": (50, 85),
            "impact": "high",
            "description": "Tip-in transition zone - transient fueling sensitive",
        },
    ]
    
    # Analyze each surface
    for surface_id, hit_matrix in coverage.aggregated_hit_count.items():
        rows = len(hit_matrix)
        cols = len(hit_matrix[0]) if rows > 0 else 0
        
        if rows == 0 or cols == 0:
            continue
        
        # Check each region for gaps
        for region in regions:
            rpm_min, rpm_max = region["rpm_range"]
            map_min, map_max = region["map_range"]
            
            # Find cells in region
            empty_cells = 0
            total_cells = 0
            
            # Approximate cell mapping (assuming standard bins)
            # RPM bins: typically 500-8000 in steps
            # MAP bins: typically 20-100 in steps
            
            for i in range(rows):
                for j in range(cols):
                    # Rough mapping to RPM/MAP ranges
                    # This assumes standard binning - may need adjustment
                    rpm_estimate = 500 + (i * 7500 / rows)
                    map_estimate = 20 + (j * 80 / cols)
                    
                    if (rpm_min <= rpm_estimate <= rpm_max and
                        map_min <= map_estimate <= map_max):
                        total_cells += 1
                        if hit_matrix[i][j] < min_hits:
                            empty_cells += 1
            
            if total_cells > 0:
                coverage_pct = ((total_cells - empty_cells) / total_cells) * 100
                
                # Only report gaps with significant missing coverage
                if empty_cells > 0:
                    gaps.append({
                        "surface_id": surface_id,
                        "region_name": region["name"],
                        "rpm_range": region["rpm_range"],
                        "map_range": region["map_range"],
                        "empty_cells": empty_cells,
                        "total_cells": total_cells,
                        "coverage_pct": round(coverage_pct, 1),
                        "impact": region["impact"],
                        "description": region["description"],
                    })
    
    # Sort by impact then empty cell count
    impact_order = {"high": 0, "medium": 1, "low": 2}
    gaps.sort(key=lambda g: (impact_order.get(g["impact"], 3), -g["empty_cells"]))
    
    return gaps


def get_coverage_summary(vehicle_id: str) -> dict[str, Any] | None:
    """
    Get summary of cumulative coverage for a vehicle.
    
    Returns:
        Summary dict with total runs, surfaces, overall coverage
    """
    coverage = load_cumulative_coverage(vehicle_id)
    
    if not coverage:
        return None
    
    # Calculate overall coverage stats
    total_cells = 0
    covered_cells = 0
    
    for surface_id, hit_matrix in coverage.aggregated_hit_count.items():
        for row in hit_matrix:
            for count in row:
                total_cells += 1
                if count >= 3:  # Standard threshold
                    covered_cells += 1
    
    coverage_pct = (covered_cells / total_cells * 100) if total_cells > 0 else 0.0
    
    return {
        "vehicle_id": coverage.vehicle_id,
        "dyno_signature": coverage.dyno_signature,
        "total_runs": coverage.total_runs,
        "run_ids": coverage.run_ids,
        "surfaces": list(coverage.aggregated_hit_count.keys()),
        "total_cells": total_cells,
        "covered_cells": covered_cells,
        "coverage_pct": round(coverage_pct, 1),
        "last_updated": coverage.last_updated,
        "created_at": coverage.created_at,
    }


def reset_cumulative_coverage(vehicle_id: str) -> bool:
    """Reset cumulative coverage for a vehicle."""
    path = get_tracker_path(vehicle_id)
    
    try:
        if path.exists():
            path.unlink()
            logger.info(f"Reset coverage tracker for {vehicle_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to reset coverage tracker: {e}")
        return False
