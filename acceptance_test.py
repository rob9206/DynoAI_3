"""
Acceptance Test for VE Correction Apply/Rollback System

Validates all requirements from the problem statement:
1. Enforce clamping before apply: any percent > MaxAdjustmentPct is capped; default ± 7 %
2. Apply routine: Multiply base VE table by factor table, output with 4-decimal precision
3. Generate apply_meta.json with base_sha, factor_sha, applied_at_utc, max_adjust_pct, app_version
4. Rollback routine: Verify hashes; divide VE by previous factor; restore original table
5. --dry-run flag: preview outputs + metadata without writing the updated VE file
6. No factor exceeds 1.07 or drops below 0.93 at ± 7 % clamp
7. Apply → Rollback reproduces original VE within 4-decimal tolerance
8. Deterministic SHA hashes; mismatched metadata blocks rollback
"""

import json
import tempfile
from pathlib import Path

from ve_operations import (
    VEApply,
    VERollback,
    compute_sha256,
    read_ve_table,
    write_ve_table,
)


def test_requirement_1_clamping():
    """Requirement 1: Enforce clamping before apply (default ±7%)"""
    print("Testing Requirement 1: Clamping enforcement...")

    temp_dir = Path(tempfile.mkdtemp())

    # Create base VE
    rpm_bins = [2000, 2500, 3000]
    kpa_bins = [50, 65, 80]
    base_ve = [[100.0, 110.0, 120.0]] * 3
    base_path = temp_dir / "base.csv"
    write_ve_table(base_path, rpm_bins, kpa_bins, base_ve)

    # Create extreme factors that should be clamped
    extreme_factors = [
        [20.0, -25.0, 15.0],  # All exceed ±7%
        [12.0, -18.0, 10.0],
        [-30.0, 40.0, -15.0],
    ]
    factor_path = temp_dir / "factors.csv"
    write_ve_table(factor_path, rpm_bins, kpa_bins, extreme_factors)

    # Apply with default ±7%
    output_path = temp_dir / "output.csv"
    applier = VEApply()  # Default max_adjust_pct=7.0
    applier.apply(base_path, factor_path, output_path)

    # Verify all multipliers are in [0.93, 1.07]
    _, _, base_values = read_ve_table(base_path)
    _, _, updated_values = read_ve_table(output_path)

    for i in range(len(base_values)):
        for j in range(len(base_values[0])):
            multiplier = updated_values[i][j] / base_values[i][j]
            # Use small epsilon for floating point comparison
            if not 0.92999 <= multiplier <= 1.07001:
                raise AssertionError(
                    f"Multiplier {multiplier} out of bounds at [{i}][{j}]"
                )

    print("[OK] Requirement 1: Clamping enforced correctly (factors capped to ±7%)")
    return True


def test_requirement_2_apply_with_precision():
    """Requirement 2: Apply routine with 4-decimal precision"""
    print("\nTesting Requirement 2: Apply routine with 4-decimal precision...")

    temp_dir = Path(tempfile.mkdtemp())

    rpm_bins = [2000]
    kpa_bins = [50]
    base_ve = [[100.0]]
    base_path = temp_dir / "base.csv"
    write_ve_table(base_path, rpm_bins, kpa_bins, base_ve)

    # 5% increase
    factors = [[5.0]]
    factor_path = temp_dir / "factors.csv"
    write_ve_table(factor_path, rpm_bins, kpa_bins, factors)

    output_path = temp_dir / "output.csv"
    applier = VEApply()
    applier.apply(base_path, factor_path, output_path)

    # Check output has 4 decimal places
    content = output_path.read_text()
    if "105.0000" not in content:
        raise AssertionError("Output should have 4 decimal places")

    print("[OK] Requirement 2: Apply routine outputs with 4-decimal precision")
    return True


