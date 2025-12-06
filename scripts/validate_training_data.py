#!/usr/bin/env python3
"""
Validate and analyze DynoAI training data.

This script validates training data JSON files for completeness,
calculates summary statistics, and identifies data quality issues.

Security Note:
    This is a CLI utility that intentionally reads user-specified files.
    Path traversal is expected behavior. The script validates:
    - File exists (resolve with strict=True)
    - File is .json extension
    - File is readable JSON
    
    Do not expose this script to untrusted input or web interfaces.

Usage:
    python scripts/validate_training_data.py docs/examples/training_data_example.json
    python scripts/validate_training_data.py training_data/*.json --verbose
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.models.validators import DataValidator, ValidationResult
from api.models.training_data_schemas import TuningSession, BuildConfiguration


class TrainingDataValidator:
    """Validates training data structure and content."""
    
    def __init__(self, verbose: bool = False, enable_physics: bool = True):
        self.verbose = verbose
        self.enable_physics = enable_physics
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.data_validator = DataValidator() if enable_physics else None
    
    def validate_file(self, file_path: Path) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate a training data JSON file.
        
        Returns:
            (is_valid, stats_dict)
        """
        self.errors = []
        self.warnings = []
        
        # Resolve to absolute path and validate
        try:
            file_path = file_path.resolve(strict=True)
        except (OSError, RuntimeError) as e:
            self.errors.append(f"Invalid file path: {e}")
            return False, {}
        
        # Ensure it's a .json file
        if file_path.suffix.lower() != '.json':
            self.errors.append(f"Not a JSON file: {file_path}")
            return False, {}
        
        # Read file safely
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            self.errors.append(f"Invalid JSON: {e}")
            return False, {}
        except (OSError, PermissionError) as e:
            self.errors.append(f"Cannot read file: {e}")
            return False, {}
        
        # Validate structure
        self._validate_structure(data)
        
        # Validate sessions
        if "tuning_sessions" in data:
            for idx, session in enumerate(data["tuning_sessions"]):
                self._validate_session(session, idx)
                
                # Physics validation if enabled
                if self.enable_physics and self.data_validator:
                    self._validate_session_physics(session, idx)
        
        # Calculate statistics
        stats = self._calculate_stats(data)
        
        is_valid = len(self.errors) == 0
        return is_valid, stats
    
    def _validate_structure(self, data: Dict[str, Any]) -> None:
        """Validate top-level structure."""
        required_fields = ["dataset_id", "version", "created_at"]
        for field in required_fields:
            if field not in data:
                self.errors.append(f"Missing required field: {field}")
        
        if "tuning_sessions" not in data:
            self.warnings.append("No tuning_sessions found")
        
        if "extracted_patterns" not in data and "tuning_sessions" in data:
            if len(data["tuning_sessions"]) > 0:
                self.warnings.append("No extracted_patterns - run pattern extraction")
    
    def _validate_session(self, session: Dict[str, Any], idx: int) -> None:
        """Validate individual tuning session."""
        prefix = f"Session {idx}"
        
        # Required fields
        required = ["session_id", "timestamp_utc", "objective", "build_config"]
        for field in required:
            if field not in session:
                self.errors.append(f"{prefix}: Missing {field}")
        
        # Build config validation
        if "build_config" in session:
            build = session["build_config"]
            build_required = ["engine_family", "displacement_ci", "stage", "cam_spec"]
            for field in build_required:
                if field not in build:
                    self.errors.append(f"{prefix}: build_config missing {field}")
            
            # Cam spec validation
            if "cam_spec" in build:
                cam = build["cam_spec"]
                cam_required = ["profile", "overlap_deg_front", "overlap_deg_rear"]
                for field in cam_required:
                    if field not in cam:
                        self.warnings.append(f"{prefix}: cam_spec missing {field}")
        
        # Results validation
        if "results" not in session:
            self.warnings.append(f"{prefix}: No results data")
        else:
            results = session["results"]
            if "peak_hp" not in results or results.get("peak_hp", 0) == 0:
                self.warnings.append(f"{prefix}: Missing or zero peak_hp")
            if "duration_hours" not in results or results.get("duration_hours", 0) == 0:
                self.warnings.append(f"{prefix}: Missing tuning duration")
        
        # AFR targets validation
        if "afr_targets" not in session or not session["afr_targets"]:
            self.warnings.append(f"{prefix}: No AFR targets specified")
    
    def _validate_session_physics(self, session: Dict[str, Any], idx: int) -> None:
        """Validate session against physical constraints."""
        prefix = f"Session {idx}"
        
        try:
            # Extract build config
            if "build_config" not in session:
                return
            
            build_data = session["build_config"]
            
            # Validate displacement = bore × stroke
            if all(k in build_data for k in ["bore_in", "stroke_in", "displacement_ci"]):
                import math
                calculated_ci = (
                    (build_data["bore_in"] ** 2) * math.pi * 
                    build_data["stroke_in"] * 2 / 4
                )
                diff = abs(build_data["displacement_ci"] - calculated_ci)
                if diff > 5.0:
                    self.errors.append(
                        f"{prefix}: Displacement mismatch - {build_data['displacement_ci']} CI "
                        f"doesn't match bore {build_data['bore_in']}\" × stroke {build_data['stroke_in']}\" "
                        f"(calculated: {calculated_ci:.1f} CI, diff: {diff:.1f} CI)"
                    )
            
            # Validate HP/CI ratio
            if "results" in session:
                results = session["results"]
                if "peak_hp" in results and "displacement_ci" in build_data:
                    hp_per_ci = results["peak_hp"] / build_data["displacement_ci"]
                    if hp_per_ci < 0.5 or hp_per_ci > 1.3:
                        self.warnings.append(
                            f"{prefix}: Unusual HP/CI ratio - {hp_per_ci:.2f} "
                            f"({results['peak_hp']} HP / {build_data['displacement_ci']} CI). "
                            "Typical range: 0.7-1.0 HP/CI"
                        )
                
                # Validate torque > HP for V-twins
                if "peak_hp" in results and "peak_torque" in results:
                    if results["peak_torque"] < results["peak_hp"] * 0.85:
                        self.warnings.append(
                            f"{prefix}: Low torque for V-twin - {results['peak_torque']} lb-ft "
                            f"vs {results['peak_hp']} HP. V-twins typically have torque ≥ HP"
                        )
                
                # Validate AFR accuracy
                if "afr_accuracy_rms_error" in results:
                    afr_error = results["afr_accuracy_rms_error"]
                    if afr_error > 1.0:
                        self.errors.append(
                            f"{prefix}: Poor AFR accuracy - {afr_error:.2f} RMS error (should be < 1.0)"
                        )
                    elif afr_error > 0.3:
                        self.warnings.append(
                            f"{prefix}: Mediocre AFR accuracy - {afr_error:.2f} RMS error "
                            "(good tunes: < 0.3)"
                        )
                
                # Validate cylinder imbalance
                if "max_cylinder_afr_delta" in results:
                    cyl_delta = results["max_cylinder_afr_delta"]
                    if cyl_delta > 2.0:
                        self.errors.append(
                            f"{prefix}: Extreme cylinder imbalance - {cyl_delta:.2f} AFR points "
                            "(typical maximum: 2.0)"
                        )
                    elif cyl_delta < 0.3:
                        self.warnings.append(
                            f"{prefix}: Unusually low cylinder imbalance - {cyl_delta:.2f} AFR points "
                            "(may indicate single-cylinder tuning or averaged data)"
                        )
            
            # Validate compression ratio
            if "compression_ratio" in build_data:
                cr = build_data["compression_ratio"]
                if cr < 8.0 or cr > 14.0:
                    self.errors.append(
                        f"{prefix}: Unrealistic compression ratio - {cr:.1f}:1 "
                        "(typical range: 9.0-11.5:1 for pump gas)"
                    )
            
            # Validate cam overlap
            if "cam_spec" in build_data:
                cam = build_data["cam_spec"]
                if "overlap_deg_front" in cam and "overlap_deg_rear" in cam:
                    avg_overlap = (cam["overlap_deg_front"] + cam["overlap_deg_rear"]) / 2
                    if avg_overlap > 70.0:
                        self.errors.append(
                            f"{prefix}: Unrealistic cam overlap - {avg_overlap:.1f}° average "
                            "(maximum practical: 70°)"
                        )
                    elif avg_overlap < 0:
                        self.errors.append(f"{prefix}: Cam overlap cannot be negative")
        
        except Exception as e:
            if self.verbose:
                self.warnings.append(f"{prefix}: Physics validation error - {str(e)}")
    
    def _calculate_stats(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate statistics for the dataset."""
        stats = {
            "total_sessions": 0,
            "objectives": {},
            "engine_families": {},
            "stages": {},
            "cam_profiles": {},
            "total_dyno_hours": 0.0,
            "avg_hp": 0.0,
            "avg_duration_hours": 0.0,
            "pattern_counts": {},
        }
        
        if "tuning_sessions" not in data:
            return stats
        
        sessions = data["tuning_sessions"]
        stats["total_sessions"] = len(sessions)
        
        hp_values = []
        duration_values = []
        
        for session in sessions:
            # Objective
            obj = session.get("objective", "unknown")
            stats["objectives"][obj] = stats["objectives"].get(obj, 0) + 1
            
            # Build config
            if "build_config" in session:
                build = session["build_config"]
                
                engine = build.get("engine_family", "unknown")
                stats["engine_families"][engine] = stats["engine_families"].get(engine, 0) + 1
                
                stage = build.get("stage", "unknown")
                stats["stages"][stage] = stats["stages"].get(stage, 0) + 1
                
                if "cam_spec" in build:
                    cam = build["cam_spec"].get("profile", "unknown")
                    stats["cam_profiles"][cam] = stats["cam_profiles"].get(cam, 0) + 1
            
            # Results
            if "results" in session:
                results = session["results"]
                
                if "peak_hp" in results and results["peak_hp"] > 0:
                    hp_values.append(results["peak_hp"])
                
                if "duration_hours" in results and results["duration_hours"] > 0:
                    duration_values.append(results["duration_hours"])
                    stats["total_dyno_hours"] += results["duration_hours"]
        
        if hp_values:
            stats["avg_hp"] = sum(hp_values) / len(hp_values)
        
        if duration_values:
            stats["avg_duration_hours"] = sum(duration_values) / len(duration_values)
        
        # Pattern counts
        if "extracted_patterns" in data:
            patterns = data["extracted_patterns"]
            for pattern_type, pattern_list in patterns.items():
                if isinstance(pattern_list, list):
                    stats["pattern_counts"][pattern_type] = len(pattern_list)
        
        return stats
    
    def print_report(self, file_path: Path, is_valid: bool, stats: Dict[str, Any]) -> None:
        """Print validation report."""
        print(f"\n{'='*70}")
        print(f"Validation Report: {file_path.name}")
        print(f"{'='*70}")
        
        # Status
        if is_valid:
            print("✅ Status: VALID")
        else:
            print("❌ Status: INVALID")
        
        # Errors
        if self.errors:
            print(f"\n🚨 Errors ({len(self.errors)}):")
            for error in self.errors:
                print(f"  - {error}")
        
        # Warnings
        if self.warnings:
            print(f"\n⚠️  Warnings ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  - {warning}")
        
        # Statistics
        if stats:
            print(f"\n📊 Statistics:")
            print(f"  Total Sessions: {stats['total_sessions']}")
            print(f"  Total Dyno Hours: {stats['total_dyno_hours']:.1f}")
            print(f"  Avg HP: {stats['avg_hp']:.1f}")
            print(f"  Avg Duration: {stats['avg_duration_hours']:.1f} hours")
            
            if stats['objectives']:
                print(f"\n  Objectives:")
                for obj, count in stats['objectives'].items():
                    print(f"    - {obj}: {count}")
            
            if stats['engine_families']:
                print(f"\n  Engine Families:")
                for family, count in stats['engine_families'].items():
                    print(f"    - {family}: {count}")
            
            if stats['stages']:
                print(f"\n  Stages:")
                for stage, count in stats['stages'].items():
                    print(f"    - {stage}: {count}")
            
            if stats['cam_profiles']:
                print(f"\n  Cam Profiles:")
                for cam, count in stats['cam_profiles'].items():
                    print(f"    - {cam}: {count}")
            
            if stats['pattern_counts']:
                print(f"\n  Extracted Patterns:")
                for pattern_type, count in stats['pattern_counts'].items():
                    print(f"    - {pattern_type}: {count}")
        
        print(f"{'='*70}\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate DynoAI training data files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/validate_training_data.py docs/examples/training_data_example.json
  python scripts/validate_training_data.py training_data/*.json
  python scripts/validate_training_data.py data.json --verbose
        """
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="Training data JSON file(s) to validate"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--no-physics",
        action="store_true",
        help="Disable physics-based validation checks"
    )
    
    args = parser.parse_args()
    
    validator = TrainingDataValidator(
        verbose=args.verbose,
        enable_physics=not args.no_physics
    )
    
    all_valid = True
    total_sessions = 0
    total_hours = 0.0
    
    for file_path_str in args.files:
        file_path = Path(file_path_str)
        is_valid, stats = validator.validate_file(file_path)
        validator.print_report(file_path, is_valid, stats)
        
        if not is_valid:
            all_valid = False
        
        total_sessions += stats.get("total_sessions", 0)
        total_hours += stats.get("total_dyno_hours", 0.0)
    
    # Summary if multiple files
    if len(args.files) > 1:
        print(f"\n{'='*70}")
        print("Overall Summary")
        print(f"{'='*70}")
        print(f"Files Processed: {len(args.files)}")
        print(f"Total Sessions: {total_sessions}")
        print(f"Total Dyno Hours: {total_hours:.1f}")
        print(f"Status: {'✅ All Valid' if all_valid else '❌ Some Invalid'}")
        print(f"{'='*70}\n")
    
    # Exit code
    sys.exit(0 if all_valid else 1)


if __name__ == "__main__":
    main()

