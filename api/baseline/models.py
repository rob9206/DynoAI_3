"""
Data models for One-Pull Baseline.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum


class CellType(str, Enum):
    """How a cell's value was determined."""
    MEASURED = "measured"
    INTERPOLATED = "interpolated"
    EXTRAPOLATED = "extrapolated"


class ValidationSeverity(str, Enum):
    """Severity level for validation issues."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class ValidationIssue:
    """A single validation issue."""
    severity: ValidationSeverity
    code: str
    message: str
    details: Optional[Dict] = None


@dataclass
class InputValidationResult:
    """Result of input data validation."""
    is_valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]

    @property
    def warnings(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]


@dataclass
class FDCAnalysis:
    """Fuel Delivery Characteristic analysis results."""
    overall_fdc: float              # Overall slope
    low_map_fdc: float              # FDC in lower MAP range
    high_map_fdc: float             # FDC in upper MAP range
    stability_score: float          # 0-1, how consistent FDC is
    is_stable: bool                 # True if safe to extrapolate
    instability_warning: Optional[str] = None


@dataclass
class CellConfidence:
    """Detailed confidence breakdown for a cell."""
    total: float                    # Final confidence 0-100
    base_score: float               # Base from cell type
    distance_penalty: float         # Penalty for distance from measured
    stability_bonus: float          # Bonus if FDC is stable
    agreement_bonus: float          # Bonus if predictions agree
    density_bonus: float            # Bonus for high data density nearby


@dataclass
class BaselineResult:
    """Complete baseline generation result."""
    # Core outputs
    ve_corrections: List[List[float]]
    confidence_map: List[List[float]]
    cell_types: List[List[str]]
    rpm_axis: List[int]
    map_axis: List[int]

    # Statistics
    measured_cells: int
    interpolated_cells: int
    extrapolated_cells: int
    avg_confidence: float
    min_confidence: float

    # FDC analysis
    fdc: FDCAnalysis

    # Validation
    input_validation: InputValidationResult

    # Warnings & recommendations
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