def test_requirement_3_metadata():
    """Requirement 3: Generate apply_meta.json with required fields"""
    print("\nTesting Requirement 3: Metadata generation...")

    temp_dir = Path(tempfile.mkdtemp())

    rpm_bins = [2000]
    kpa_bins = [50]
    base_ve = [[100.0]]
    base_path = temp_dir / "base.csv"
    write_ve_table(base_path, rpm_bins, kpa_bins, base_ve)

    factors = [[5.0]]
    factor_path = temp_dir / "factors.csv"
    write_ve_table(factor_path, rpm_bins, kpa_bins, factors)

    output_path = temp_dir / "output.csv"
    metadata_path = temp_dir / "meta.json"

    applier = VEApply()
    metadata = applier.apply(
        base_path, factor_path, output_path, metadata_path=metadata_path
    )

    # Verify required fields
    required_fields = [
        "base_sha",
        "factor_sha",
        "applied_at_utc",
        "max_adjust_pct",
        "app_version",
    ]
    for field in required_fields:
        if field not in metadata:
            raise AssertionError(f"Missing required field: {field}")

    # Verify comment about rollback
    if "Rollback" not in metadata.get("comment", ""):
        raise AssertionError("Missing rollback comment")

    # Verify metadata file was written
    if not metadata_path.exists():
        raise AssertionError("Metadata file not created")

    with open(metadata_path) as f:
        saved_meta = json.load(f)
    if saved_meta != metadata:
        raise AssertionError("Saved metadata doesn't match returned metadata")

    print(
        "[OK] Requirement 3: Metadata contains all required fields and is saved correctly"
    )
    return True


def test_requirement_4_rollback():
    """Requirement 4: Rollback routine with hash verification"""
    print("\nTesting Requirement 4: Rollback with hash verification...")

    temp_dir = Path(tempfile.mkdtemp())

    rpm_bins = [2000, 2500]
    kpa_bins = [50, 65]
    base_ve = [[100.0, 110.0], [120.0, 130.0]]
    base_path = temp_dir / "base.csv"
    write_ve_table(base_path, rpm_bins, kpa_bins, base_ve)

    factors = [[5.0, -3.0], [-2.0, 7.0]]
    factor_path = temp_dir / "factors.csv"
    write_ve_table(factor_path, rpm_bins, kpa_bins, factors)

    # Apply
    updated_path = temp_dir / "updated.csv"
    metadata_path = temp_dir / "meta.json"
    applier = VEApply()
    applier.apply(base_path, factor_path, updated_path, metadata_path=metadata_path)

    # Rollback
    restored_path = temp_dir / "restored.csv"
    roller = VERollback()
    roller.rollback(updated_path, metadata_path, restored_path)

    # Verify restoration
    _, _, base_values = read_ve_table(base_path)
    _, _, restored_values = read_ve_table(restored_path)

    for i in range(len(base_values)):
        for j in range(len(base_values[0])):
            if abs(base_values[i][j] - restored_values[i][j]) >= 0.0001:
                raise AssertionError(f"Rollback failed at [{i}][{j}]")

    # Test hash verification - modify factor file and try rollback
    modified_factors = [[10.0, 10.0], [10.0, 10.0]]
    write_ve_table(factor_path, rpm_bins, kpa_bins, modified_factors)

    try:
        roller.rollback(updated_path, metadata_path, temp_dir / "bad_restore.csv")
        if not False:
            raise AssertionError("Rollback should have failed with hash mismatch")
    except RuntimeError as e:
        if "hash mismatch" not in str(e).lower():
            raise AssertionError("Should detect hash mismatch")

    print(
        "[OK] Requirement 4: Rollback works and hash verification prevents tampered rollback"
    )
    return True


