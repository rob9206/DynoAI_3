from __future__ import annotations

import json
import math
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from dynoai.test_utils import make_synthetic_csv
# make_realistic_dyno_csv is also available in dynoai.test_utils if needed for advanced testing
from io_contracts import sanitize_csv_cell

PY = sys.executable
ROOT = Path(__file__).resolve().parent
TOOL = ROOT / "ai_tuner_toolkit_dyno_v1_2.py"  # adjust if needed

REQUIRED_FILES = [("Diagnostics_Report.txt", "text"), ("VE_Correction_Delta_DYNO.csv", "csv")]
OPTIONAL_FILES = [("attribution_grid.csv","csv")]


def run_tool(csv_path: Path, outdir: Path, extra_args: List[str] | None = None):
    args = [PY, str(TOOL), "--csv", str(csv_path), "--outdir", str(outdir),
            "--smooth_passes","2","--clamp","15","--rear_bias","2.5","--rear_rule_deg","2.0","--hot_extra","-1.0"]
    if extra_args:
        args += extra_args
    return subprocess.run(args, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

def must_exist(path: Path, kind: str = "file"):
    if not path.exists():
        raise AssertionError(f"Missing expected {kind}: {path}")


def main() -> int:
    # Create a local temp directory to avoid cross-directory issues with safe_path
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    tmp_root = ROOT / "temp_selftest"
    tmp_root.mkdir(exist_ok=True)
    tmp = tmp_root / f"run_{timestamp}"
    tmp.mkdir(parents=True, exist_ok=True)

    try:
        csv_path, outdir = tmp/"selftest.csv", tmp/"out"
        outdir.mkdir(parents=True, exist_ok=True)
        make_synthetic_csv(csv_path)
        print("Running Dyno AI Tuner self-test...")
        proc = run_tool(csv_path, outdir)
        print(proc.stdout)
        if proc.returncode != 0:
            print(proc.stderr)
            raise AssertionError(f"Tool exited with code {proc.returncode}")
        manifest = json.load(open(outdir/"manifest.json","r",encoding="utf-8"))
        status = manifest.get("status",{}).get("code")
        if status != "success":
            raise AssertionError(f"Manifest status not success: {status}")
        for fname,_ in REQUIRED_FILES:
            must_exist(outdir/fname)
        print("[OK] Core outputs found.")
        for fname,_ in OPTIONAL_FILES:
            if not (outdir/fname).exists():
                print(f"[WARN] Optional output missing (ok): {fname}")
        stats = manifest.get("stats", {})
        if int(stats.get("rows_read",0)) < 1000:
            raise AssertionError("Rows read too low.")
        if int(stats.get("bins_total",0)) <= 0:
            raise AssertionError("No bins detected.")
        print("[OK] Manifest validated.")
        print(f"Artifacts saved in: {outdir}")
        print("[OK] Self-tests PASSED")
        return 0
    except Exception as e:
        print(f"[ERROR] Self-tests FAILED: {e}")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
