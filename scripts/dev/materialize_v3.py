#!/usr/bin/env python3
r"""
Materialize DynoAI v3 minimal production repository from DynoAI_2.

Purpose:
    Copy a minimal, production-ready subset of DynoAI_2 into the DynoAI_3 working tree.

Usage:
    python scripts/materialize_v3.py --dest C:\\Dev\\DynoAI_3 [--dry-run]

    Or set environment variable:
    set DYNOAI3_ROOT=C:\Dev\DynoAI_3
    python scripts/materialize_v3.py [--dry-run]
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


def get_git_commit_sha(repo_root: Path) -> Optional[str]:
    """Get the current Git commit SHA from the repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def get_git_branch(repo_root: Path) -> Optional[str]:
    """Get the current Git branch name."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


# Strict allowlist of files and directories to copy
ALLOWED_FILES = [
    # Core engine files
    "ai_tuner_toolkit_dyno_v1_2.py",
    # Test harnesses
    "selftest.py",
    "selftest_runner.py",
    "acceptance_test.py",
    "quick_test.py",
    # Data generators
    "generate_large_log.py",
    "generate_dense_dyno_data.py",
    # Essential config
    "requirements.txt",
    "mypy.ini",
    ".flake8",
    ".gitignore",
    # Documentation
    "README.md",
    "CHANGELOG.md",
    "QUICK_START.md",
    "QUICK_START_WEB.md",
    "MIGRATION.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "LICENSE",
    # Startup scripts
    "start-web.ps1",
    "start-dev.sh",
    "start-dev.bat",
]

ALLOWED_DIRECTORIES = [
    "tests/",  # Full test suite
    "experiments/",  # Experimental kernels
    "api/",  # Backend API service
    "scripts/",  # Essential scripts only (filtered)
    "tables/",  # Base VE tables
    "templates/",  # CSV templates
    "docs/",  # Essential documentation (filtered)
    "dynoai/",  # DynoAI package
    "frontend/",  # React frontend
]

# Explicit exclusions (even if in allowed directories)
EXCLUDE_PATTERNS = [
    # Python cache
    "__pycache__",
    "*.pyc",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    # Virtual environments
    ".venv",
    "venv",
    "env",
    # Node modules
    "node_modules",
    # Build artifacts
    "dist",
    "build",
    "*.egg-info",
    # Outputs and logs
    "outputs",
    "uploads",
    "runs",
    "ve_runs",
    "logs",
    "*.log",
    # IDE and OS
    ".vscode",
    ".idea",
    ".DS_Store",
    "Thumbs.db",
    # Git
    ".git",
    # Archive and legacy (explicit)
    "archive",
    "legacy",
    # Historical
    "gui",
    "vbnet",
    "DynoAi.CLI",
    "DynoAi.Corrections",
    "DynoAi.Corrections.Tests",
    "DynoAi.sln",
]

# Scripts to exclude (when copying scripts/ directory)
EXCLUDE_SCRIPTS = [
    "old_",
    "legacy_",
    "archive_",
    "temp_",
]

# Docs to exclude (when copying docs/ directory)
EXCLUDE_DOCS = [
    "archive",
    "legacy",
    "old",
]


def should_exclude(path: Path, relative_path: Path) -> bool:
    """Check if a path should be excluded based on exclusion patterns."""
    path_str = str(relative_path).replace("\\", "/")
    path_parts = path_str.split("/")

    # Check if any part of the path matches exclusion patterns
    for pattern in EXCLUDE_PATTERNS:
        if pattern.startswith("*"):
            # Wildcard pattern (e.g., *.pyc)
            if path.name.endswith(pattern[1:]):
                return True
        else:
            # Exact match in any path component
            if pattern in path_parts:
                return True
            # Or exact filename match
            if path.name == pattern:
                return True

    # Special filtering for scripts/
    if "scripts" in path_parts:
        for exclude_prefix in EXCLUDE_SCRIPTS:
            if path.name.startswith(exclude_prefix):
                return True

    # Special filtering for docs/
    if "docs" in path_parts:
        for exclude_dir in EXCLUDE_DOCS:
            if exclude_dir in path_parts:
                return True

    return False


def copy_file(src: Path, dst: Path, dry_run: bool = False) -> bool:
    """
    Copy a single file from src to dst, preserving contents byte-for-byte.

    Returns True if copied (or would be copied in dry-run), False if skipped.
    """
    if not src.exists():
        return False

    if dry_run:
        print(f"  [DRY-RUN] {src.name}")
        return True

    # Ensure destination directory exists
    dst.parent.mkdir(parents=True, exist_ok=True)

    # Copy file preserving metadata
    shutil.copy2(src, dst)
    print(f"  [COPY] {src.name}")
    return True


def copy_directory(
    src: Path, dst: Path, src_root: Path, dry_run: bool = False
) -> List[str]:
    """
    Recursively copy a directory, excluding patterns.

    Returns list of relative paths that were copied.
    """
    copied_files = []

    if not src.exists():
        return copied_files

    for item in src.rglob("*"):
        if item.is_file():
            relative_path = item.relative_to(src_root)

            # Check exclusions
            if should_exclude(item, relative_path):
                continue

            dst_file = dst / item.relative_to(src)

            if copy_file(item, dst_file, dry_run):
                copied_files.append(str(relative_path).replace("\\", "/"))

    return copied_files


def materialize_v3(src_root: Path, dest_root: Path, dry_run: bool = False) -> int:
    """
    Materialize DynoAI v3 from DynoAI_2.

    Args:
        src_root: DynoAI_2 repository root
        dest_root: DynoAI_3 target directory
        dry_run: If True, only print what would be done

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    print("=" * 70)
    print("[*] DynoAI v3 Materialization")
    print("=" * 70)
    print(f"Source:  {src_root}")
    print(f"Target:  {dest_root}")
    print(f"Mode:    {'DRY-RUN (no files will be copied)' if dry_run else 'LIVE'}")
    print()

    # Verify source is a git repo
    git_dir = src_root / ".git"
    if not git_dir.exists():
        print(f"[ERROR] Source is not a Git repository: {src_root}")
        return 1

    # Get source commit info
    commit_sha = get_git_commit_sha(src_root)
    branch_name = get_git_branch(src_root)

    if not commit_sha:
        print("[WARN] Could not determine Git commit SHA")
        commit_sha = "unknown"

    print(f"[*] Source commit: {commit_sha}")
    print(f"[*] Source branch: {branch_name or 'unknown'}")
    print()

    # Confirm with user (unless dry-run)
    if not dry_run:
        if dest_root.exists():
            response = input(
                "Target directory exists. Files will be overwritten. Continue? [y/N]: "
            )
        else:
            response = input("Create target directory and copy files? [y/N]: ")

        if response.lower() != "y":
            print("[*] Aborted by user.")
            return 0
        print()

    # Track all copied files
    all_copied_files: List[str] = []

    # Copy individual files
    print("[*] Copying core files...")
    for file_name in ALLOWED_FILES:
        src_file = src_root / file_name
        dst_file = dest_root / file_name

        if src_file.exists():
            if copy_file(src_file, dst_file, dry_run):
                all_copied_files.append(file_name)
        else:
            print(f"  [SKIP] {file_name} (not found)")

    # Copy directories
    print("\n[*] Copying directories...")
    for dir_path in ALLOWED_DIRECTORIES:
        dir_name = dir_path.rstrip("/")
        src_dir = src_root / dir_name
        dst_dir = dest_root / dir_name

        print(f"\n  [DIR] {dir_name}/")

        if src_dir.exists() and src_dir.is_dir():
            copied = copy_directory(src_dir, dst_dir, src_root, dry_run)
            all_copied_files.extend(copied)
        else:
            print("    [SKIP] Directory not found")

    # Generate manifest
    manifest = {
        "source_repo": "DynoAI_2",
        "source_commit": commit_sha,
        "source_branch": branch_name or "unknown",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "file_count": len(all_copied_files),
        "file_list": sorted(all_copied_files),
    }

    manifest_path = dest_root / ".dynoai_v3_manifest.json"

    if not dry_run:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        print(f"\n[+] Manifest written: {manifest_path}")
    else:
        print(f"\n[DRY-RUN] Would write manifest: {manifest_path}")
        print(f"  Files: {len(all_copied_files)}")

    # Summary
    print("\n" + "=" * 70)
    if dry_run:
        print("[*] DRY-RUN COMPLETE")
        print(f"[*] Would copy {len(all_copied_files)} files")
        print("[*] Run without --dry-run to perform actual copy")
    else:
        print("[+] Materialization complete!")
        print(f"[+] Copied {len(all_copied_files)} files")
        print("\nNext steps:")
        print(f"  1. cd {dest_root}")
        print("  2. python scripts/verify_v3_readiness.py  # Verify installation")
        print("  3. git init                                # Initialize git")
        print("  4. git add -A")
        print("  5. git commit -m 'Initialize DynoAI v3'")
        print("  6. git remote add origin <repo-url>")
        print("  7. git push -u origin main")
    print("=" * 70)

    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Materialize DynoAI v3 minimal production repository from DynoAI_2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/materialize_v3.py --dest C:\\Dev\\DynoAI_3 --dry-run
  python scripts/materialize_v3.py --dest C:\\Dev\\DynoAI_3
  
  # Or with environment variable:
  set DYNOAI3_ROOT=C:\\Dev\\DynoAI_3
  python scripts/materialize_v3.py
        """,
    )

    parser.add_argument(
        "--dest",
        type=str,
        help="Destination directory for DynoAI_3 (or set DYNOAI3_ROOT env var)",
    )

    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Show what would be copied without actually copying",
    )

    args = parser.parse_args()

    # Determine source root (DynoAI_2)
    src_root = Path(__file__).resolve().parent.parent

    # Determine destination root (DynoAI_3)
    dest_str = args.dest or os.environ.get("DYNOAI3_ROOT")

    if not dest_str:
        print("[ERROR] Destination not specified.")
        print("Use --dest argument or set DYNOAI3_ROOT environment variable.")
        print()
        parser.print_help()
        return 1

    dest_root = Path(dest_str).resolve()

    # Validate paths
    if not src_root.exists():
        print(f"[ERROR] Source directory does not exist: {src_root}")
        return 1

    # Run materialization
    return materialize_v3(src_root, dest_root, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