def test_requirement_5_dry_run():
    """Requirement 5: --dry-run flag previews without writing"""
    print("\nTesting Requirement 5: Dry-run mode...")

    temp_dir = Path(tempfile.mkdtemp())

    rpm_bins = [2000]
    kpa_bins = [50]
    base_ve = [[100.0]]
    base_path = temp_dir / "base.csv"
    write_ve_table(base_path, rpm_bins, kpa_bins, base_ve)

    factors = [[5.0]]
    factor_path = temp_dir / "factors.csv"
    write_ve_table(factor_path, rpm_bins, kpa_bins, factors)

    output_path = temp_dir / "output.csv"
    metadata_path = temp_dir / "meta.json"

    # Apply with dry-run
    applier = VEApply()
    metadata = applier.apply(
        base_path, factor_path, output_path, metadata_path=metadata_path, dry_run=True
    )

    # Verify no files were written
    if output_path.exists():
        raise AssertionError("Output file should not exist in dry-run")
    if metadata_path.exists():
        raise AssertionError("Metadata file should not exist in dry-run")

    # But metadata should be returned
    if "base_sha" not in metadata:
        raise AssertionError("Metadata should still be returned in dry-run")

    print("[OK] Requirement 5: Dry-run mode previews without writing files")
    return True


def test_requirement_6_multiplier_bounds():
    """Requirement 6: No factor exceeds 1.07 or drops below 0.93 at ±7% clamp"""
    print("\nTesting Requirement 6: Multiplier bounds [0.93, 1.07]...")

    temp_dir = Path(tempfile.mkdtemp())

    rpm_bins = [2000, 2500, 3000, 3500]
    kpa_bins = [35, 50, 65, 80, 95]
    base_ve = [[100.0] * 5 for _ in range(4)]
    base_path = temp_dir / "base.csv"
    write_ve_table(base_path, rpm_bins, kpa_bins, base_ve)

    # Create factors that will be clamped to exactly ±7%
    factors = [
        [7.0, -7.0, 100.0, -100.0, 7.0],
        [-7.0, 7.0, 50.0, -50.0, -7.0],
        [20.0, -20.0, 7.0, -7.0, 0.0],
        [-15.0, 15.0, -7.0, 7.0, 0.0],
    ]
    factor_path = temp_dir / "factors.csv"
    write_ve_table(factor_path, rpm_bins, kpa_bins, factors)

    output_path = temp_dir / "output.csv"
    applier = VEApply(max_adjust_pct=7.0)
    applier.apply(base_path, factor_path, output_path)

    _, _, base_values = read_ve_table(base_path)
    _, _, updated_values = read_ve_table(output_path)

    for i in range(len(base_values)):
        for j in range(len(base_values[0])):
            multiplier = updated_values[i][j] / base_values[i][j]
            if not 0.93 <= multiplier <= 1.07:
                raise AssertionError(
                    f"Multiplier {multiplier} out of [0.93, 1.07] at [{i}][{j}]"
                )

    print("[OK] Requirement 6: All multipliers within [0.93, 1.07] bounds")
    return True


