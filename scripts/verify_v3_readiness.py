#!/usr/bin/env python3
"""
DynoAI v3 Readiness Verification Script

Acts as a gatekeeper before tagging/pushing v3.
Validates repository structure, runs tests, and checks API health.

Usage:
    python scripts/verify_v3_readiness.py                # Run all checks
    python scripts/verify_v3_readiness.py --pytest-only  # Only pytest
    python scripts/verify_v3_readiness.py --selftest-only # Only selftest
    python scripts/verify_v3_readiness.py --skip-api     # Skip API check
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


# Determine repo root
REPO_ROOT = Path(__file__).resolve().parent.parent


def check_path(path: Path, kind: str) -> bool:
    """
    Validate that a required path exists.

    Args:
        path: Path to check (absolute or relative to REPO_ROOT)
        kind: "file" or "dir"

    Returns:
        True if exists and matches kind, False otherwise
    """
    if not path.is_absolute():
        path = REPO_ROOT / path

    rel_path = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path

    if kind == "file":
        exists = path.is_file()
    elif kind == "dir":
        exists = path.is_dir()
    else:
        exists = path.exists()

    if exists:
        print(f"  [OK] {rel_path}")
        return True
    else:
        print(f"  [MISSING] {rel_path}")
        return False


def check_repo_structure() -> bool:
    """
    Validate that all required files and directories exist.

    Returns:
        True if all required paths exist, False otherwise
    """
    print("\n[VERIFY] Checking repo structure...")

    required_paths: List[Tuple[Path, str]] = [
        # Core engine files
        (REPO_ROOT / "ai_tuner_toolkit_dyno_v1_2.py", "file"),
        (REPO_ROOT / "dynoai" / "core" / "ve_operations.py", "file"),
        (REPO_ROOT / "dynoai" / "core" / "io_contracts.py", "file"),
        # Test infrastructure
        (REPO_ROOT / "tests", "dir"),
        # API
        (REPO_ROOT / "api", "dir"),
        (REPO_ROOT / "api" / "app.py", "file"),
        # Essential configs
        (REPO_ROOT / "requirements.txt", "file"),
    ]

    all_exist = True
    for path, kind in required_paths:
        if not check_path(path, kind):
            all_exist = False

    # Check for at least one selftest file
    selftest_files = list(REPO_ROOT.glob("selftest*.py"))
    if selftest_files:
        print(f"  [OK] Found {len(selftest_files)} selftest file(s)")
    else:
        print("  [MISSING] No selftest*.py files found")
        all_exist = False

    if all_exist:
        print("[+] All required files present")
    else:
        print("[-] Some required files are missing")

    return all_exist


def run_pytest(repo_root: Path) -> int:
    """
    Run pytest test suite.

    Args:
        repo_root: Repository root directory

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    print("[VERIFY] Running pytest...")
    result = subprocess.run([sys.executable, "-m", "pytest"], cwd=str(repo_root))
    if result.returncode == 0:
        print("[VERIFY] pytest PASSED")
    else:
        print("[VERIFY] pytest FAILED (exit code {})".format(result.returncode))
    return result.returncode


