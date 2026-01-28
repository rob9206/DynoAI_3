"""
DynoAI NextGen Analysis Payload

Defines the stable JSON schema for all NextGen analysis outputs.
This payload is the single source of truth that can be consumed by:
- The frontend UI
- AI narration layers
- Training data collectors
- External integrations

The schema is versioned (dynoai.nextgen@1) to support future evolution.

Usage:
    from dynoai.core.nextgen_payload import NextGenAnalysisPayload

    payload = NextGenAnalysisPayload(
        run_id="run_123",
        inputs_present={"rpm": True, "spark_f": True, ...},
        mode_summary={"wot": 150, "cruise": 500, ...},
        surfaces={"spark_front": spark_surface.to_dict(), ...},
        spark_valley=[finding.to_dict() for finding in findings],
        cause_tree=cause_result.to_dict(),
        next_tests=test_plan.to_dict(),
    )

    # Serialize to JSON
    json_data = payload.to_dict()
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

__all__ = [
    "NextGenAnalysisPayload",
    "SCHEMA_VERSION",
    "ECU_MODEL_NOTES",
]

# Schema version for forward compatibility
SCHEMA_VERSION = "dynoai.nextgen@1"

# =============================================================================
# ECU Model Notes (Short, Factual)
# =============================================================================

# These notes explain the ECU mental model to help users understand findings.
# Keep them general and conceptual - no step-by-step tuning guidance.
ECU_MODEL_NOTES = [
    "VE is a correction surface on a base air model; closed-loop can mask VE error at steady state.",
    "Final spark = base table + modifiers + knock retard; knock always has authority to pull timing.",
    "Spark valley at high MAP often aligns with torque/VE peak and knock margin limits.",
    "AFR error (measured - commanded) reveals where VE correction is insufficient.",
    "Rear cylinder typically runs hotter on V-twins, making it more knock-prone.",
    "Transient enrichment compensates for wall wetting; closed-loop cannot correct fast transients.",
]

# =============================================================================
# Payload Dataclass
# =============================================================================


@dataclass
class NextGenAnalysisPayload:
    """
    Complete NextGen analysis payload.

    This is the unified output format for all NextGen analysis.
    It is designed to be JSON-serializable without custom encoders.

    Attributes:
        run_id: Unique identifier for the run
        generated_at: ISO timestamp of generation
        inputs_present: Dict of channel_name -> bool indicating availability
        channel_readiness: Channel readiness checklist and feature availability
        mode_summary: Dict of mode_name -> sample_count
        surfaces: Dict of surface_id -> serialized Surface2D
        spark_valley: List of serialized SparkValleyFinding
        cause_tree: Serialized CauseTreeResult
        next_tests: Serialized NextTestPlan
        notes_warnings: List of informational notes and warnings
        warning_codes: List of stable warning codes for programmatic use
    """

    run_id: str
    inputs_present: Dict[str, bool] = field(default_factory=dict)
    channel_readiness: Dict[str, Any] = field(default_factory=dict)
    mode_summary: Dict[str, int] = field(default_factory=dict)
    surfaces: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    spark_valley: List[Dict[str, Any]] = field(default_factory=list)
    cause_tree: Dict[str, Any] = field(default_factory=dict)
    next_tests: Dict[str, Any] = field(default_factory=dict)
    notes_warnings: List[str] = field(default_factory=list)
    warning_codes: List[str] = field(default_factory=list)
    ecu_model_notes: List[str] = field(
        default_factory=lambda: list(ECU_MODEL_NOTES))

    # Metadata
    schema_version: str = SCHEMA_VERSION
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize to a JSON-compatible dictionary.

        This method ensures all nested objects are converted to dicts.
        """
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "generated_at": self.generated_at,
            "inputs_present": self.inputs_present,
            "channel_readiness": self.channel_readiness,
            "mode_summary": self.mode_summary,
            "surfaces": self.surfaces,
            "spark_valley": self.spark_valley,
            "cause_tree": self.cause_tree,
            "next_tests": self.next_tests,
            "notes_warnings": self.notes_warnings,
            "warning_codes": self.warning_codes,
            "ecu_model_notes": self.ecu_model_notes,
        }

    def to_json(self, indent: int = 2) -> str:
        """
        Serialize to JSON string.

        Args:
            indent: Indentation level for pretty printing

        Returns:
            JSON string
        """
        return json.dumps(self.to_dict(), indent=indent, default=str)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NextGenAnalysisPayload":
        """
        Deserialize from a dictionary.

        Args:
            data: Dict from JSON parsing

        Returns:
            NextGenAnalysisPayload instance
        """
        return cls(
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            run_id=data.get("run_id", ""),
            generated_at=data.get("generated_at",
                                  datetime.now(timezone.utc).isoformat()),
            inputs_present=data.get("inputs_present", {}),
            channel_readiness=data.get("channel_readiness", {}),
            mode_summary=data.get("mode_summary", {}),
            surfaces=data.get("surfaces", {}),
            spark_valley=data.get("spark_valley", []),
            cause_tree=data.get("cause_tree", {}),
            next_tests=data.get("next_tests", {}),
            notes_warnings=data.get("notes_warnings", []),
            warning_codes=data.get("warning_codes", []),
            ecu_model_notes=data.get("ecu_model_notes", list(ECU_MODEL_NOTES)),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "NextGenAnalysisPayload":
        """
        Deserialize from JSON string.

        Args:
            json_str: JSON string

        Returns:
            NextGenAnalysisPayload instance
        """
        data = json.loads(json_str)
        return cls.from_dict(data)

    # =========================================================================
    # Convenience Properties
    # =========================================================================

    @property
    def has_per_cylinder_data(self) -> bool:
        """True if per-cylinder surfaces are available."""
        return ("spark_front" in self.surfaces or "spark_rear" in self.surfaces
                or "afr_error_front" in self.surfaces)

    @property
    def has_spark_valley(self) -> bool:
        """True if spark valley findings exist."""
        return len(self.spark_valley) > 0

    @property
    def has_hypotheses(self) -> bool:
        """True if cause tree contains hypotheses."""
        hypotheses = self.cause_tree.get("hypotheses", [])
        return len(hypotheses) > 0

    @property
    def top_hypothesis(self) -> Optional[Dict[str, Any]]:
        """Get the highest-confidence hypothesis."""
        hypotheses = self.cause_tree.get("hypotheses", [])
        if not hypotheses:
            return None
        return max(hypotheses, key=lambda h: h.get("confidence", 0))

    @property
    def total_samples(self) -> int:
        """Total number of samples analyzed."""
        # Handle both old format (dict of counts) and new format (dict with counts/durations)
        if isinstance(self.mode_summary, dict):
            if "counts" in self.mode_summary:
                return sum(self.mode_summary["counts"].values())
            elif "total_samples" in self.mode_summary:
                return self.mode_summary["total_samples"]
            else:
                return sum(self.mode_summary.values())
        return 0

    @property
    def surface_count(self) -> int:
        """Number of surfaces generated."""
        return len(self.surfaces)

    @property
    def test_step_count(self) -> int:
        """Number of recommended test steps."""
        steps = self.next_tests.get("steps", [])
        return len(steps)

    # =========================================================================
    # Summary Generation
    # =========================================================================

    def get_summary(self) -> Dict[str, Any]:
        """
        Generate a high-level summary of the analysis.

        Returns:
            Dict with summary metrics
        """
        summary = {
            "run_id": self.run_id,
            "generated_at": self.generated_at,
            "total_samples": self.total_samples,
            "surface_count": self.surface_count,
            "has_per_cylinder": self.has_per_cylinder_data,
            "has_spark_valley": self.has_spark_valley,
            "hypothesis_count": len(self.cause_tree.get("hypotheses", [])),
            "test_step_count": self.test_step_count,
            "warning_count": len(self.notes_warnings),
        }

        # Add top hypothesis if present
        top = self.top_hypothesis
        if top:
            summary["top_hypothesis"] = {
                "title": top.get("title"),
                "confidence": top.get("confidence"),
                "category": top.get("category"),
            }

        # Add mode distribution highlights
        if self.mode_summary:
            total = self.total_samples
            if total > 0:
                wot_pct = self.mode_summary.get("wot", 0) / total * 100
                cruise_pct = self.mode_summary.get("cruise", 0) / total * 100
                summary["mode_highlights"] = {
                    "wot_percent": round(wot_pct, 1),
                    "cruise_percent": round(cruise_pct, 1),
                }

        return summary


# =============================================================================
# Builder Function
# =============================================================================


def build_nextgen_payload(
        run_id: str,
        normalization_result: Any,  # NormalizationResult from log_normalizer
        mode_result: Any,  # ModeLabeledFrame from mode_detection
        surfaces: Dict[str, Any],  # Dict[str, Surface2D] from surface_builder
        spark_valley_findings: List[
            Any],  # List[SparkValleyFinding] from spark_valley
        cause_tree_result: Any,  # CauseTreeResult from cause_tree
        test_plan: Any,  # NextTestPlan from next_test_planner
        channel_readiness: Any = None,  # ChannelReadiness from log_normalizer
) -> NextGenAnalysisPayload:
    """
    Build a NextGenAnalysisPayload from analysis components.

    This is a convenience function that handles serialization of all components.

    Args:
        run_id: Unique run identifier
        normalization_result: Result from log_normalizer.normalize_dataframe()
        mode_result: Result from mode_detection.label_modes()
        surfaces: Dict of Surface2D objects from surface_builder
        spark_valley_findings: List of SparkValleyFinding from spark_valley
        cause_tree_result: CauseTreeResult from cause_tree
        test_plan: NextTestPlan from next_test_planner
        channel_readiness: Optional ChannelReadiness from log_normalizer

    Returns:
        NextGenAnalysisPayload ready for JSON serialization
    """
    # Build inputs_present from normalization result
    inputs_present = {}
    if hasattr(normalization_result, "presence"):
        presence = normalization_result.presence
        inputs_present = {
            "rpm": presence.has_required,
            "map_kpa": presence.has_required,
            "tps": presence.has_tps,
            "iat": presence.has_iat,
            "ect": presence.has_ect,
            "afr_meas_f": presence.has_per_cylinder_afr,
            "afr_meas_r": presence.has_per_cylinder_afr,
            "afr_meas": presence.has_global_afr,
            "spark_f": presence.has_per_cylinder_spark,
            "spark_r": presence.has_per_cylinder_spark,
            "spark": presence.has_global_spark,
            "knock": presence.has_knock,
        }

    # Build channel readiness dict
    channel_readiness_dict = {}
    if channel_readiness is not None:
        if hasattr(channel_readiness, "to_dict"):
            channel_readiness_dict = channel_readiness.to_dict()
        elif isinstance(channel_readiness, dict):
            channel_readiness_dict = channel_readiness

    # Get mode summary (with durations if available)
    mode_summary = {}
    if hasattr(mode_result, "to_summary_dict"):
        mode_summary = mode_result.to_summary_dict()
    elif hasattr(mode_result, "summary_counts"):
        mode_summary = mode_result.summary_counts

    # Serialize surfaces
    surfaces_dict = {}
    for surface_id, surface in surfaces.items():
        if hasattr(surface, "to_dict"):
            surfaces_dict[surface_id] = surface.to_dict()
        else:
            surfaces_dict[surface_id] = surface

    # Serialize spark valley findings
    spark_valley_list = []
    for finding in spark_valley_findings:
        if hasattr(finding, "to_dict"):
            spark_valley_list.append(finding.to_dict())
        else:
            spark_valley_list.append(finding)

    # Serialize cause tree
    cause_tree_dict = {}
    if hasattr(cause_tree_result, "to_dict"):
        cause_tree_dict = cause_tree_result.to_dict()
    elif isinstance(cause_tree_result, dict):
        cause_tree_dict = cause_tree_result

    # Serialize test plan
    next_tests_dict = {}
    if hasattr(test_plan, "to_dict"):
        next_tests_dict = test_plan.to_dict()
    elif isinstance(test_plan, dict):
        next_tests_dict = test_plan

    # Collect warnings (human-readable)
    notes_warnings = []
    if hasattr(normalization_result, "warnings"):
        notes_warnings.extend(normalization_result.warnings)

    # Collect warning codes (stable, for programmatic use)
    warning_codes = []
    if hasattr(normalization_result, "warning_codes"):
        warning_codes = normalization_result.warning_codes
    elif hasattr(normalization_result, "structured_warnings"):
        warning_codes = [
            w.code for w in normalization_result.structured_warnings
        ]

    return NextGenAnalysisPayload(
        run_id=run_id,
        inputs_present=inputs_present,
        channel_readiness=channel_readiness_dict,
        mode_summary=mode_summary,
        surfaces=surfaces_dict,
        spark_valley=spark_valley_list,
        cause_tree=cause_tree_dict,
        next_tests=next_tests_dict,
        notes_warnings=notes_warnings,
        warning_codes=warning_codes,
    )
