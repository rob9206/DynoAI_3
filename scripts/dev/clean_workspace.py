"""Utility to clean local-only artifacts (caches, scratch outputs, stale bundles).

Run as:
    python scripts/clean_workspace.py --apply
Use --aggressive to also drop bulky backups like test_fixed_venv.
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
PROTECTED_PARTS = {".git", ".venv"}
RELEASE_ARCHIVE_PATTERNS = (
    "DynoAI_Master_Build_*.zip",
    "DynoAI_Reliability_Pack_*.zip",
)


@dataclass(frozen=True)
class Target:
    glob: str
    aggressive: bool
    description: str


TARGETS: Tuple[Target, ...] = (
    Target("**/__pycache__", False, "Python bytecode caches"),
    Target(".mypy_cache", False, "mypy cache"),
    Target(".pytest_cache", False, "pytest cache"),
    Target(".ruff_cache", False, "ruff cache"),
    Target("temp_selftest", False, "self-test scratch runs"),
    Target("outputs_selftest_*", False, "timestamped self-test outputs"),
    Target("test_output", False, "legacy test output directory"),
    Target("test_output_dir", False, "placeholder test output directory"),
    Target("test_kernel_output", False, "kernel debugging artifacts"),
    Target("test_generic_output", False, "generic test artifacts"),
    Target("__pycache__", False, "root-level bytecode cache"),
    Target(".venv_broken_backup", True, "stale virtualenv backup"),
    Target("test_fixed_venv", True, "pinned virtualenv used for experiments"),
)


def _within_protected(path: Path) -> bool:
    try:
        rel_parts = path.relative_to(ROOT).parts
    except ValueError:
        return True
    return any(part in PROTECTED_PARTS for part in rel_parts)


def _matches_keep(path: Path, keep_patterns: Sequence[str]) -> bool:
    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    return any(fnmatch.fnmatch(rel, pattern) for pattern in keep_patterns)


def _collect_matches(
    include_aggressive: bool, keep_patterns: Sequence[str]
) -> List[Tuple[Path, Target]]:
    seen: set[Path] = set()
    results: List[Tuple[Path, Target]] = []
    for target in TARGETS:
        if target.aggressive and not include_aggressive:
            continue
        for match in ROOT.glob(target.glob):
            if not match.exists():
                continue
            if _within_protected(match):
                continue
            if _matches_keep(match, keep_patterns):
                continue
            resolved = match.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            results.append((resolved, target))
    results.sort(key=lambda item: str(item[0]))
    return results


def _handle_remove_error(func, path, exc_info):
    # Ensure Windows read-only files can be deleted.
    try:
        os.chmod(path, stat.S_IWRITE)
    except OSError:
        pass
    try:
        func(path)
    except OSError:
        raise exc_info[1]


def _remove_path(path: Path, dry_run: bool, verbose: bool) -> None:
    rel = path.relative_to(ROOT)
    if dry_run:
        print(f"[dry-run] would remove {rel}")
        return
    if path.is_dir():
        shutil.rmtree(path, onerror=_handle_remove_error)
    else:
        path.unlink(missing_ok=True)
    if verbose:
        print(f"removed {rel}")


def _archive_releases(dry_run: bool, verbose: bool) -> List[Tuple[Path, Path]]:
    moves: List[Tuple[Path, Path]] = []
    dest_root = ROOT / "archive" / "releases"
    for pattern in RELEASE_ARCHIVE_PATTERNS:
        for src in ROOT.glob(pattern):
            dest = dest_root / src.name
            if dest.exists():
                continue
            moves.append((src, dest))
    if dry_run:
        for src, dest in moves:
            print(f"[dry-run] would move {src.relative_to(ROOT)} -> {dest.relative_to(ROOT)}")
        return moves
    dest_root.mkdir(parents=True, exist_ok=True)
    for src, dest in moves:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), dest)
        if verbose:
            print(f"moved {src.relative_to(ROOT)} -> {dest.relative_to(ROOT)}")
    return moves


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Remove local-only caches and generated outputs so the repo stays tidy."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete files (default is dry-run).",
    )
    parser.add_argument(
        "--aggressive",
        action="store_true",
        help="Include heavier targets such as legacy virtualenv backups.",
    )
    parser.add_argument(
        "--archive-releases",
        action="store_true",
        help="Move release ZIP bundles into archive/releases/.",
    )
    parser.add_argument(
        "--keep",
        action="append",
        default=[],
        metavar="GLOB",
        help="Skip matches that satisfy this glob (can be passed multiple times).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print a line for every deletion/move.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dry_run = not args.apply
    matches = _collect_matches(args.aggressive, args.keep)

    if matches:
        print(f"Discovered {len(matches)} target(s).")
    else:
        print("No generated caches or outputs matched the current filters.")

    removed = 0
    for path, target in matches:
        if args.verbose:
            print(f"target {path.relative_to(ROOT)} ({target.description})")
        _remove_path(path, dry_run, args.verbose)
        removed += 1

    moves: List[Tuple[Path, Path]] = []
    if args.archive_releases:
        moves = _archive_releases(dry_run, args.verbose)

    if dry_run:
        print("Dry run complete. Re-run with --apply to make changes.")
    else:
        print(f"Removed {removed} item(s).")
        if args.archive_releases and moves:
            print(f"Archived {len(moves)} release bundle(s).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
