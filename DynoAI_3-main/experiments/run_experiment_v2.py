# experiments/run_experiment.py
"""Unified experiment runner with kernel registry and safety checks.

Runs toolkit with selected kernel variant, validates paths, writes fingerprints,
and enforces bin alignment + delta floor for clean summaries.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import math
import re
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Tuple

from kernel_registry import resolve_kernel

ROOT = Path(__file__).resolve().parents[1]
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")

# Add paths before any local imports
sys.path.insert(0, str(ROOT))  # import toolkit from repo root
sys.path.insert(0, str(ROOT / "experiments"))  # find experiments module


def _resolve_under_root(p: Path) -> Path:
    """Resolve path and ensure it's within the repo root.

    Args:
        p: Path to validate

    Returns:
        Resolved absolute path

    Raises:
        ValueError: Path escapes repo root
    """
    rp = p.resolve()
    root_str = str(ROOT.resolve())
    rp_str = str(rp)

    # Check if rp is under root or is root itself
    if not (
        rp_str.startswith(root_str + "\\")
        or rp_str.startswith(root_str + "/")
        or rp_str == root_str
    ):
        raise ValueError(f"Path escapes repo root: {rp}")
    return rp


def _strip_quote_num(s: str) -> str:
    """Strip leading quote from sanitized CSV numeric cells."""
    if s.startswith("'"):
        return s[1:]
    return s


def _read_grid_csv(p: Path) -> Tuple[List[int], List[int], List[List[float]]]:
    """Read VE grid CSV and return (rpm_bins, kpa_bins, grid).

    Grid cells with empty/NaN values are returned as math.nan.
    """
    with p.open(newline="", encoding="utf-8") as f:
        r = list(csv.reader(f))

    # First row: header ["RPM", "35", "50", ...]
    kpa_bins = [int(x) for x in r[0][1:]]
    rpm_bins: List[int] = []
    grid: List[List[float]] = []

    for row in r[1:]:
        rpm_bins.append(int(_strip_quote_num(row[0])))
        vals: List[float] = []
        for v in row[1:]:
            v = _strip_quote_num(v)
            if not v or v in ("", "NaN", "None"):
                vals.append(math.nan)
            else:
                vals.append(float(v))
        grid.append(vals)

    return rpm_bins, kpa_bins, grid


def _assert_bin_alignment(
    a_rpm: List[int], a_kpa: List[int], b_rpm: List[int], b_kpa: List[int]
) -> None:
    """Hard-fail if RPM/kPa grids don't match exactly.

    No implicit reindexing allowed for safety.
    """
    if a_rpm != b_rpm or a_kpa != b_kpa:
        raise AssertionError(
            f"RPM/kPa grid mismatch; no implicit reindex allowed.\n"
            f"  Grid A: RPM={a_rpm}, kPa={a_kpa}\n"
            f"  Grid B: RPM={b_rpm}, kPa={b_kpa}"
        )


def avg_abs_delta_with_alignment(new_path: Path, base_path: Path) -> float | None:
    """Compute average absolute delta between two VE grids with bin alignment check."""
    try:
        nr, nk, ng = _read_grid_csv(new_path)
        br, bk, bg = _read_grid_csv(base_path)

        # Enforce bin alignment
        _assert_bin_alignment(nr, nk, br, bk)

        total = 0.0
        count = 0
        for ri in range(len(nr)):
            for ki in range(len(nk)):
                n_val = ng[ri][ki]
                b_val = bg[ri][ki]
                if not math.isnan(n_val) and not math.isnan(b_val):
                    total += abs(n_val - b_val)
                    count += 1

        return (total / count) if count else None
    except Exception:
        return None


def metrics_from_manifest(manifest_path: Path) -> dict[str, int | bool | str | None]:
    """Extract lightweight metrics from a manifest.json file."""
    try:
        m: Dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
        raw_stats = m.get("stats", {})
        raw_status = m.get("status", {})
        raw_apply = m.get("apply", {})

        return {
            "status": raw_status.get("code"),
            "apply_allowed": raw_apply.get("allowed"),
            "bins_total": raw_stats.get("bins_total"),
            "bins_covered": raw_stats.get("bins_covered"),
            "rows_read": raw_stats.get("rows_read"),
        }
    except Exception:
        return {"status": "manifest-read-error"}


def _early_diag(outdir: Path, msg: str, exc: Exception | None = None) -> None:
    """Write early diagnostic to Diagnostics_Report.txt."""
    try:
        outdir.mkdir(parents=True, exist_ok=True)
        with open(outdir / "Diagnostics_Report.txt", "a", encoding="utf-8") as f:
            f.write(msg + "\n")
            if exc:
                traceback.print_exception(exc, file=f)
    except Exception:
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--idea-id", required=True, help="Kernel idea id from registry.")
    ap.add_argument("--csv", required=True, help="Input dyno CSV / WinPEP file.")
    ap.add_argument(
        "--outdir",
        required=True,
        help="Output directory (must reside within project root).",
    )
    ap.add_argument(
        "--smooth_passes",
        type=int,
        default=None,
        help="Override kernel default smooth passes",
    )
    ap.add_argument(
        "--clamp", type=float, default=None, help="Override kernel default clamp limit"
    )
    ap.add_argument("--rear_bias", type=float, default=0.0)
    ap.add_argument("--rear_rule_deg", type=float, default=2.0)
    ap.add_argument("--hot_extra", type=float, default=-1.0)
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Write summary and fingerprint without running pipeline",
    )
    args = ap.parse_args()

    # Validate and resolve paths
    csv_path = _resolve_under_root(Path(args.csv))
    outdir = _resolve_under_root(Path(args.outdir))

    if not SAFE_ID_RE.match(args.idea_id):
        raise ValueError(f"Invalid idea id '{args.idea_id}' (allowed: alphanum _ . -)")

    # Auto-create output directory
    outdir.mkdir(parents=True, exist_ok=True)

    # Resolve kernel from registry
    try:
        kernel_fn, defaults, module_path, func_name = resolve_kernel(args.idea_id)
        params = dict(defaults)

        # CLI overrides
        if args.smooth_passes is not None:
            params["passes"] = int(args.smooth_passes)
        if args.clamp is not None:
            params["clamp"] = float(args.clamp)
    except Exception as e:
        _early_diag(outdir, f"Failed to resolve kernel '{args.idea_id}'", e)
        raise

    # Write kernel fingerprint
    fingerprint_content = f"module={module_path}\nfunction={func_name}\nparams={json.dumps(params, sort_keys=True)}\n"
    (outdir / "kernel_fingerprint.txt").write_text(
        fingerprint_content, encoding="utf-8"
    )

    # Dry-run mode: skip toolkit execution
    if args.dry_run:
        summary = {
            "status": {"code": "DRY_RUN"},
            "config": {"idea_id": args.idea_id, "args": params},
            "duration_sec": 0.0,
        }
        (outdir / "experiment_summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        print(json.dumps(summary, indent=2))
        return 0

    # Import toolkit and monkey-patch kernel
    toolkit = importlib.import_module("ai_tuner_toolkit_dyno_v1_2")
    setattr(toolkit, "kernel_smooth", kernel_fn)

    # Execute toolkit with patched kernel
    t0 = time.time()
    argv_backup = sys.argv[:]
    try:
        sys.argv = [
            "ai_tuner_toolkit_dyno_v1_2.py",
            "--csv",
            str(csv_path),
            "--outdir",
            str(outdir),
            "--smooth_passes",
            str(params.get("passes", 2)),
            "--clamp",
            str(args.clamp if args.clamp is not None else 15.0),
            "--rear_bias",
            str(args.rear_bias),
            "--rear_rule_deg",
            str(args.rear_rule_deg),
            "--hot_extra",
            str(args.hot_extra),
        ]
        exit_code = toolkit.main()
    except Exception as e:
        _early_diag(outdir, "Toolkit execution failed", e)
        raise
    finally:
        sys.argv = argv_backup

    dt = time.time() - t0

    # Summarize results
    manifest = outdir / "manifest.json"
    summary: dict[str, object] = {
        "idea_id": args.idea_id,
        "duration_sec": round(dt, 3),
        "metrics": (
            metrics_from_manifest(manifest)
            if manifest.exists()
            else {"status": "missing-manifest"}
        ),
    }

    # Compute delta vs baseline if available (with bin alignment check)
    ve_new = outdir / "VE_Correction_Delta_DYNO.csv"
    ve_base = outdir.parent / "baseline" / "VE_Correction_Delta_DYNO.csv"

    if ve_new.exists() and ve_base.exists():
        try:
            ve_base_resolved = _resolve_under_root(ve_base)
            delta = avg_abs_delta_with_alignment(ve_new, ve_base_resolved)
            if delta is not None:
                # Delta floor: treat < 0.001% as 0.000%
                reported_delta = 0.0 if delta < 1e-3 else delta
                summary["avg_abs_ve_delta_vs_baseline"] = round(reported_delta, 3)
        except Exception as e:
            _early_diag(outdir, "Failed to compute baseline delta", e)

    # Write summary
    (outdir / "experiment_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))

    return exit_code or 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        # Fallback diagnostics
        try:
            ap = argparse.ArgumentParser()
            ap.add_argument("--outdir", required=True)
            args, _ = ap.parse_known_args()
            _early_diag(Path(args.outdir), "Top-level exception", e)
        except Exception:
            pass
        raise
