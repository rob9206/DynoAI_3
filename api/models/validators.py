"""
DynoAI Training Data Validators

Validates training data against physical constraints, industry norms,
and statistical patterns to ensure data authenticity and quality.
"""

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from api.models.training_data_schemas import (
    BuildConfiguration,
    CamProfile,
    StageLevel,
    TuningSession,
)


@dataclass
class ValidationResult:
    """Result of validation check."""

    is_valid: bool
    errors: List[str]
    warnings: List[str]

    def add_error(self, message: str) -> None:
        """Add validation error."""
        self.errors.append(message)
        self.is_valid = False

    def add_warning(self, message: str) -> None:
        """Add validation warning."""
        self.warnings.append(message)


class PhysicsValidator:
    """Validates data against physical laws and engineering constraints."""

    # Known physical constants
    HP_TORQUE_CONSTANT = 5252  # HP = (Torque × RPM) / 5252

    # Realistic ranges for V-twin engines
    HP_PER_CI_MIN = 0.5  # Very mild build
    HP_PER_CI_MAX = 1.3  # Race-level build
    HP_PER_CI_TYPICAL = (0.7, 1.0)  # Street builds

    COMPRESSION_RATIO_MIN = 8.0
    COMPRESSION_RATIO_MAX = 14.0
    COMPRESSION_RATIO_TYPICAL = (9.0, 11.5)

    CAM_OVERLAP_MAX = 70.0  # Degrees
    CAM_DURATION_MIN = 180.0  # Degrees @ 0.053"
    CAM_DURATION_MAX = 280.0

    VE_VALUE_MIN = 40.0  # Percent
    VE_VALUE_MAX = 160.0
    VE_VALUE_TYPICAL = (70.0, 130.0)

    VE_CHANGE_MAX = 50.0  # Max percent change in single tune

    AFR_ERROR_GOOD = 0.3  # RMS error for quality tune
    AFR_ERROR_MAX = 1.0  # Acceptable maximum

    CYLINDER_IMBALANCE_TYPICAL = (0.3, 1.2)  # AFR points
    CYLINDER_IMBALANCE_MAX = 2.0

    @staticmethod
    def validate_displacement(config: BuildConfiguration) -> ValidationResult:
        """
        Validate displacement matches bore and stroke.

        Formula: CI = (bore² × π × stroke × cylinders) / 4
        For V-twin: cylinders = 2
        """
        result = ValidationResult(is_valid=True, errors=[], warnings=[])

        if config.bore_in <= 0 or config.stroke_in <= 0:
            result.add_error("Bore and stroke must be positive values")
            return result

        # Calculate displacement from bore and stroke
        calculated_ci = (config.bore_in**2) * math.pi * config.stroke_in * 2 / 4

        # Allow 5 CI tolerance for rounding
        tolerance = 5.0
        diff = abs(config.displacement_ci - calculated_ci)

        if diff > tolerance:
            result.add_error(
                f"Displacement mismatch: {config.displacement_ci} CI specified, "
                f'but bore {config.bore_in}" × stroke {config.stroke_in}" = '
                f"{calculated_ci:.1f} CI (difference: {diff:.1f} CI)"
            )

        return result

    @staticmethod
    def validate_hp_torque_relationship(
        hp: float, torque: float, rpm_at_peak_torque: float = 3500
    ) -> ValidationResult:
        """
        Validate HP and torque follow physics: HP = (Torque × RPM) / 5252

        V-twins typically peak torque around 3000-4000 RPM.
        """
        result = ValidationResult(is_valid=True, errors=[], warnings=[])

        if hp <= 0 or torque <= 0:
            result.add_error("HP and torque must be positive values")
            return result

        # Calculate expected HP from torque at typical peak torque RPM
        calculated_hp = (
            torque * rpm_at_peak_torque
        ) / PhysicsValidator.HP_TORQUE_CONSTANT

        # Allow 20% tolerance (different peak RPMs, measurement variance)
        tolerance_pct = 20.0
        diff_pct = abs(hp - calculated_hp) / calculated_hp * 100

        if diff_pct > tolerance_pct:
            result.add_warning(
                f"HP/Torque relationship questionable: {hp:.1f} HP vs "
                f"{calculated_hp:.1f} HP calculated from {torque:.1f} lb-ft @ {rpm_at_peak_torque} RPM "
                f"(difference: {diff_pct:.1f}%)"
            )

        # V-twins should have torque >= HP (typically)
        if torque < hp * 0.85:
            result.add_warning(
                f"Low torque for V-twin: {torque:.1f} lb-ft vs {hp:.1f} HP. "
                "V-twins typically have torque ≥ HP"
            )

        return result

    @staticmethod
    def validate_hp_per_ci(hp: float, displacement_ci: int) -> ValidationResult:
        """Validate HP/CI ratio is realistic."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])

        if displacement_ci <= 0:
            result.add_error("Displacement must be positive")
            return result

        hp_per_ci = hp / displacement_ci

        if hp_per_ci < PhysicsValidator.HP_PER_CI_MIN:
            result.add_error(
                f"Unrealistically low HP/CI: {hp_per_ci:.2f} "
                f"({hp:.1f} HP / {displacement_ci} CI). "
                f"Minimum expected: {PhysicsValidator.HP_PER_CI_MIN}"
            )

        if hp_per_ci > PhysicsValidator.HP_PER_CI_MAX:
            result.add_error(
                f"Unrealistically high HP/CI: {hp_per_ci:.2f} "
                f"({hp:.1f} HP / {displacement_ci} CI). "
                f"Maximum realistic: {PhysicsValidator.HP_PER_CI_MAX} (race builds)"
            )

        # Warn if outside typical range
        typical_min, typical_max = PhysicsValidator.HP_PER_CI_TYPICAL
        if hp_per_ci < typical_min or hp_per_ci > typical_max:
            result.add_warning(
                f"HP/CI outside typical range: {hp_per_ci:.2f} "
                f"(typical street builds: {typical_min}-{typical_max} HP/CI)"
            )

        return result

    @staticmethod
    def validate_compression_ratio(cr: float) -> ValidationResult:
        """Validate compression ratio is realistic."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])

        if cr < PhysicsValidator.COMPRESSION_RATIO_MIN:
            result.add_error(
                f"Unrealistically low compression ratio: {cr:.1f}:1 "
                f"(minimum: {PhysicsValidator.COMPRESSION_RATIO_MIN}:1)"
            )

        if cr > PhysicsValidator.COMPRESSION_RATIO_MAX:
            result.add_error(
                f"Unrealistically high compression ratio: {cr:.1f}:1 "
                f"(maximum for pump gas: {PhysicsValidator.COMPRESSION_RATIO_MAX}:1)"
            )

        # Warn if outside typical range
        typical_min, typical_max = PhysicsValidator.COMPRESSION_RATIO_TYPICAL
        if cr < typical_min or cr > typical_max:
            result.add_warning(
                f"Compression ratio outside typical range: {cr:.1f}:1 "
                f"(typical: {typical_min}-{typical_max}:1)"
            )

        return result

    @staticmethod
    def validate_cam_specs(config: BuildConfiguration) -> ValidationResult:
        """Validate cam specifications are realistic."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])

        cam = config.cam_spec

        # Check overlap
        avg_overlap = (cam.overlap_deg_front + cam.overlap_deg_rear) / 2

        if avg_overlap > PhysicsValidator.CAM_OVERLAP_MAX:
            result.add_error(
                f"Unrealistic cam overlap: {avg_overlap:.1f}° average "
                f"(maximum practical: {PhysicsValidator.CAM_OVERLAP_MAX}°)"
            )

        if avg_overlap < 0:
            result.add_error("Cam overlap cannot be negative")

        # Check duration
        for duration, name in [
            (cam.intake_duration_deg, "intake"),
            (cam.exhaust_duration_deg, "exhaust"),
        ]:
            if duration < PhysicsValidator.CAM_DURATION_MIN:
                result.add_error(
                    f"Unrealistic {name} duration: {duration}° "
                    f"(minimum: {PhysicsValidator.CAM_DURATION_MIN}°)"
                )

            if duration > PhysicsValidator.CAM_DURATION_MAX:
                result.add_error(
                    f"Unrealistic {name} duration: {duration}° "
                    f"(maximum: {PhysicsValidator.CAM_DURATION_MAX}°)"
                )

        # Check lift
        if cam.intake_lift_in < 0.3 or cam.intake_lift_in > 0.7:
            result.add_warning(
                f'Unusual intake lift: {cam.intake_lift_in}" (typical range: 0.4-0.6")'
            )

        if cam.exhaust_lift_in < 0.3 or cam.exhaust_lift_in > 0.7:
            result.add_warning(
                f'Unusual exhaust lift: {cam.exhaust_lift_in}" '
                '(typical range: 0.4-0.6")'
            )

        return result

    @staticmethod
    def validate_ve_tables(
        initial: List[List[float]], final: List[List[float]]
    ) -> ValidationResult:
        """Validate VE table values and changes are realistic."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])

        if len(initial) != len(final) or len(initial[0]) != len(final[0]):
            result.add_error("Initial and final VE tables have different dimensions")
            return result

        extreme_changes = []
        unrealistic_values = []

        for r in range(len(initial)):
            for k in range(len(initial[0])):
                initial_val = initial[r][k]
                final_val = final[r][k]

                # Skip empty cells
                if initial_val == 0 or final_val == 0:
                    continue

                # Check final value is realistic
                if (
                    final_val < PhysicsValidator.VE_VALUE_MIN
                    or final_val > PhysicsValidator.VE_VALUE_MAX
                ):
                    unrealistic_values.append(f"Cell [{r}][{k}]: {final_val:.1f}%")

                # Check change is realistic
                change_pct = abs((final_val - initial_val) / initial_val * 100)
                if change_pct > PhysicsValidator.VE_CHANGE_MAX:
                    extreme_changes.append(
                        f"Cell [{r}][{k}]: {change_pct:.1f}% change "
                        f"({initial_val:.1f}% → {final_val:.1f}%)"
                    )

        if unrealistic_values:
            result.add_error(
                f"Unrealistic VE values (outside {PhysicsValidator.VE_VALUE_MIN}-"
                f"{PhysicsValidator.VE_VALUE_MAX}%): "
                + ", ".join(unrealistic_values[:5])  # Show first 5
            )

        if extreme_changes:
            result.add_warning(
                f"Extreme VE changes (>{PhysicsValidator.VE_CHANGE_MAX}%) in single tune: "
                + ", ".join(extreme_changes[:5])
            )

        return result


