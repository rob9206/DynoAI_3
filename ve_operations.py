"""
VE Correction Apply/Rollback System

This module provides safe application and rollback of VE correction factors.
All operations are designed to be predictable, capped, reversible, and audit-friendly.
"""

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional, Tuple

import io_contracts
from io_contracts import sanitize_csv_cell

# Version of the VE operations module
APP_VERSION = "1.0.0"

# Default maximum adjustment percentage (±7%)
DEFAULT_MAX_ADJUST_PCT = 7.0


def compute_sha256(file_path: Path) -> str:
    """
    Compute SHA-256 hash of a file.

    Args:
        file_path: Path to the file to hash

    Returns:
        Hexadecimal string representation of the SHA-256 hash

    Raises:
        FileNotFoundError: If the file does not exist
    """
    sha256_hash = hashlib.sha256()
    # Re-sanitize path defensively (caller already should have, but double-check helps static analysis & safety)
    safe_path = io_contracts.safe_path(str(file_path), allow_parent_dir=True)
    with open(safe_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def read_ve_table(csv_path: Path) -> Tuple[List[int], List[int], List[List[float]]]:
    """
    Read a VE table from CSV format.

    Expected format:
    - First row: RPM, followed by MAP/kPa bin values
    - Subsequent rows: RPM value, followed by VE values for each kPa bin

    Args:
        csv_path: Path to the CSV file containing the VE table

    Returns:
        Tuple of (rpm_bins, kpa_bins, ve_grid) where:
        - rpm_bins: List of RPM values
        - kpa_bins: List of kPa values
        - ve_grid: 2D list of VE values (rows=RPM, cols=kPa)

    Raises:
        RuntimeError: If the CSV format is invalid
        FileNotFoundError: If the file does not exist
    """
    safe_csv = io_contracts.safe_path(str(csv_path), allow_parent_dir=True)
    with open(safe_csv, newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        raise RuntimeError(f"{csv_path} is empty")

    # Parse header row
    header = [h.strip() for h in rows[0]]
    if len(header) < 2 or header[0].upper() != "RPM":
        raise RuntimeError(f"{csv_path} missing RPM header")

    kpa_bins = [int(float(x)) for x in header[1:]]

    # Parse data rows
    rpm_bins: List[int] = []
    ve_grid: List[List[float]] = []

    for row in rows[1:]:
        if not row or not row[0].strip():
            continue

        rpm = int(float(row[0]))
        rpm_bins.append(rpm)

        ve_row: List[float] = []
        for j in range(1, len(kpa_bins) + 1):
            if j < len(row) and row[j].strip():
                # Strip leading quote added by sanitize_csv_cell for CSV safety
                cell_value = row[j].strip()
                if cell_value.startswith("'"):
                    cell_value = cell_value[1:]
                ve_row.append(float(cell_value))
            else:
                ve_row.append(0.0)
        ve_grid.append(ve_row)

    return rpm_bins, kpa_bins, ve_grid


def write_ve_table(
    csv_path: Path,
    rpm_bins: List[int],
    kpa_bins: List[int],
    ve_grid: List[List[float]],
    precision: int = 4,
):
    """
    Write a VE table to CSV format with specified precision.

    Args:
        csv_path: Path to write the CSV file
        rpm_bins: List of RPM values
        kpa_bins: List of kPa values
        ve_grid: 2D list of VE values (rows=RPM, cols=kPa)
        precision: Number of decimal places for VE values (default: 4)
    """
    safe_out = io_contracts.safe_path(str(csv_path), allow_parent_dir=True)
    with open(safe_out, "w", newline="") as f:
        writer = csv.writer(f)

        # Write header
        writer.writerow(["RPM"] + [sanitize_csv_cell(k) for k in kpa_bins])

        # Write data rows
        for rpm, ve_row in zip(rpm_bins, ve_grid):
            row_data: List[Any] = [sanitize_csv_cell(rpm)]
            for ve_val in ve_row:
                formatted_val = f"{ve_val:.{precision}f}"
                row_data.append(sanitize_csv_cell(formatted_val))
            writer.writerow(row_data)


def clamp_factor_grid(
    factor_grid: List[List[float]], max_adjust_pct: float
) -> List[List[float]]:
    """
    Clamp correction factors to stay within maximum adjustment percentage.

    A factor represents a percentage change. For example:
    - 5.0 means +5% (multiply by 1.05)
    - -3.0 means -3% (multiply by 0.97)

    This function ensures no factor exceeds ±max_adjust_pct.

    Args:
        factor_grid: 2D list of correction factors (as percentages)
        max_adjust_pct: Maximum allowed adjustment percentage (e.g., 7.0 for ±7%)

    Returns:
        Clamped 2D list of factors where all values are in [-max_adjust_pct, +max_adjust_pct]

    Constraints:
        - With max_adjust_pct=7, factors are clamped to [-7, +7]
        - This translates to multipliers in range [0.93, 1.07]
    """
    clamped: List[List[float]] = []
    for row in factor_grid:
        clamped_row: List[float] = []
        for factor in row:
            if factor > max_adjust_pct:
                clamped_row.append(max_adjust_pct)
            elif factor < -max_adjust_pct:
                clamped_row.append(-max_adjust_pct)
            else:
                clamped_row.append(factor)
        clamped.append(clamped_row)
    return clamped


def analyze_cylinder_delta(front_ve_path: Path, rear_ve_path: Path) -> dict[str, Any]:
    """
    Calculate the delta between Front and Rear VE tables.

    Args:
        front_ve_path: Path to Front cylinder VE table
        rear_ve_path: Path to Rear cylinder VE table

    Returns:
        Dictionary containing:
        - delta_grid: 2D list of (Rear - Front) values
        - max_delta: Maximum absolute difference
        - avg_delta: Average absolute difference
        - rpm_bins: RPM values
        - kpa_bins: kPa values

    Raises:
        RuntimeError: If table dimensions don't match
    """
    f_rpm, f_kpa, f_ve = read_ve_table(front_ve_path)
    r_rpm, r_kpa, r_ve = read_ve_table(rear_ve_path)

    if f_rpm != r_rpm or f_kpa != r_kpa:
        raise RuntimeError("Front and Rear tables must have identical dimensions")

    delta_grid: List[List[float]] = []
    max_delta = 0.0
    total_delta = 0.0
    count = 0

    for f_row, r_row in zip(f_ve, r_ve):
        delta_row: List[float] = []
        for f_val, r_val in zip(f_row, r_row):
            delta = r_val - f_val
            delta_row.append(delta)
            abs_delta = abs(delta)
            if abs_delta > max_delta:
                max_delta = abs_delta
            total_delta += abs_delta
            count += 1
        delta_grid.append(delta_row)

    return {
        "delta_grid": delta_grid,
        "max_delta": max_delta,
        "avg_delta": total_delta / count if count > 0 else 0.0,
        "rpm_bins": f_rpm,
        "kpa_bins": f_kpa,
    }


class DualCylinderVEApply:
    """
    Coordinator for applying VE corrections to both cylinders simultaneously.
    Ensures atomic-like operations where both succeed or neither is written.
    """

    def __init__(self, max_adjust_pct: float = DEFAULT_MAX_ADJUST_PCT):
        self.applier = VEApply(max_adjust_pct)

    def apply(
        self,
        front_base: Path,
        rear_base: Path,
        front_factor: Path,
        rear_factor: Path,
        front_output: Path,
        rear_output: Path,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """
        Apply corrections to both cylinders.

        Returns:
            Dictionary with metadata for both operations
        """
        # 1. Validate all inputs first (fail early)
        # We just read them to ensure they exist and are valid CSVs
        read_ve_table(front_base)
        read_ve_table(rear_base)
        read_ve_table(front_factor)
        read_ve_table(rear_factor)

        # 2. Run applies
        # Note: In a real DB this would be a transaction. Here we rely on
        # file system operations. If one fails, the other might remain.
        # A true atomic file write is complex, so we do best-effort with pre-checks.

        front_meta = self.applier.apply(
            base_ve_path=front_base,
            factor_path=front_factor,
            output_path=front_output,
            dry_run=dry_run,
        )

        rear_meta = self.applier.apply(
            base_ve_path=rear_base,
            factor_path=rear_factor,
            output_path=rear_output,
            dry_run=dry_run,
        )

        return {
            "operation": "apply_dual",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "front": front_meta,
            "rear": rear_meta,
        }


class VEApply:
    """
    Apply VE correction factors to a base VE table.

    This class handles:
    - Clamping factors to maximum adjustment percentage
    - Multiplying base VE by correction factors
    - Writing updated VE table with 4-decimal precision
    - Generating metadata for audit trail and rollback
    """

    def __init__(self, max_adjust_pct: float = DEFAULT_MAX_ADJUST_PCT):
        """
        Initialize the VE Apply operation.

        Args:
            max_adjust_pct: Maximum adjustment percentage (default: 7.0 for ±7%)
        """
        self.max_adjust_pct = max_adjust_pct

    def apply(
        self,
        base_ve_path: Path,
        factor_path: Path,
        output_path: Path,
        metadata_path: Optional[Path] = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """
        Apply correction factors to base VE table.

        Process:
        1. Read base VE table
        2. Read correction factor table (as percentages)
        3. Clamp factors to ±max_adjust_pct
        4. Multiply: updated_ve = base_ve × (1 + factor/100)
        5. Write updated VE table with 4-decimal precision
        6. Generate metadata JSON with hashes and timestamp

        Args:
            base_ve_path: Path to base VE CSV file
            factor_path: Path to correction factor CSV file (percentage values)
            output_path: Path to write updated VE CSV file
            metadata_path: Path to write metadata JSON (default: same dir as output with _meta.json)
            dry_run: If True, preview outputs without writing files

        Returns:
            Dictionary containing metadata about the operation

        Raises:
            RuntimeError: If table dimensions don't match or files are invalid
        """
        # Read base VE table
        rpm_bins, kpa_bins, base_ve = read_ve_table(base_ve_path)

        # Read factor table (as percentages)
        factor_rpm, factor_kpa, factor_grid = read_ve_table(factor_path)

        # Verify dimensions match
        if rpm_bins != factor_rpm or kpa_bins != factor_kpa:
            raise RuntimeError(
                f"Table dimension mismatch: base has {len(rpm_bins)}x{len(kpa_bins)} bins, "
                f"factor has {len(factor_rpm)}x{len(factor_kpa)} bins"
            )

        # Clamp factors to maximum adjustment
        clamped_factors = clamp_factor_grid(factor_grid, self.max_adjust_pct)

        # Apply factors: updated_ve = base_ve * (1 + factor/100)
        updated_ve: List[List[float]] = []
        for base_row, factor_row in zip(base_ve, clamped_factors):
            updated_row: List[float] = []
            for base_val, factor_val in zip(base_row, factor_row):
                # Convert percentage to multiplier: 5% -> 1.05, -3% -> 0.97
                multiplier = 1.0 + (factor_val / 100.0)
                updated_row.append(base_val * multiplier)
            updated_ve.append(updated_row)

        # Compute hashes
        base_sha = compute_sha256(base_ve_path)
        factor_sha = compute_sha256(factor_path)

        # Create metadata
        metadata: dict[str, Any] = {
            "operation": "apply",
            "base_sha": base_sha,
            "factor_sha": factor_sha,
            "applied_at_utc": datetime.now(timezone.utc).isoformat(),
            "max_adjust_pct": self.max_adjust_pct,
            "app_version": APP_VERSION,
            "base_file": str(base_ve_path),
            "factor_file": str(factor_path),
            "output_file": str(output_path),
            "comment": "Rollback = divide by last factor (or multiply by reciprocal of applied multipliers)",
        }

        if dry_run:
            print("DRY RUN - Preview of operation:")
            print(f"  Base VE: {base_ve_path}")
            print(f"  Factor file: {factor_path}")
            print(f"  Output: {output_path}")
            print(f"  Max adjustment: ±{self.max_adjust_pct}%")
            print(
                f"  Table dimensions: {len(rpm_bins)} RPM bins × {len(kpa_bins)} kPa bins"
            )
            print("\nMetadata that would be written:")
            print(json.dumps(metadata, indent=2))
            print("\nNo files were written (dry-run mode)")
        else:
            # Write updated VE table
            write_ve_table(output_path, rpm_bins, kpa_bins, updated_ve, precision=4)

            # Write metadata
            if metadata_path is None:
                metadata_path = output_path.parent / (output_path.stem + "_meta.json")

            safe_meta = io_contracts.safe_path(
                str(metadata_path), allow_parent_dir=True
            )
            with open(safe_meta, "w") as f:
                json.dump(metadata, f, indent=2)

            print("[OK] Applied VE corrections:")
            print(f"  Output: {output_path}")
            print(f"  Metadata: {metadata_path}")

        # Return metadata whether dry-run or not
        return metadata


class VERollback:
    """
    Rollback a previously applied VE correction.

    This class handles:
    - Verifying metadata and file hashes
    - Reversing the correction by dividing by factors
    - Restoring the original VE table
    """

    def rollback(
        self,
        current_ve_path: Path,
        metadata_path: Path,
        output_path: Path,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """
        Rollback a VE correction using stored metadata.

        Process:
        1. Read metadata to get original base_sha and factor information
        2. Verify current VE file hasn't been tampered with (optional)
        3. Read current VE table
        4. Read factor table from metadata
        5. Divide: restored_ve = current_ve / (1 + factor/100)
        6. Write restored VE table

        Args:
            current_ve_path: Path to current (modified) VE CSV file
            metadata_path: Path to metadata JSON from apply operation
            output_path: Path to write restored VE CSV file
            dry_run: If True, preview outputs without writing files

        Returns:
            Dictionary containing information about the rollback

        Raises:
            RuntimeError: If metadata is invalid or hashes don't match
            FileNotFoundError: If required files don't exist
        """
        # Read metadata
        safe_meta = io_contracts.safe_path(str(metadata_path), allow_parent_dir=True)
        with open(safe_meta, "r") as f:
            metadata = json.load(f)

        # Verify this is apply metadata
        if metadata.get("operation") != "apply":
            raise RuntimeError(
                f"Metadata is not from an apply operation: {metadata.get('operation')}"
            )

        # Get factor file path from metadata
        factor_path = Path(metadata.get("factor_file"))
        if not factor_path.exists():
            raise RuntimeError(f"Factor file not found: {factor_path}")

        # Verify factor file hash
        factor_sha = compute_sha256(factor_path)
        if factor_sha != metadata.get("factor_sha"):
            raise RuntimeError(
                f"Factor file hash mismatch!\n"
                f"  Expected: {metadata.get('factor_sha')}\n"
                f"  Got: {factor_sha}\n"
                f"  Factor file may have been modified. Cannot safely rollback."
            )

        # Read current VE table
        rpm_bins, kpa_bins, current_ve = read_ve_table(current_ve_path)

        # Read factor table
        factor_rpm, factor_kpa, factor_grid = read_ve_table(factor_path)

        # Verify dimensions
        if rpm_bins != factor_rpm or kpa_bins != factor_kpa:
            raise RuntimeError(
                f"Table dimension mismatch during rollback: current has {len(rpm_bins)}x{len(kpa_bins)} bins, "
                f"factor has {len(factor_rpm)}x{len(factor_kpa)} bins"
            )

        # Clamp factors (same as during apply)
        max_adjust_pct = metadata.get("max_adjust_pct", DEFAULT_MAX_ADJUST_PCT)
        clamped_factors = clamp_factor_grid(factor_grid, max_adjust_pct)

        # Reverse the operation: restored_ve = current_ve / (1 + factor/100)
        restored_ve: List[List[float]] = []
        for current_row, factor_row in zip(current_ve, clamped_factors):
            restored_row: List[float] = []
            for current_val, factor_val in zip(current_row, factor_row):
                # Convert percentage to multiplier: 5% -> 1.05, -3% -> 0.97
                multiplier = 1.0 + (factor_val / 100.0)
                # Divide to reverse
                restored_row.append(current_val / multiplier)
            restored_ve.append(restored_row)

        rollback_info: dict[str, Any] = {
            "operation": "rollback",
            "rolled_back_at_utc": datetime.now(timezone.utc).isoformat(),
            "original_apply_metadata": metadata,
            "current_file": str(current_ve_path),
            "restored_file": str(output_path),
        }

        if dry_run:
            print("DRY RUN - Preview of rollback:")
            print(f"  Current VE: {current_ve_path}")
            print(f"  Metadata: {metadata_path}")
            print(f"  Output: {output_path}")
            print(f"  Original apply date: {metadata.get('applied_at_utc')}")
            print(f"  Max adjustment was: ±{max_adjust_pct}%")
            print("\nRollback info that would be generated:")
            print(json.dumps(rollback_info, indent=2))
            print("\nNo files were written (dry-run mode)")
        else:
            # Write restored VE table
            write_ve_table(output_path, rpm_bins, kpa_bins, restored_ve, precision=4)

            print("[OK] Rolled back VE corrections:")
            print(f"  Restored to: {output_path}")
            print(f"  Original apply: {metadata.get('applied_at_utc')}")

        # Return rollback info whether dry-run or not
        return rollback_info


def main():
    """Command-line interface for VE apply/rollback operations."""
    import argparse

    parser = argparse.ArgumentParser(
        description="VE Correction Apply/Rollback System - Safe, auditable VE table modifications"
    )

    subparsers = parser.add_subparsers(dest="command", help="Operation to perform")

    # Apply command
    apply_parser = subparsers.add_parser("apply", help="Apply VE corrections")
    apply_parser.add_argument("--base", required=True, help="Base VE table CSV file")
    apply_parser.add_argument(
        "--factor", required=True, help="Correction factor CSV file (percentages)"
    )
    apply_parser.add_argument(
        "--output", required=True, help="Output path for updated VE table"
    )
    apply_parser.add_argument(
        "--metadata", help="Metadata JSON output path (default: <output>_meta.json)"
    )
    apply_parser.add_argument(
        "--max-adjust",
        type=float,
        default=DEFAULT_MAX_ADJUST_PCT,
        help=f"Maximum adjustment percentage (default: ±{DEFAULT_MAX_ADJUST_PCT}%%)",
    )
    apply_parser.add_argument(
        "--dry-run", action="store_true", help="Preview operation without writing files"
    )

    # Rollback command
    rollback_parser = subparsers.add_parser("rollback", help="Rollback VE corrections")
    rollback_parser.add_argument(
        "--current", required=True, help="Current (modified) VE table CSV file"
    )
    rollback_parser.add_argument(
        "--metadata", required=True, help="Metadata JSON from apply operation"
    )
    rollback_parser.add_argument(
        "--output", required=True, help="Output path for restored VE table"
    )
    rollback_parser.add_argument(
        "--dry-run", action="store_true", help="Preview operation without writing files"
    )

    # Apply Dual command
    dual_parser = subparsers.add_parser(
        "apply-dual", help="Apply VE corrections to both cylinders"
    )
    dual_parser.add_argument(
        "--front-base", required=True, help="Front base VE table CSV"
    )
    dual_parser.add_argument(
        "--rear-base", required=True, help="Rear base VE table CSV"
    )
    dual_parser.add_argument(
        "--front-factor", required=True, help="Front correction factor CSV"
    )
    dual_parser.add_argument(
        "--rear-factor", required=True, help="Rear correction factor CSV"
    )
    dual_parser.add_argument(
        "--front-output", required=True, help="Front output VE table CSV"
    )
    dual_parser.add_argument(
        "--rear-output", required=True, help="Rear output VE table CSV"
    )
    dual_parser.add_argument(
        "--max-adjust",
        type=float,
        default=DEFAULT_MAX_ADJUST_PCT,
        help=f"Maximum adjustment percentage (default: ±{DEFAULT_MAX_ADJUST_PCT}%%)",
    )
    dual_parser.add_argument(
        "--dry-run", action="store_true", help="Preview operation without writing files"
    )

    # Delta command
    delta_parser = subparsers.add_parser(
        "delta", help="Analyze delta between front and rear cylinders"
    )
    delta_parser.add_argument("--front", required=True, help="Front VE table CSV")
    delta_parser.add_argument("--rear", required=True, help="Rear VE table CSV")
    delta_parser.add_argument(
        "--output", help="Optional JSON output path for delta analysis"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        if args.command == "apply":
            applier = VEApply(max_adjust_pct=args.max_adjust)

            # Secure path validation
            base_path = io_contracts.safe_path(args.base)
            factor_path = io_contracts.safe_path(args.factor)
            output_path = io_contracts.safe_path(args.output, allow_parent_dir=True)
            metadata_path = (
                io_contracts.safe_path(args.metadata, allow_parent_dir=True)
                if args.metadata
                else None
            )

            applier.apply(
                base_ve_path=base_path,
                factor_path=factor_path,
                output_path=output_path,
                metadata_path=metadata_path,
                dry_run=args.dry_run,
            )

        elif args.command == "rollback":
            roller = VERollback()

            # Secure path validation
            current_path = io_contracts.safe_path(args.current)
            metadata_path = io_contracts.safe_path(args.metadata)
            output_path = io_contracts.safe_path(args.output, allow_parent_dir=True)

            roller.rollback(
                current_ve_path=current_path,
                metadata_path=metadata_path,
                output_path=output_path,
                dry_run=args.dry_run,
            )

        elif args.command == "apply-dual":
            dual_applier = DualCylinderVEApply(max_adjust_pct=args.max_adjust)

            # Secure path validation
            f_base = io_contracts.safe_path(args.front_base)
            r_base = io_contracts.safe_path(args.rear_base)
            f_factor = io_contracts.safe_path(args.front_factor)
            r_factor = io_contracts.safe_path(args.rear_factor)
            f_out = io_contracts.safe_path(args.front_output, allow_parent_dir=True)
            r_out = io_contracts.safe_path(args.rear_output, allow_parent_dir=True)

            result = dual_applier.apply(
                front_base=f_base,
                rear_base=r_base,
                front_factor=f_factor,
                rear_factor=r_factor,
                front_output=f_out,
                rear_output=r_out,
                dry_run=args.dry_run,
            )

            if args.dry_run:
                print(json.dumps(result, indent=2))
            else:
                print("[OK] Applied Dual VE corrections")
                print(f"  Front Output: {f_out}")
                print(f"  Rear Output: {r_out}")

        elif args.command == "delta":
            # Secure path validation
            f_path = io_contracts.safe_path(args.front)
            r_path = io_contracts.safe_path(args.rear)

            result = analyze_cylinder_delta(f_path, r_path)

            # Always print summary to stdout
            print(f"Cylinder Delta Analysis (Rear - Front):")
            print(f"  Max Delta: {result['max_delta']:.4f}")
            print(f"  Avg Delta: {result['avg_delta']:.4f}")

            if args.output:
                out_path = io_contracts.safe_path(args.output, allow_parent_dir=True)
                with open(out_path, "w") as f:
                    json.dump(result, f, indent=2)
                print(f"  Detailed JSON written to: {out_path}")

        return 0
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
