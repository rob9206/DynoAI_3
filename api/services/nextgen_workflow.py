"""
DynoAI NextGen Workflow Service

Orchestrates the NextGen analysis pipeline:
1. Load/normalize CSV data
2. Detect operating modes
3. Build surfaces (spark, AFR error, knock)
4. Detect spark valley
5. Build cause tree hypotheses
6. Generate next-test plan
7. Package and cache payload

Usage:
    from api.services.nextgen_workflow import NextGenWorkflow, get_nextgen_workflow
    
    workflow = get_nextgen_workflow()
    result = workflow.generate_for_run("run_123", force=False)
    
    if result["success"]:
        payload = result["payload"]
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from api.services.run_manager import get_run_manager
from dynoai.core.cause_tree import build_cause_tree
from dynoai.core.log_normalizer import normalize_dataframe, get_channel_readiness
from dynoai.core.mode_detection import label_modes
from dynoai.core.next_test_planner import generate_test_plan
from dynoai.core.nextgen_payload import (
    SCHEMA_VERSION,
    NextGenAnalysisPayload,
    build_nextgen_payload,
)
from dynoai.core.spark_valley import detect_valleys_multi_cylinder
from dynoai.core.surface_builder import build_standard_surfaces

__all__ = [
    "NextGenWorkflow",
    "get_nextgen_workflow",
    "TestPlannerConstraints",
    "get_planner_constraints",
    "save_planner_constraints",
]

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

CONSTRAINTS_DIR = Path("config/planner_constraints")
CONSTRAINTS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class TestPlannerConstraints:
    """User-configurable constraints for test planning."""
    
    min_rpm: int = 1000
    max_rpm: int = 7000
    min_map_kpa: int = 20
    max_map_kpa: int = 100
    max_pulls_per_session: int = 8
    preferred_test_environment: str = "both"  # inertia_dyno, street, both
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "min_rpm": self.min_rpm,
            "max_rpm": self.max_rpm,
            "min_map_kpa": self.min_map_kpa,
            "max_map_kpa": self.max_map_kpa,
            "max_pulls_per_session": self.max_pulls_per_session,
            "preferred_test_environment": self.preferred_test_environment,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TestPlannerConstraints":
        return cls(
            min_rpm=data.get("min_rpm", 1000),
            max_rpm=data.get("max_rpm", 7000),
            min_map_kpa=data.get("min_map_kpa", 20),
            max_map_kpa=data.get("max_map_kpa", 100),
            max_pulls_per_session=data.get("max_pulls_per_session", 8),
            preferred_test_environment=data.get("preferred_test_environment", "both"),
        )


def get_constraints_path(vehicle_id: str = "default") -> Path:
    """Get path to constraints file."""
    safe_id = vehicle_id.replace("/", "_").replace("\\", "_")
    return CONSTRAINTS_DIR / f"{safe_id}.json"


def get_planner_constraints(vehicle_id: str = "default") -> TestPlannerConstraints:
    """Load test planner constraints for vehicle."""
    path = get_constraints_path(vehicle_id)
    
    if not path.exists():
        return TestPlannerConstraints()  # Default
    
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        return TestPlannerConstraints.from_dict(data)
    except Exception as e:
        logger.warning(f"Failed to load planner constraints: {e}")
        return TestPlannerConstraints()


def save_planner_constraints(constraints: TestPlannerConstraints, vehicle_id: str = "default") -> bool:
    """Save test planner constraints."""
    path = get_constraints_path(vehicle_id)
    
    try:
        CONSTRAINTS_DIR.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w') as f:
            json.dump(constraints.to_dict(), f, indent=2)
        
        logger.info(f"Saved planner constraints for {vehicle_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to save planner constraints: {e}")
        return False


# =============================================================================
# Output File Names
# =============================================================================

NEXTGEN_PAYLOAD_FILE = "NextGenAnalysis.json"
NEXTGEN_META_FILE = "NextGenAnalysis_Meta.json"


# =============================================================================
# Workflow Service
# =============================================================================

class NextGenWorkflow:
    """
    Orchestrates the NextGen analysis pipeline.
    
    Handles:
    - Input resolution (RunManager or fallback)
    - Analysis execution
    - Output caching
    - Metadata generation
    """
    
    def __init__(self, runs_dir: str = "runs"):
        """
        Initialize the workflow service.
        
        Args:
            runs_dir: Base directory for runs
        """
        self._runs_dir = Path(runs_dir)
        self._run_manager = get_run_manager()
    
    def get_input_csv_path(self, run_id: str) -> Optional[Path]:
        """
        Resolve the input CSV path for a run.
        
        Tries RunManager first, then falls back to standard convention.
        
        Args:
            run_id: The run ID
            
        Returns:
            Path to input CSV if found, None otherwise
        """
        # Try RunManager first
        csv_path = self._run_manager.get_run_input_path(run_id)
        if csv_path and csv_path.exists():
            return csv_path
        
        # Fallback to direct path construction
        fallback_path = self._runs_dir / run_id / "input" / "dynoai_input.csv"
        if fallback_path.exists():
            return fallback_path
        
        # Try alternative input filenames
        run_dir = self._runs_dir / run_id / "input"
        if run_dir.exists():
            for pattern in ["*.csv", "*.CSV"]:
                csv_files = list(run_dir.glob(pattern))
                if csv_files:
                    return csv_files[0]
        
        return None
    
    def get_output_dir(self, run_id: str) -> Path:
        """
        Get the output directory for a run, creating if needed.
        
        Args:
            run_id: The run ID
            
        Returns:
            Path to output directory
        """
        output_dir = self._run_manager.get_run_output_dir(run_id)
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            return output_dir
        
        # Fallback: create in run directory root
        run_dir = self._runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir
    
    def load_cached(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Load cached NextGen payload if it exists and schema matches.
        
        Args:
            run_id: The run ID
            
        Returns:
            Cached payload dict if valid, None otherwise
        """
        output_dir = self.get_output_dir(run_id)
        payload_path = output_dir / NEXTGEN_PAYLOAD_FILE
        meta_path = output_dir / NEXTGEN_META_FILE
        
        if not payload_path.exists() or not meta_path.exists():
            return None
        
        try:
            # Check schema version
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            
            if meta.get("schema_version") != SCHEMA_VERSION:
                logger.info(
                    f"Cache invalidated: schema mismatch "
                    f"(cached={meta.get('schema_version')}, current={SCHEMA_VERSION})"
                )
                return None
            
            # Load payload
            with open(payload_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            
            return payload
            
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load cached payload: {e}")
            return None
    
    def generate_for_run(
        self,
        run_id: str,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate NextGen analysis for a run.
        
        Args:
            run_id: The run ID
            force: If True, regenerate even if cached
            
        Returns:
            Dict with success, payload, and metadata
        """
        result: Dict[str, Any] = {
            "success": False,
            "run_id": run_id,
            "generated_at": None,
            "from_cache": False,
            "payload": None,
            "summary": None,
            "download_url": None,
            "error": None,
        }
        
        # Check cache unless force=True
        if not force:
            cached = self.load_cached(run_id)
            if cached:
                result["success"] = True
                result["from_cache"] = True
                result["payload"] = cached
                result["generated_at"] = cached.get("generated_at")
                result["summary"] = self._build_summary(cached)
                result["download_url"] = f"/api/nextgen/{run_id}/download"
                return result
        
        # Find input CSV
        csv_path = self.get_input_csv_path(run_id)
        if not csv_path:
            result["error"] = f"Input CSV not found for run {run_id}"
            return result
        
        try:
            # Execute pipeline
            payload = self._execute_pipeline(run_id, csv_path)
            
            # Write outputs
            output_dir = self.get_output_dir(run_id)
            self._write_outputs(output_dir, payload)
            
            # Build response
            payload_dict = payload.to_dict()
            result["success"] = True
            result["payload"] = payload_dict
            result["generated_at"] = payload.generated_at
            result["summary"] = self._build_summary(payload_dict)
            result["download_url"] = f"/api/nextgen/{run_id}/download"
            
        except Exception as e:
            logger.exception(f"NextGen analysis failed for run {run_id}")
            result["error"] = str(e)
        
        return result
    
    def _execute_pipeline(
        self,
        run_id: str,
        csv_path: Path,
    ) -> NextGenAnalysisPayload:
        """
        Execute the full NextGen analysis pipeline.
        
        Args:
            run_id: The run ID
            csv_path: Path to input CSV
            
        Returns:
            NextGenAnalysisPayload with all analysis results
        """
        logger.info(f"Starting NextGen analysis for run {run_id}")
        
        # Step 1: Load CSV
        logger.info(f"Loading CSV from {csv_path}")
        df = pd.read_csv(csv_path)
        logger.info(f"Loaded {len(df)} rows, {len(df.columns)} columns")
        
        # Step 2: Normalize columns
        logger.info("Normalizing columns...")
        norm_result = normalize_dataframe(df)
        logger.info(
            f"Normalization complete: {len(norm_result.columns_found)} columns found, "
            f"confidence={norm_result.confidence_factor:.2f}"
        )
        
        # Step 2b: Build channel readiness
        logger.info("Building channel readiness...")
        channel_readiness = get_channel_readiness(norm_result)
        logger.info(
            f"Channel readiness: {channel_readiness.required_present}/{channel_readiness.required_total} required, "
            f"{channel_readiness.recommended_present}/{channel_readiness.recommended_total} recommended"
        )
        if channel_readiness.warning_codes:
            logger.info(f"Warning codes: {channel_readiness.warning_codes}")
        
        if not norm_result.presence.has_required:
            raise ValueError("Required columns (rpm, map_kpa) not found in data")
        
        # Step 3: Label operating modes
        logger.info("Detecting operating modes...")
        mode_result = label_modes(norm_result.df)
        logger.info(f"Mode detection complete: {mode_result.summary_counts}")
        
        # Step 4: Build surfaces
        logger.info("Building surfaces...")
        surfaces = build_standard_surfaces(mode_result.df)
        logger.info(f"Built {len(surfaces)} surfaces: {list(surfaces.keys())}")
        
        # Step 5: Detect spark valley
        logger.info("Detecting spark valleys...")
        spark_valley_findings = detect_valleys_multi_cylinder(surfaces)
        logger.info(f"Found {len(spark_valley_findings)} spark valley findings")
        
        # Step 6: Build cause tree
        logger.info("Building cause tree...")
        cause_tree_result = build_cause_tree(
            mode_summary=mode_result.summary_counts,
            surfaces=surfaces,
            spark_valley=spark_valley_findings,
        )
        logger.info(f"Generated {len(cause_tree_result.hypotheses)} hypotheses")
        
        # Step 7: Generate test plan
        logger.info("Generating test plan...")
        test_plan = generate_test_plan(
            surfaces=surfaces,
            cause_tree=cause_tree_result,
            mode_summary=mode_result.summary_counts,
        )
        logger.info(f"Generated {len(test_plan.steps)} test steps")
        
        # Step 8: Build payload
        logger.info("Building payload...")
        payload = build_nextgen_payload(
            run_id=run_id,
            normalization_result=norm_result,
            mode_result=mode_result,
            surfaces=surfaces,
            spark_valley_findings=spark_valley_findings,
            cause_tree_result=cause_tree_result,
            test_plan=test_plan,
            channel_readiness=channel_readiness,
        )
        
        logger.info(f"NextGen analysis complete for run {run_id}")
        return payload
    
    def _write_outputs(
        self,
        output_dir: Path,
        payload: NextGenAnalysisPayload,
    ) -> None:
        """
        Write payload and metadata to output directory.
        
        Args:
            output_dir: Output directory path
            payload: NextGenAnalysisPayload to write
        """
        payload_path = output_dir / NEXTGEN_PAYLOAD_FILE
        meta_path = output_dir / NEXTGEN_META_FILE
        
        # Write payload JSON
        payload_json = payload.to_json(indent=2)
        with open(payload_path, "w", encoding="utf-8") as f:
            f.write(payload_json)
        
        logger.info(f"Wrote payload to {payload_path}")
        
        # Compute SHA256 of payload
        payload_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        
        # Build metadata
        meta = {
            "schema_version": payload.schema_version,
            "run_id": payload.run_id,
            "generated_at": payload.generated_at,
            "row_count": payload.total_samples,
            "columns_present": list(payload.inputs_present.keys()),
            "surface_count": len(payload.surfaces),
            "hypothesis_count": len(payload.cause_tree.get("hypotheses", [])),
            "test_step_count": len(payload.next_tests.get("steps", [])),
            "sha256": payload_hash,
            "file_size_bytes": len(payload_json),
        }
        
        # Write metadata JSON
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
        
        logger.info(f"Wrote metadata to {meta_path}")
    
    def _build_summary(self, payload_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build a summary dict from payload.
        
        Args:
            payload_dict: Serialized payload
            
        Returns:
            Summary dict for API response
        """
        mode_summary = payload_dict.get("mode_summary", {})
        
        # Handle both old format (dict of counts) and new format (dict with counts/durations)
        if isinstance(mode_summary, dict) and "counts" in mode_summary:
            mode_counts = mode_summary.get("counts", {})
            mode_durations = mode_summary.get("durations_sec", {})
        else:
            mode_counts = mode_summary
            mode_durations = {}
        
        total_samples = sum(mode_counts.values()) if mode_counts else 0
        
        hypotheses = payload_dict.get("cause_tree", {}).get("hypotheses", [])
        top_hypothesis = None
        if hypotheses:
            top_hyp = max(hypotheses, key=lambda h: h.get("confidence", 0))
            top_hypothesis = {
                "title": top_hyp.get("title"),
                "confidence": top_hyp.get("confidence"),
                "category": top_hyp.get("category"),
            }
        
        # Extract coverage gaps info
        next_tests = payload_dict.get("next_tests", {})
        coverage_gaps = next_tests.get("coverage_gaps", [])
        coverage_gaps_detailed = next_tests.get("coverage_gaps_detailed", [])
        
        # Count high-impact gaps
        high_impact_gaps = sum(
            1 for g in coverage_gaps_detailed 
            if isinstance(g, dict) and g.get("impact") == "high"
        )
        
        return {
            "total_samples": total_samples,
            "surface_count": len(payload_dict.get("surfaces", {})),
            "spark_valley_count": len(payload_dict.get("spark_valley", [])),
            "hypothesis_count": len(hypotheses),
            "test_step_count": len(next_tests.get("steps", [])),
            "warning_count": len(payload_dict.get("notes_warnings", [])),
            "top_hypothesis": top_hypothesis,
            "mode_distribution": {
                "wot_percent": round(mode_counts.get("wot", 0) / max(total_samples, 1) * 100, 1),
                "cruise_percent": round(mode_counts.get("cruise", 0) / max(total_samples, 1) * 100, 1),
                "idle_percent": round(mode_counts.get("idle", 0) / max(total_samples, 1) * 100, 1),
                "tip_in_percent": round(mode_counts.get("tip_in", 0) / max(total_samples, 1) * 100, 1),
            },
            "mode_durations_sec": mode_durations,
            "coverage_gap_count": len(coverage_gaps),
            "high_impact_gap_count": high_impact_gaps,
            "dyno_step_count": next_tests.get("dyno_step_count", 0),
            "street_step_count": next_tests.get("street_step_count", 0),
        }
    
    def get_payload_path(self, run_id: str) -> Optional[Path]:
        """
        Get path to cached payload file.
        
        Args:
            run_id: The run ID
            
        Returns:
            Path to payload file if exists, None otherwise
        """
        output_dir = self.get_output_dir(run_id)
        payload_path = output_dir / NEXTGEN_PAYLOAD_FILE
        if payload_path.exists():
            return payload_path
        return None


# =============================================================================
# Global Instance
# =============================================================================

_nextgen_workflow: Optional[NextGenWorkflow] = None


def get_nextgen_workflow() -> NextGenWorkflow:
    """Get or create the global NextGenWorkflow instance."""
    global _nextgen_workflow
    if _nextgen_workflow is None:
        _nextgen_workflow = NextGenWorkflow()
    return _nextgen_workflow
