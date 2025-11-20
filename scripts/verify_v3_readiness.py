from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

# Make io_contracts import robust across layouts (repo root vs dynoai/io_contracts.py)
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
dyno_pkg = ROOT / "dynoai"
if dyno_pkg.exists():
    dyno_pkg_str = str(dyno_pkg)
    if dyno_pkg_str not in sys.path:
        sys.path.insert(0, dyno_pkg_str)
try:
    import io_contracts  # type: ignore
    from io_contracts import safe_path  # type: ignore
except ImportError:
    from dynoai import io_contracts  # type: ignore
    from dynoai.io_contracts import safe_path  # type: ignore


ROOT = Path(__file__).resolve().parent.parent

TOOL = ROOT / "ai_tuner_toolkit_dyno_v1_2.py"
SELFTEST = ROOT / "selftest_runner.py"
LARGE_LOG_GENERATOR = ROOT / "generate_large_log.py"

RUNS_DIR = ROOT / "runs"
SMOKE_OUTDIR = RUNS_DIR / "v3_smoke"
VE_RUNS_PREVIEW = ROOT / "ve_runs" / "preview"


def run_cmd(cmd: list[str], cwd: Path | None = None, label: str = "") -> int:
    print(f"\n=== RUN: {label or ' '.join(cmd)} ===")
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.stdout:
        print(proc.stdout.strip())
    if proc.stderr:
        print(proc.stderr.strip(), file=sys.stderr)
    print(f"=== EXIT: {proc.returncode} ({label}) ===")
    return proc.returncode


def step_selftest() -> bool:
    print("\n[STEP A] Running selftest_runner.py ...")
    if not SELFTEST.exists():
        print(f"[ERROR] selftest_runner.py not found at {SELFTEST}")
        return False
    code = run_cmd([sys.executable, str(SELFTEST)], cwd=ROOT, label="selftest_runner")
    if code != 0:
        print("[FAIL] selftest_runner.py exited non-zero")
        return False
    print("[OK] selftest_runner.py completed.")
    return True


def ensure_large_log() -> Path | None:
    print("\n[STEP B] Ensuring large_test_log.csv exists ...")
    csv_path = ROOT / "large_test_log.csv"
    if csv_path.exists():
        print(f"[OK] Found existing {csv_path}")
        return csv_path
    if not LARGE_LOG_GENERATOR.exists():
        print(f"[ERROR] generate_large_log.py not found at {LARGE_LOG_GENERATOR}")
        return None
    code = run_cmd(
        [sys.executable, str(LARGE_LOG_GENERATOR)],
        cwd=ROOT,
        label="generate_large_log",
    )
    if code != 0 or not csv_path.exists():
        print("[FAIL] Failed to generate large_test_log.csv")
        return None
    print(f"[OK] Generated {csv_path}")
    return csv_path


def step_dyno_smoke(csv_path: Path) -> bool:
    print("\n[STEP C] Running dyno smoke test on large_test_log.csv ...")
    # Use safe_path for new output directory
    outdir = safe_path(str(SMOKE_OUTDIR))
    outdir.mkdir(parents=True, exist_ok=True)
    if not TOOL.exists():
        print(f"[ERROR] Dyno tool not found at {TOOL}")
        return False
    cmd = [
        sys.executable,
        str(TOOL),
        "--csv",
        str(csv_path),
        "--outdir",
        str(outdir),
        "--smooth_passes",
        "2",
        "--clamp",
        "7.0",
    ]
    code = run_cmd(cmd, cwd=ROOT, label="dyno_smoke_v3")
    if code != 0:
        print("[FAIL] Dyno smoke test exited non-zero")
        return False
    manifest_path = outdir / "manifest.json"
    if not manifest_path.exists():
        print(f"[FAIL] manifest.json not found in {outdir}")
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[FAIL] Could not parse manifest.json: {e}")
        return False
    status = manifest.get("status", {})
    code_str = status.get("code")
    if code_str != "success":
        print(f"[FAIL] Manifest status.code != 'success' (got {code_str!r})")
        return False
    stats = manifest.get("stats", {})
    rows_read = int(stats.get("rows_read", 0) or 0)
    bins_total = int(stats.get("bins_total", 0) or 0)
    bins_covered = int(stats.get("bins_covered", 0) or 0)
    if rows_read <= 0 or bins_total <= 0 or bins_covered <= 0:
        print(f"[FAIL] Suspicious stats: rows_read={rows_read}, bins_total={bins_total}, bins_covered={bins_covered}")
        return False
    print(f"[OK] Dyno smoke manifest: rows_read={rows_read}, bins_total={bins_total}, bins_covered={bins_covered}")
    return True


