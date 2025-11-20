# experiments/run_experiment.py
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
from typing import Any, Dict, List, Tuple, cast

ROOT = Path(__file__).resolve().parents[1]
_LAST_OUTDIR: Path | None = None
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
sys.path.insert(0, str(ROOT))  # import toolkit from repo root
sys.path.insert(0, str(ROOT / "experiments" / "protos"))  # find experimental kernels


def _resolve_under_root(p: str | Path) -> Path:
    """Resolve path and ensure it's within the repo root.

    Args:
        p: Path-like input to validate

    Returns:
        Resolved absolute path

    Raises:
        ValueError: Path escapes repo root
    """
    rp = Path(p).expanduser().resolve()
    root = ROOT.resolve()
    try:
        rp.relative_to(root)
    except ValueError:
        raise ValueError(f"Path escapes repo root: {rp}")
    return rp


def _strip_quote_num(s: str) -> str:
    """Strip surrounding quotes (single or double) from numeric cells."""
    if not s or not isinstance(s, str):
        return s
    start = 0
    end = len(s)
    while start < end and s[start] in {"'", '"'}:
        start += 1
    while end > start and s[end - 1] in {"'", '"'}:
        end -= 1
    return s[start:end]


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
            if v in ("", "NaN", "None") or v is None:
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


def list_csv_outputs(outdir: Path) -> list[Path]:
    return sorted([p for p in outdir.glob("*.csv") if p.is_file()])


