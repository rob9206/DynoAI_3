"""
DynoAI Training Data Collector

Collects and aggregates tuning session data for AI model training.
Converts raw dyno logs and tuning outcomes into structured training patterns.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from api.models.validators import DataValidator
from api.models.training_data_schemas import (
    AFRTargetPattern,
    BuildConfiguration,
    CylinderImbalancePattern,
    DecelPoppingPattern,
    DynoSessionMetadata,
    EnvironmentalConditions,
    HeatSoakPattern,
    KnockTimingPattern,
    TrainingDataset,
    TuningObjective,
    TuningSession,
    VEScalingPattern,
)

logger = logging.getLogger(__name__)


class TrainingDataCollector:
    """
    Collects training data from completed tuning sessions.
    
    Usage:
        collector = TrainingDataCollector()
        
        # Create session from dyno run
        session = collector.create_session_from_run(
            run_id="abc123",
            build_config=build_config,
            objective="ve_optimization"
        )
        
        # Add to dataset
        collector.add_session(session)
        
        # Extract patterns
        collector.extract_all_patterns()
        
        # Save dataset
        collector.save_dataset("training_data/dataset_v1.json")
    """
    
    def __init__(self, dataset_id: Optional[str] = None, strict_mode: bool = False):
        """
        Initialize collector with new or existing dataset.
        
        Args:
            dataset_id: Unique dataset identifier
            strict_mode: If True, raise errors on validation failures.
                        If False, log warnings and continue.
        """
        if dataset_id is None:
            dataset_id = f"dataset_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        self.dataset = TrainingDataset(
            dataset_id=dataset_id,
            version="1.0"
        )
        self.strict_mode = strict_mode
        self.validator = DataValidator()
    
    def create_session_from_run(
        self,
        run_id: str,
        build_config: BuildConfiguration,
        objective: TuningObjective,
        conditions: EnvironmentalConditions,
        dyno_metadata: DynoSessionMetadata,
        initial_tables: Dict[str, List[List[float]]],
        final_tables: Dict[str, List[List[float]]],
        results: Dict[str, Any],
        tuner_id: Optional[str] = None,
    ) -> TuningSession:
        """
        Create a TuningSession from completed dyno run data.
        
        Args:
            run_id: Unique run identifier
            build_config: Engine build configuration
            objective: Primary tuning objective
            conditions: Environmental conditions
            dyno_metadata: Dyno session metadata
            initial_tables: Initial VE/spark tables {"ve_front": [[...]], ...}
            final_tables: Final VE/spark tables after tuning
            results: Results dict with hp, torque, afr metrics, etc.
            tuner_id: Optional tuner identifier
        
        Returns:
            TuningSession object ready to add to dataset
        """
        session = TuningSession(
            session_id=run_id,
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            tuner_id=tuner_id,
            build_config=build_config,
            objective=objective,
            conditions=conditions,
            dyno_metadata=dyno_metadata,
            
            # Tables
            initial_ve_table_front=initial_tables.get("ve_front", []),
            initial_ve_table_rear=initial_tables.get("ve_rear", []),
            initial_spark_table_front=initial_tables.get("spark_front", []),
            initial_spark_table_rear=initial_tables.get("spark_rear", []),
            
            final_ve_table_front=final_tables.get("ve_front", []),
            final_ve_table_rear=final_tables.get("ve_rear", []),
            final_spark_table_front=final_tables.get("spark_front", []),
            final_spark_table_rear=final_tables.get("spark_rear", []),
            
            # Results
            afr_targets=results.get("afr_targets", {}),
            peak_hp=results.get("peak_hp", 0.0),
            peak_torque=results.get("peak_torque", 0.0),
            afr_accuracy_rms_error=results.get("afr_accuracy_rms_error", 0.0),
            max_cylinder_afr_delta=results.get("max_cylinder_afr_delta", 0.0),
            knock_events_detected=results.get("knock_events", 0),
            timing_retard_cells=results.get("timing_retard_cells", 0),
            timing_advance_cells=results.get("timing_advance_cells", 0),
            decel_pop_severity_before=results.get("decel_pop_before", 0),
            decel_pop_severity_after=results.get("decel_pop_after", 0),
            iat_start_f=results.get("iat_start", 0.0),
            iat_end_f=results.get("iat_end", 0.0),
            iat_peak_f=results.get("iat_peak", 0.0),
            hp_variation_due_to_heat=results.get("hp_variation", 0.0),
            tuning_duration_hours=results.get("duration_hours", 0.0),
            iterations_required=results.get("iterations", 0),
            
            # Quality metrics
            tuner_satisfaction=results.get("tuner_satisfaction"),
            customer_satisfaction=results.get("customer_satisfaction"),
            
            # Notes
            challenges_encountered=results.get("challenges", []),
            solutions_applied=results.get("solutions", []),
            notes=results.get("notes", ""),
        )
        
        return session
    
    def add_session(self, session: TuningSession) -> None:
        """
        Add a tuning session to the dataset with validation.
        
        Validates session data against physical constraints and industry norms.
        In strict mode, raises ValueError on validation errors.
        In non-strict mode, logs warnings and continues.
        """
        # Validate session
        validation_result = self.validator.validate_session(session)
        
        # Handle validation results
        if not validation_result.is_valid:
            error_msg = (
                f"Session {session.session_id} validation failed:\n" +
                "\n".join(f"  ERROR: {e}" for e in validation_result.errors)
            )
            
            if self.strict_mode:
                raise ValueError(error_msg)
            else:
                logger.error(error_msg)
        
        # Log warnings even in non-strict mode
        if validation_result.warnings:
            warning_msg = (
                f"Session {session.session_id} validation warnings:\n" +
                "\n".join(f"  WARNING: {w}" for w in validation_result.warnings)
            )
            logger.warning(warning_msg)
        
        # Add to dataset
        self.dataset.add_session(session)
        logger.info(
            f"Added session {session.session_id} to dataset {self.dataset.dataset_id} "
            f"(errors: {len(validation_result.errors)}, warnings: {len(validation_result.warnings)})"
        )
    
    def extract_all_patterns(self) -> None:
        """
        Extract all learnable patterns from collected sessions.
        
        This analyzes the raw session data and generates pattern objects
        for AI training.
        """
        logger.info("Extracting patterns from tuning sessions...")
        
        for session in self.dataset.tuning_sessions:
            # Extract VE scaling patterns
            if session.objective == TuningObjective.VE_OPTIMIZATION:
                ve_pattern = self._extract_ve_pattern(session)
                if ve_pattern:
                    self.dataset.ve_scaling_patterns.append(ve_pattern)
            
            # Extract cylinder balance patterns
            if session.objective == TuningObjective.CYLINDER_BALANCE:
                balance_pattern = self._extract_balance_pattern(session)
                if balance_pattern:
                    self.dataset.cylinder_imbalance_patterns.append(balance_pattern)
            
            # Extract decel pop patterns
            if session.objective == TuningObjective.DECEL_POP_FIX:
                decel_pattern = self._extract_decel_pattern(session)
                if decel_pattern:
                    self.dataset.decel_popping_patterns.append(decel_pattern)
            
            # Extract heat soak patterns
            if session.objective == TuningObjective.HEAT_SOAK_FIX:
                heat_pattern = self._extract_heat_pattern(session)
                if heat_pattern:
                    self.dataset.heat_soak_patterns.append(heat_pattern)
            
            # Extract knock/timing patterns
            if session.objective == TuningObjective.TIMING_OPTIMIZATION:
                timing_pattern = self._extract_timing_pattern(session)
                if timing_pattern:
                    self.dataset.knock_timing_patterns.append(timing_pattern)
            
            # Extract AFR target patterns (from all sessions)
            afr_patterns = self._extract_afr_patterns(session)
            self.dataset.afr_target_patterns.extend(afr_patterns)
        
        logger.info(f"Pattern extraction complete: {self.dataset.summary()}")
    
    def _extract_ve_pattern(self, session: TuningSession) -> Optional[VEScalingPattern]:
        """Extract VE scaling pattern from session."""
        try:
            if not session.initial_ve_table_front or not session.final_ve_table_front:
                return None
            
            # Calculate VE deltas in key regions
            # Idle: RPM idx 0-1, KPA idx 0-2
            idle_delta = self._calculate_ve_delta(
                session.initial_ve_table_front,
                session.final_ve_table_front,
                rpm_range=(0, 2),
                kpa_range=(0, 3)
            )
            
            # Cruise: RPM idx 4-6, KPA idx 3-5
            cruise_delta = self._calculate_ve_delta(
                session.initial_ve_table_front,
                session.final_ve_table_front,
                rpm_range=(4, 7),
                kpa_range=(3, 6)
            )
            
            # Midrange: RPM idx 6-8, KPA idx 6-8
            mid_delta = self._calculate_ve_delta(
                session.initial_ve_table_front,
                session.final_ve_table_front,
                rpm_range=(6, 9),
                kpa_range=(6, 9)
            )
            
            # WOT: RPM idx 8-10, KPA idx 10-12
            wot_delta = self._calculate_ve_delta(
                session.initial_ve_table_front,
                session.final_ve_table_front,
                rpm_range=(8, 11),
                kpa_range=(10, 13)
            )
            
            # Front vs Rear difference
            front_rear_diff = 0.0
            if session.final_ve_table_rear:
                front_rear_diff = self._calculate_table_difference(
                    session.final_ve_table_front,
                    session.final_ve_table_rear
                )
            
            return VEScalingPattern(
                engine_family=session.build_config.engine_family,
                stage=session.build_config.stage,
                cam_overlap_category=session.build_config.cam_spec.get_overlap_category(),
                displacement_ci=session.build_config.displacement_ci,
                ve_delta_idle=idle_delta,
                ve_delta_cruise=cruise_delta,
                ve_delta_midrange=mid_delta,
                ve_delta_wot=wot_delta,
                front_rear_ve_difference_pct=front_rear_diff,
                sessions_observed=1,
            )
        except Exception as e:
            logger.warning(f"Failed to extract VE pattern: {e}")
            return None
    
    def _extract_balance_pattern(self, session: TuningSession) -> Optional[CylinderImbalancePattern]:
        """Extract cylinder imbalance pattern from session."""
        try:
            # Would need imbalance data from session
            # For now, create placeholder
            imbalance_data: List[Tuple[int, int, float]] = []
            
            return CylinderImbalancePattern(
                engine_family=session.build_config.engine_family,
                cam_profile=session.build_config.cam_spec.profile,
                exhaust_type=session.build_config.header_type,
                imbalance_cells=imbalance_data,
                front_ve_corrections=session.final_ve_table_front,
                rear_ve_corrections=session.final_ve_table_rear,
                imbalance_before_max=session.max_cylinder_afr_delta,
                imbalance_after_max=0.0,
                correction_success=session.max_cylinder_afr_delta < 0.3,
            )
        except Exception as e:
            logger.warning(f"Failed to extract balance pattern: {e}")
            return None
    
    def _extract_decel_pattern(self, session: TuningSession) -> Optional[DecelPoppingPattern]:
        """Extract decel popping pattern from session."""
        try:
            return DecelPoppingPattern(
                engine_family=session.build_config.engine_family,
                cam_overlap_deg=(
                    session.build_config.cam_spec.overlap_deg_front +
                    session.build_config.cam_spec.overlap_deg_rear
                ) / 2,
                exhaust_type=session.build_config.header_type,
                pair_valve_present=True,  # Would need to detect from build
                pop_severity=session.decel_pop_severity_before,
                pop_eliminated=(session.decel_pop_severity_after <= 2),
                customer_satisfaction=session.customer_satisfaction or 0,
            )
        except Exception as e:
            logger.warning(f"Failed to extract decel pattern: {e}")
            return None
    
    def _extract_heat_pattern(self, session: TuningSession) -> Optional[HeatSoakPattern]:
        """Extract heat soak pattern from session."""
        try:
            return HeatSoakPattern(
                ambient_temp_f=session.conditions.ambient_temp_f,
                airflow_cfm=session.dyno_metadata.fan_airflow_cfm,
                iat_initial_f=session.iat_start_f,
                iat_peak_f=session.iat_peak_f,
                hp_variation_before=session.hp_variation_due_to_heat,
                hp_variation_after=0.0,  # Would measure post-correction
            )
        except Exception as e:
            logger.warning(f"Failed to extract heat pattern: {e}")
            return None
    
    def _extract_timing_pattern(self, session: TuningSession) -> Optional[KnockTimingPattern]:
        """Extract knock/timing pattern from session."""
        try:
            return KnockTimingPattern(
                compression_ratio=session.build_config.compression_ratio,
                fuel_octane=session.build_config.octane_requirement,
                cam_profile=session.build_config.cam_spec.profile,
                altitude_ft=session.conditions.altitude_ft,
                initial_timing_table=session.initial_spark_table_front,
                final_timing_table=session.final_spark_table_front,
                knock_free=(session.knock_events_detected == 0),
            )
        except Exception as e:
            logger.warning(f"Failed to extract timing pattern: {e}")
            return None
    
    def _extract_afr_patterns(self, session: TuningSession) -> List[AFRTargetPattern]:
        """Extract AFR target patterns from session."""
        patterns = []
        
        for region, target_afr in session.afr_targets.items():
            # Map region to RPM/load ranges
            rpm_range, load_range = self._get_region_ranges(region)
            
            pattern = AFRTargetPattern(
                operating_region=region,
                rpm_range=rpm_range,
                load_range=load_range,
                target_afr=target_afr,
                acceptable_range=(target_afr - 0.2, target_afr + 0.2),
                altitude_ft=session.conditions.altitude_ft,
                ambient_temp_f=session.conditions.ambient_temp_f,
                fuel_octane=session.build_config.octane_requirement,
                rationale=f"{region} tuning for {session.build_config.stage.value}",
            )
            patterns.append(pattern)
        
        return patterns
    
    def _calculate_ve_delta(
        self,
        initial: List[List[float]],
        final: List[List[float]],
        rpm_range: Tuple[int, int],
        kpa_range: Tuple[int, int]
    ) -> float:
        """Calculate average VE delta in a region."""
        if not initial or not final:
            return 0.0
        
        deltas = []
        for r in range(rpm_range[0], rpm_range[1]):
            for k in range(kpa_range[0], kpa_range[1]):
                if r < len(initial) and k < len(initial[0]) and \
                   r < len(final) and k < len(final[0]):
                    if initial[r][k] > 0:
                        delta_pct = (final[r][k] - initial[r][k]) / initial[r][k] * 100
                        deltas.append(delta_pct)
        
        return sum(deltas) / len(deltas) if deltas else 0.0
    
    def _calculate_table_difference(
        self,
        table1: List[List[float]],
        table2: List[List[float]]
    ) -> float:
        """Calculate average percentage difference between two tables."""
        if not table1 or not table2:
            return 0.0
        
        diffs = []
        for r in range(min(len(table1), len(table2))):
            for k in range(min(len(table1[0]), len(table2[0]))):
                if table1[r][k] > 0 and table2[r][k] > 0:
                    diff_pct = abs(table1[r][k] - table2[r][k]) / table1[r][k] * 100
                    diffs.append(diff_pct)
        
        return sum(diffs) / len(diffs) if diffs else 0.0
    
    def _get_region_ranges(self, region: str) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """Map operating region name to RPM/load ranges."""
        region_map = {
            "idle": ((800, 1200), (15, 30)),
            "cruise": ((2000, 3000), (25, 45)),
            "acceleration": ((2500, 4500), (50, 80)),
            "wot": ((3000, 6000), (85, 105)),
            "decel": ((1500, 4000), (10, 25)),
        }
        return region_map.get(region, ((1000, 6000), (10, 105)))
    
    def save_dataset(self, output_path: str | Path) -> None:
        """Save training dataset to JSON file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert dataset to dictionary (would need serialization methods)
        dataset_dict = {
            "dataset_id": self.dataset.dataset_id,
            "version": self.dataset.version,
            "created_at": self.dataset.created_at,
            "summary": self.dataset.summary(),
            # Would serialize all sessions and patterns
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(dataset_dict, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved training dataset to {output_path}")
    
    def load_dataset(self, input_path: str | Path) -> None:
        """Load training dataset from JSON file."""
        input_path = Path(input_path)
        
        with open(input_path, 'r', encoding='utf-8') as f:
            dataset_dict = json.load(f)
        
        # Would deserialize into TrainingDataset object
        logger.info(f"Loaded training dataset from {input_path}")


__all__ = ["TrainingDataCollector"]