def run_selftest(repo_root: Path) -> int:
    """
    Run selftest suite.

    Args:
        repo_root: Repository root directory

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    selftest_runner = repo_root / "selftest_runner.py"
    selftest_main = repo_root / "selftest.py"

    if selftest_runner.exists():
        cmd = [sys.executable, str(selftest_runner)]
        label = "selftest_runner.py"
    elif selftest_main.exists():
        cmd = [sys.executable, str(selftest_main)]
        label = "selftest.py"
    else:
        print("[VERIFY] No selftest script found; skipping selftest step.")
        return 0

    print(f"[VERIFY] Running {label}...")
    result = subprocess.run(cmd, cwd=str(repo_root))
    if result.returncode == 0:
        print(f"[VERIFY] {label} PASSED")
    else:
        print(f"[VERIFY] {label} FAILED (exit code {result.returncode})")
    return result.returncode


def check_api_health() -> bool:
    """
    Check if API server is running and healthy.

    Returns:
        True if API is healthy, False otherwise
    """
    print("\n[TEST] Checking API health...")

    try:
        import requests
    except ImportError:
        print("[WARN] requests module not installed, skipping API check")
        print("       Install with: pip install requests")
        return True  # Non-fatal

    api_url = "http://localhost:5001/api/health"

    try:
        response = requests.get(api_url, timeout=5)

        if response.status_code == 200:
            data = response.json()
            print(f"[+] API health check: PASS")
            print(f"    Status: {data.get('status')}")
            print(f"    Version: {data.get('version')}")
            return True
        else:
            print(f"[-] API health check: FAIL (HTTP {response.status_code})")
            return False

    except requests.exceptions.ConnectionError:
        print("[-] API health check: FAIL (connection refused)")
        print("    API server may not be running on port 5001")
        print("    Start with: python api/app.py")
        return False
    except requests.exceptions.Timeout:
        print("[-] API health check: FAIL (timeout)")
        return False
    except Exception as e:
        print(f"[-] API health check: FAIL ({e})")
        return False


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="DynoAI v3 Readiness Verification",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/verify_v3_readiness.py               # Run all checks
  python scripts/verify_v3_readiness.py --pytest-only # Only pytest
  python scripts/verify_v3_readiness.py --skip-api    # Skip API check
        """,
    )

    parser.add_argument(
        "--skip-api",
        action="store_true",
        help="Skip API health check",
    )

    parser.add_argument(
        "--pytest-only",
        action="store_true",
        help="Only run pytest (skip selftest and API)",
    )

    parser.add_argument(
        "--selftest-only",
        action="store_true",
        help="Only run selftest (skip pytest and API)",
    )

    args = parser.parse_args()

    # Print header
    print("=" * 70)
    print("[*] DynoAI v3 Readiness Verification")
    print("=" * 70)
    print(f"Repo: {REPO_ROOT}")
    print()

    # Phase 1: Check structure (always run)
    structure_ok = check_repo_structure()

    if not structure_ok:
        print("\n" + "=" * 70)
        print("[-] VERIFICATION FAILED: Required files missing")
        print("=" * 70)
        return 1

    # Determine which tests to run
    run_pytest_test = not args.selftest_only
    run_selftest_test = not args.pytest_only
    run_api_check = (
        not args.skip_api and not args.pytest_only and not args.selftest_only
    )

    results = []

    # Phase 2: Run pytest
    if run_pytest_test:
        pytest_result = run_pytest(REPO_ROOT)
        results.append(("pytest", pytest_result == 0))

    # Phase 3: Run selftest
    if run_selftest_test:
        selftest_result = run_selftest(REPO_ROOT)
        results.append(("selftest", selftest_result == 0))

    # Phase 4: Check API
    if run_api_check:
        api_result = check_api_health()
        results.append(("API health", api_result))

    # Summary
    print("\n" + "=" * 70)
    print("[*] VERIFICATION SUMMARY")
    print("=" * 70)

    all_passed = True
    for test_name, passed in results:
        status = "[+] PASS" if passed else "[-] FAIL"
        print(f"  {status}: {test_name}")
        if not passed:
            all_passed = False

    print("=" * 70)

    if all_passed and results:
        print("\n[+] DynoAI v3 is READY for release!")
        print("\nNext steps:")
        print("  1. git tag -a v3.0.0 -m 'DynoAI v3.0: Production release'")
        print("  2. git push origin v3.0.0")
        print("  3. git push origin main")
        print()
        return 0
    elif not results:
        print("\n[WARN] No tests were run (check flags)")
        return 0
    else:
        print("\n[-] DynoAI v3 has FAILED verification checks")
        print("\nFix the issues above before releasing.")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