class ConsistencyValidator:
    """Validates data consistency and logical relationships."""

    @staticmethod
    def validate_stage_consistency(config: BuildConfiguration) -> ValidationResult:
        """Validate stage level matches modifications."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])

        # Stock should have stock cam
        if config.stage == StageLevel.STOCK:
            if config.cam_spec.profile != CamProfile.STOCK:
                result.add_error(
                    f"Stage STOCK specified but has {config.cam_spec.profile.value} cam"
                )

        # Stage 1 shouldn't have aftermarket cam
        if config.stage == StageLevel.STAGE_1:
            if config.cam_spec.profile not in [CamProfile.STOCK, CamProfile.CUSTOM]:
                result.add_warning(
                    f"Stage 1 typically has stock cam, but {config.cam_spec.profile.value} specified"
                )

        # Stage 2+ should have aftermarket cam
        if config.stage in [StageLevel.STAGE_2, StageLevel.STAGE_3, StageLevel.STAGE_4]:
            if config.cam_spec.profile == CamProfile.STOCK:
                result.add_warning(
                    f"{config.stage.value} typically has aftermarket cam, but stock cam specified"
                )

        return result

    @staticmethod
    def validate_afr_accuracy(
        afr_error: float, cylinder_delta: float
    ) -> ValidationResult:
        """Validate AFR tuning quality metrics."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])

        if afr_error > PhysicsValidator.AFR_ERROR_MAX:
            result.add_error(
                f"Poor AFR accuracy: {afr_error:.2f} RMS error "
                f"(should be < {PhysicsValidator.AFR_ERROR_MAX})"
            )
        elif afr_error > PhysicsValidator.AFR_ERROR_GOOD:
            result.add_warning(
                f"Mediocre AFR accuracy: {afr_error:.2f} RMS error "
                f"(good tunes: < {PhysicsValidator.AFR_ERROR_GOOD})"
            )

        if cylinder_delta > PhysicsValidator.CYLINDER_IMBALANCE_MAX:
            result.add_error(
                f"Extreme cylinder imbalance: {cylinder_delta:.2f} AFR points "
                f"(maximum typical: {PhysicsValidator.CYLINDER_IMBALANCE_MAX})"
            )
        elif cylinder_delta < PhysicsValidator.CYLINDER_IMBALANCE_TYPICAL[0]:
            result.add_warning(
                f"Unusually low cylinder imbalance: {cylinder_delta:.2f} AFR points "
                f"(may indicate single-cylinder tuning or averaged data)"
            )

        return result