def test_requirement_7_roundtrip_tolerance():
    """Requirement 7: Apply → Rollback reproduces original VE within 4-decimal tolerance"""
    print("\nTesting Requirement 7: Roundtrip tolerance...")

    temp_dir = Path(tempfile.mkdtemp())

    # Use realistic VE table with varying values
    rpm_bins = [1500, 2000, 2500, 3000, 3500]
    kpa_bins = [35, 50, 65, 80, 95]
    base_ve = [
        [100.5, 105.3, 110.7, 115.2, 120.9],
        [110.1, 115.8, 120.4, 125.6, 130.3],
        [115.9, 120.2, 125.5, 130.8, 135.1],
        [120.7, 125.4, 130.9, 135.3, 140.6],
        [125.3, 130.7, 135.2, 140.8, 145.4],
    ]
    base_path = temp_dir / "base.csv"
    write_ve_table(base_path, rpm_bins, kpa_bins, base_ve)

    # Various correction factors
    factors = [
        [7.0, -7.0, 5.0, -3.0, 0.0],
        [-5.0, 7.0, -7.0, 5.0, -3.0],
        [3.0, -5.0, 7.0, -7.0, 5.0],
        [-1.0, 3.0, -5.0, 7.0, -7.0],
        [0.0, -1.0, 3.0, -5.0, 7.0],
    ]
    factor_path = temp_dir / "factors.csv"
    write_ve_table(factor_path, rpm_bins, kpa_bins, factors)

    # Apply
    updated_path = temp_dir / "updated.csv"
    metadata_path = temp_dir / "meta.json"
    applier = VEApply()
    applier.apply(base_path, factor_path, updated_path, metadata_path=metadata_path)

    # Rollback
    restored_path = temp_dir / "restored.csv"
    roller = VERollback()
    roller.rollback(updated_path, metadata_path, restored_path)

    # Verify 4-decimal tolerance
    _, _, base_values = read_ve_table(base_path)
    _, _, restored_values = read_ve_table(restored_path)

    max_diff = 0.0
    for i in range(len(base_values)):
        for j in range(len(base_values[0])):
            diff = abs(base_values[i][j] - restored_values[i][j])
            max_diff = max(max_diff, diff)
            if diff >= 0.0001:
                raise AssertionError(
                    f"Roundtrip difference {diff} exceeds 4-decimal tolerance at [{i}][{j}]"
                )

    print(
        f"[OK] Requirement 7: Apply->Rollback roundtrip within tolerance (max diff: {max_diff:.10f})"
    )
    return True


def test_requirement_8_deterministic_hashes():
    """Requirement 8: Deterministic SHA hashes"""
    print("\nTesting Requirement 8: Deterministic SHA hashes...")

    temp_dir = Path(tempfile.mkdtemp())

    rpm_bins = [2000]
    kpa_bins = [50]
    base_ve = [[100.0]]
    base_path = temp_dir / "base.csv"
    write_ve_table(base_path, rpm_bins, kpa_bins, base_ve)

    # Compute hash multiple times
    hash1 = compute_sha256(base_path)
    hash2 = compute_sha256(base_path)
    if hash1 != hash2:
        raise AssertionError("Hash should be deterministic")

    # Different content should give different hash
    base_ve2 = [[100.1]]
    base_path2 = temp_dir / "base2.csv"
    write_ve_table(base_path2, rpm_bins, kpa_bins, base_ve2)
    hash3 = compute_sha256(base_path2)
    if hash1 == hash3:
        raise AssertionError("Different files should have different hashes")

    print("[OK] Requirement 8: SHA hashes are deterministic")
    return True


def main():
    print("=" * 70)
    print("VE CORRECTION SYSTEM - ACCEPTANCE TEST SUITE")
    print("=" * 70)

    tests = [
        test_requirement_1_clamping,
        test_requirement_2_apply_with_precision,
        test_requirement_3_metadata,
        test_requirement_4_rollback,
        test_requirement_5_dry_run,
        test_requirement_6_multiplier_bounds,
        test_requirement_7_roundtrip_tolerance,
        test_requirement_8_deterministic_hashes,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"[FAIL] FAILED: {e}")
            failed += 1

    print("\n" + "=" * 70)
    print(f"ACCEPTANCE TEST RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)

    if failed == 0:
        print("\n[OK] ALL ACCEPTANCE CRITERIA MET")
        print("\nThe VE Correction Apply/Rollback system is ready for production use.")
        print("\nKey Features Validated:")
        print("  • Clamping enforced at ±7% (configurable)")
        print("  • 4-decimal precision output")
        print("  • Complete metadata with SHA-256 hashes")
        print("  • Hash-verified rollback capability")
        print("  • Dry-run preview mode")
        print("  • Multiplier bounds [0.93, 1.07] enforced")
        print("  • Roundtrip accuracy < 0.0001")
        print("  • Deterministic hashing")
        return 0
    else:
        print(f"\n[FAIL] {failed} ACCEPTANCE CRITERIA FAILED")
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