def load_grid_csv(path: Path) -> tuple[list[int], list[int], list[list[float | None]]]:
    import csv

    with path.open(newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        header = next(r)
        kpa_bins = [int(h) for h in header[1:]]
        rpm_bins: list[int] = []
        grid: list[list[float | None]] = []
        for row in r:
            rpm_bins.append(int(row[0]))
            vals: list[float | None] = []
            for cell in row[1:]:
                cell = cell.strip()
                # Strip leading quote added by sanitize_csv_cell
                if cell.startswith("'"):
                    cell = cell[1:]
                if cell == "":
                    vals.append(None)
                else:
                    try:
                        vals.append(float(cell))
                    except ValueError:
                        vals.append(None)
            grid.append(vals)
        return rpm_bins, kpa_bins, grid


def avg_abs_delta(new_path: Path, base_path: Path) -> float | None:
    try:
        nr, nk, ng = load_grid_csv(new_path)
        br, bk, bg = load_grid_csv(base_path)
    except Exception:
        return None
    if nr != br or nk != bk:
        return None
    total = 0.0
    count = 0
    for ri in range(len(nr)):
        for ki in range(len(nk)):
            n = ng[ri][ki]
            b = bg[ri][ki]
            if n is None or b is None:
                continue
            total += abs(n - b)
            count += 1
    return (total / count) if count else None


def metrics_from_manifest(manifest_path: Path) -> dict[str, int | bool | str | None]:
    """Extract lightweight metrics from a manifest.json file.

    The manifest structure is not guaranteed here, so we guard lookups.
    """
    m: Dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw_stats = m.get("stats")
    if isinstance(raw_stats, dict):
        stats: Dict[str, Any] = cast(Dict[str, Any], raw_stats)
    else:
        stats = {}
    raw_status = m.get("status")
    if isinstance(raw_status, dict):
        status_block: Dict[str, Any] = cast(Dict[str, Any], raw_status)
    else:
        status_block = {}
    raw_apply = m.get("apply")
    if isinstance(raw_apply, dict):
        apply_block: Dict[str, Any] = cast(Dict[str, Any], raw_apply)
    else:
        apply_block = {}
    return {
        "status": status_block.get("code"),
        "apply_allowed": apply_block.get("allowed"),
        "bins_total": stats.get("bins_total"),
        "bins_covered": stats.get("bins_covered"),
        "rows_read": stats.get("rows_read"),
    }


def _early_diag(outdir: Path, msg: str, exc: Exception | None = None):
    try:
        outdir.mkdir(parents=True, exist_ok=True)
        with open(outdir / "Diagnostics_Report.txt", "a", encoding="utf-8") as f:
            f.write(msg + "\n")
            if exc:
                traceback.print_exception(exc, file=f)
    except Exception:
        pass


def main():
    global _LAST_OUTDIR
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--idea-id",
        required=True,
        help="Kernel idea id or 'baseline' for unpatched run.",
    )
    ap.add_argument(
        "--csv",
        required=True,
        type=_resolve_under_root,
        help="Input dyno CSV / WinPEP file.",
    )
    ap.add_argument(
        "--outdir",
        required=True,
        type=_resolve_under_root,
        help="Output directory (must reside within project root).",
    )
    ap.add_argument("--smooth_passes", type=int, default=2)
    ap.add_argument("--clamp", type=float, default=15.0)
    ap.add_argument("--rear_bias", type=float, default=0.0)
    ap.add_argument("--rear_rule_deg", type=float, default=2.0)
    ap.add_argument("--hot_extra", type=float, default=-1.0)
    ap.add_argument(
        "--baseline",
        action="store_true",
        help="Run without patching kernel (toolkit default)",
    )
    args = ap.parse_args()

    outdir = args.outdir
    csv_path = args.csv
    root = ROOT.resolve()
    resolved_outdir = outdir
    _LAST_OUTDIR = resolved_outdir
    if not SAFE_ID_RE.match(args.idea_id):
        raise ValueError(f"Invalid idea id '{args.idea_id}' (allowed: alphanum _ . -)")
    outdir.mkdir(parents=True, exist_ok=True)

    # 1) Import toolkit
    toolkit = importlib.import_module("ai_tuner_toolkit_dyno_v1_2")

    # 2) Import experimental kernel and monkey-patch (unless baseline)
    mod_name, func_name, params = "", "", {}
    if not args.baseline and args.idea_id != "baseline":
        try:
            # Explicit map of valid idea ids to module:function
            IDEAS = {
                # allow short aliases
                "k1": ("experiments.protos.k1_gradient_limit_v1", "kernel_smooth"),
                "k2": ("experiments.protos.k2_coverage_adaptive_v1", "kernel_smooth"),
                "k3": ("experiments.protos.k3_bilateral_v1", "kernel_smooth"),
                # allow full module ids
                "k1_gradient_limit_v1": (
                    "experiments.protos.k1_gradient_limit_v1",
                    "kernel_smooth",
                ),
                "k2_coverage_adaptive_v1": (
                    "experiments.protos.k2_coverage_adaptive_v1",
                    "kernel_smooth",
                ),
                "k3_bilateral_v1": (
                    "experiments.protos.k3_bilateral_v1",
                    "kernel_smooth",
                ),
            }

            if args.idea_id not in IDEAS:
                raise RuntimeError(
                    f"Unknown idea id '{args.idea_id}'. Known: {', '.join(sorted(IDEAS))}"
                )

            mod_name, func_name = IDEAS[args.idea_id]
            mod = importlib.import_module(mod_name)
            if not hasattr(mod, func_name):
                raise RuntimeError(f"Module '{mod_name}' missing symbol '{func_name}'")
            kernel = getattr(mod, func_name)

            # Monkey patch: replace kernel_smooth function in toolkit module.
            setattr(toolkit, "kernel_smooth", kernel)

            # Create kernel fingerprint
            import inspect

            sig = inspect.signature(kernel)
            params = {
                name: param.default
                for name, param in sig.parameters.items()
                if param.default != inspect.Parameter.empty
            }

        except Exception as e:
            _early_diag(
                outdir, f"Failed to import experimental idea '{args.idea_id}'", e
            )
            raise RuntimeError(
                f"Failed to import experimental idea '{args.idea_id}': {e}"
            )

    # 3) Call toolkit main() with patched kernel
    t0 = time.time()
    # The repo's main() takes arguments from argparse; we call it by patching sys.argv
    argv_backup = sys.argv[:]
    try:
        sys.argv = [
            "ai_tuner_toolkit_dyno_v1_2.py",
            "--csv",
            str(csv_path),
            "--outdir",
            str(resolved_outdir),
            "--smooth_passes",
            str(args.smooth_passes),
            "--clamp",
            str(args.clamp),
            "--rear_bias",
            str(args.rear_bias),
            "--rear_rule_deg",
            str(args.rear_rule_deg),
            "--hot_extra",
            str(args.hot_extra),
        ]
        exit_code = toolkit.main()
    finally:
        sys.argv = argv_backup
    dt = time.time() - t0

    # 4) Summarize results (manifest may be missing on failures; do not hard-fail)
    manifest = resolved_outdir / "manifest.json"
    summary: dict[str, object] = {
        "idea_id": args.idea_id,
        "duration_sec": round(dt, 3),
        "metrics": (
            metrics_from_manifest(manifest)
            if manifest.exists()
            else {"status": "missing-manifest"}
        ),
    }

    # 5) Optional metric: average absolute delta vs baseline VE tables if provided
    # If caller placed baseline outputs under sibling folder 'baseline', compare VE_Correction_Delta_DYNO.csv
    ve_new = resolved_outdir / "VE_Correction_Delta_DYNO.csv"
    ve_base = validate_path_within_root(
        resolved_outdir.parent / "baseline" / "VE_Correction_Delta_DYNO.csv", root
    )
    if ve_new.exists() and ve_base.exists():
        summary["avg_abs_ve_delta_vs_baseline"] = avg_abs_delta(ve_new, ve_base)

    (outdir / "experiment_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    # Write kernel fingerprint if available and kernel was loaded
    if mod_name and func_name:
        try:
            write_kernel_fingerprint(resolved_outdir, mod_name, func_name, params)
        except Exception as e:
            _early_diag(outdir, "Failed to write kernel fingerprint", e)

    print(json.dumps(summary, indent=2))
    sys.exit(exit_code or 0)


# Update write_kernel_fingerprint to validate outdir
def write_kernel_fingerprint(
    outdir: Path, mod_name: str, func_name: str, params: dict[str, Any]
):
    resolved_outdir = outdir.resolve()
    if (
        ROOT.resolve() not in resolved_outdir.parents
        and resolved_outdir != ROOT.resolve()
    ):
        raise ValueError(f"Refusing to write outside project root: {resolved_outdir}")
    fp = resolved_outdir / "kernel_fingerprint.txt"
    ordered = ", ".join(f"{k}={params[k]!r}" for k in sorted(params))
    fp.write_text(f"{mod_name}:{func_name} {ordered}\n", encoding="utf-8")


# Utility function to validate paths
def validate_path_within_root(path: Path, root: Path):
    resolved_path = path.resolve()
    if root not in resolved_path.parents and resolved_path != root:
        raise ValueError(f"Path {resolved_path} is outside the allowed root {root}")
    return resolved_path


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Always log errors to diagnostics file in the output directory when available
        if _LAST_OUTDIR is not None:
            _early_diag(_LAST_OUTDIR, "K3 run failed", e)
        raise