def find_base_ve_table() -> Path | None:
    # Heuristic: search common locations like tables/ or root for a VE CSV
    candidates: list[Path] = []
    tables_dir = ROOT / "tables"
    if tables_dir.exists():
        candidates.extend(sorted(tables_dir.glob("*.csv")))
    candidates.extend(sorted(ROOT.glob("*.csv")))
    for p in candidates:
        name = p.name.lower()
        if "ve" in name and "base" in name:
            return p
    return None


def step_ve_apply_rollback() -> bool:
    print("\n[STEP D] (Optional) VEApply/VERollback dry-run check ...")
    try:
        import ve_operations
    except ImportError as e:
        print(f"[WARN] ve_operations not importable: {e}. Skipping VEApply/VERollback check.")
        return True  # Non-fatal
    base_table = find_base_ve_table()
    if base_table is None:
        print("[WARN] No obvious base VE table found (looking for *ve*base*.csv). Skipping VEApply/VERollback dry-run.")
        return True  # Non-fatal
    factor_table = SMOKE_OUTDIR / "VE_Correction_Delta_DYNO.csv"
    if not factor_table.exists():
        print(f"[WARN] VE_Correction_Delta_DYNO.csv not found at {factor_table}. Skipping VEApply/VERollback dry-run.")
        return True
    # Use preview folder for any potential outputs; still DRY-RUN
    preview_dir = safe_path(str(VE_RUNS_PREVIEW))
    preview_dir.mkdir(parents=True, exist_ok=True)
    output_path = preview_dir / "VE_Apply_Preview.csv"
    meta_path = preview_dir / "VE_Apply_Preview_meta.json"
    print(f"[INFO] Using base VE table: {base_table}")
    print(f"[INFO] Using factor table: {factor_table}")
    print(f"[INFO] Output (dry-run preview): {output_path}")
    print(f"[INFO] Metadata (dry-run preview): {meta_path}")
    applier = ve_operations.VEApply()
    # DRY RUN: does not actually write files
    applier.apply(
        base_ve_path=base_table,
        factor_path=factor_table,
        output_path=output_path,
        metadata_path=meta_path,
        dry_run=True,
    )
    print("[OK] VEApply dry-run completed successfully.")
    return True


def step_git_status() -> bool:
    print("\n[STEP E] Checking git status (optional) ...")
    code = run_cmd(["git", "status", "--porcelain"], cwd=ROOT, label="git_status")
    # Non-zero exit means git not available; that's not a blocker for code readiness.
    return True


def main() -> int:
    print("DynoAI v3 Readiness Verification\n")
    ok = True
    if not step_selftest():
        ok = False
    csv_path = ensure_large_log()
    if csv_path is None:
        ok = False
    else:
        if not step_dyno_smoke(csv_path):
            ok = False
    if not step_ve_apply_rollback():
        # optional; only mark as fatal if you want. Keep non-fatal for now.
        pass
    step_git_status()
    print("\n=== SUMMARY ===")
    if ok:
        print("[OK] DynoAI v3 is READY from engine/selftest perspective.")
        return 0
    else:
        print("[FAIL] DynoAI v3 readiness checks FAILED. See log above.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