class DataValidator:
    """Main validator orchestrating all validation checks."""

    def __init__(self):
        self.physics = PhysicsValidator()
        self.consistency = ConsistencyValidator()

    def validate_session(self, session: TuningSession) -> ValidationResult:
        """Validate complete tuning session."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])

        # Validate build configuration
        build_results = self.validate_build_config(session.build_config)
        result.errors.extend(build_results.errors)
        result.warnings.extend(build_results.warnings)
        if not build_results.is_valid:
            result.is_valid = False

        # Validate dyno results
        results_validation = self.validate_dyno_results(session)
        result.errors.extend(results_validation.errors)
        result.warnings.extend(results_validation.warnings)
        if not results_validation.is_valid:
            result.is_valid = False

        # Validate VE tables if present
        if session.initial_ve_table_front and session.final_ve_table_front:
            ve_validation = self.physics.validate_ve_tables(
                session.initial_ve_table_front, session.final_ve_table_front
            )
            result.errors.extend(ve_validation.errors)
            result.warnings.extend(ve_validation.warnings)
            if not ve_validation.is_valid:
                result.is_valid = False

        return result

    def validate_build_config(self, config: BuildConfiguration) -> ValidationResult:
        """Validate build configuration."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])

        # Check displacement matches bore/stroke
        disp_result = self.physics.validate_displacement(config)
        result.errors.extend(disp_result.errors)
        result.warnings.extend(disp_result.warnings)
        if not disp_result.is_valid:
            result.is_valid = False

        # Check compression ratio
        cr_result = self.physics.validate_compression_ratio(config.compression_ratio)
        result.errors.extend(cr_result.errors)
        result.warnings.extend(cr_result.warnings)
        if not cr_result.is_valid:
            result.is_valid = False

        # Check cam specs
        cam_result = self.physics.validate_cam_specs(config)
        result.errors.extend(cam_result.errors)
        result.warnings.extend(cam_result.warnings)
        if not cam_result.is_valid:
            result.is_valid = False

        # Check stage consistency
        stage_result = self.consistency.validate_stage_consistency(config)
        result.errors.extend(stage_result.errors)
        result.warnings.extend(stage_result.warnings)
        if not stage_result.is_valid:
            result.is_valid = False

        return result

    def validate_dyno_results(self, session: TuningSession) -> ValidationResult:
        """Validate dyno results."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])

        # Check HP/Torque relationship
        hp_torque_result = self.physics.validate_hp_torque_relationship(
            session.peak_hp, session.peak_torque
        )
        result.errors.extend(hp_torque_result.errors)
        result.warnings.extend(hp_torque_result.warnings)
        if not hp_torque_result.is_valid:
            result.is_valid = False

        # Check HP/CI ratio
        hp_ci_result = self.physics.validate_hp_per_ci(
            session.peak_hp, session.build_config.displacement_ci
        )
        result.errors.extend(hp_ci_result.errors)
        result.warnings.extend(hp_ci_result.warnings)
        if not hp_ci_result.is_valid:
            result.is_valid = False

        # Check AFR accuracy
        afr_result = self.consistency.validate_afr_accuracy(
            session.afr_accuracy_rms_error, session.max_cylinder_afr_delta
        )
        result.errors.extend(afr_result.errors)
        result.warnings.extend(afr_result.warnings)
        if not afr_result.is_valid:
            result.is_valid = False

        return result


__all__ = [
    "ValidationResult",
    "PhysicsValidator",
    "ConsistencyValidator",
    "DataValidator",
]
