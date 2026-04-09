"""
Dyno analysis orchestrator service.

Extracted from api/app.py to reduce module-level concentration of concerns.
Handles subprocess invocation, manifest reading, and format conversion.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue
from typing import Any, List, Optional

logger = logging.getLogger(__name__)


def run_dyno_analysis(
    csv_path: Path,
    output_dir: Path,
    run_id: str,
    params: Optional[dict] = None,
    progress_queue: Optional[Queue] = None,
) -> dict:
    """
    Run the DynoAI analysis toolkit on a CSV file with progress tracking.

    Returns the parsed manifest dict from the analysis output.
    """
    is_standalone = os.environ.get("DYNOAI_STANDALONE") or hasattr(sys, "_MEIPASS")

    if is_standalone:
        if hasattr(sys, "_MEIPASS"):
            project_root = Path(sys._MEIPASS)
        else:
            project_root = Path(__file__).resolve().parent.parent.parent
        script_path = project_root / "tools" / "ai_tuner_toolkit_dyno_v1_2.py"
        python_exe = sys.executable
    else:
        project_root = Path(__file__).resolve().parent.parent.parent
        os.chdir(project_root)
        script_path = project_root / "tools" / "ai_tuner_toolkit_dyno_v1_2.py"

        venv_python = project_root / ".venv/Scripts/python.exe"
        if not venv_python.exists():
            venv_python = project_root / ".venv/bin/python"
        if not venv_python.exists():
            venv_python = Path("python")
        python_exe = str(venv_python)

    if not script_path.exists():
        from api.errors import AnalysisError

        raise AnalysisError(
            f"Autotune script not found at {script_path}", stage="setup"
        )

    cmd = _build_analysis_cmd(python_exe, script_path, csv_path, output_dir, params)

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        stdout_msg = result.stdout.strip() if result.stdout else ""
        stderr_msg = result.stderr.strip() if result.stderr else "No error output"
        error_details = (
            f"[STDOUT] {stdout_msg}\n[STDERR] {stderr_msg}"
            if stdout_msg
            else f"[ERROR] {stderr_msg}"
        )
        from api.errors import SubprocessError

        raise SubprocessError(
            error_details,
            command=" ".join(cmd),
            exit_code=result.returncode,
        )

    manifest_path = output_dir / "manifest.json"
    if not manifest_path.exists():
        from api.errors import ManifestError

        raise ManifestError(
            "Manifest file not generated", manifest_path=str(manifest_path)
        )

    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    _record_timeline(csv_path, output_dir, manifest)

    return manifest


def convert_manifest_to_frontend_format(manifest: dict, run_id: str) -> dict:
    """Convert DynoAI manifest dict to frontend-expected shape."""
    return {
        "runId": run_id,
        "timestamp": manifest.get("timing", {}).get(
            "start", datetime.now(timezone.utc).isoformat()
        ),
        "inputFile": manifest.get("input", {}).get("path", "unknown.csv"),
        "rowsProcessed": manifest.get("stats", {}).get("rows_read", 0),
        "correctionsApplied": manifest.get("stats", {}).get("front_accepted", 0)
        + manifest.get("stats", {}).get("rear_accepted", 0),
        "outputFiles": [
            {
                "name": output.get("name") or Path(output.get("path", "")).name,
                "type": (
                    "VE Table"
                    if "VE" in (output.get("name") or output.get("path", ""))
                    else "Analysis Data"
                ),
                "url": (
                    f"/api/download/{run_id}/"
                    f"{Path(output.get('path') or output.get('name', '')).name}"
                ),
            }
            for output in manifest.get("outputs", [])
        ],
        "analysisMetrics": {
            "avgCorrection": manifest.get("stats", {}).get("avg_correction", 0.0),
            "maxCorrection": manifest.get("stats", {}).get("max_correction", 0.0),
            "targetAFR": 14.7,
            "iterations": manifest.get("config", {})
            .get("args", {})
            .get("smooth_passes", 2),
        },
    }


def _build_analysis_cmd(
    python_exe: Any,
    script_path: Path,
    csv_path: Path,
    output_dir: Path,
    params: Optional[dict],
) -> List[str]:
    cmd = [
        str(python_exe),
        str(script_path),
        "--csv",
        str(csv_path),
        "--outdir",
        str(output_dir),
    ]

    if params:
        for key in ("smooth_passes", "clamp", "rear_bias", "rear_rule_deg", "hot_extra"):
            if key in params:
                cmd.extend([f"--{key}", str(params[key])])

        if params.get("decel_management"):
            cmd.append("--decel-management")
            for key in ("decel_severity", "decel_rpm_min", "decel_rpm_max"):
                if key in params:
                    cmd.extend([f"--{key.replace('_', '-')}", str(params[key])])

        if params.get("balance_cylinders"):
            cmd.append("--balance-cylinders")
            for key in ("balance_mode", "balance_max_correction"):
                if key in params:
                    cmd.extend([f"--{key.replace('_', '-')}", str(params[key])])
    else:
        cmd.extend(["--clamp", "15", "--smooth_passes", "2"])

    return cmd


def _record_timeline(csv_path: Path, output_dir: Path, manifest: dict) -> None:
    try:
        from api.services.session_logger import SessionLogger

        run_dir = output_dir.parent if output_dir.name == "output" else output_dir
        session_logger = SessionLogger(run_dir)

        ve_correction_path = output_dir / "VE_Correction_Delta_DYNO.csv"
        if ve_correction_path.exists():
            session_logger.record_analysis(
                correction_path=ve_correction_path,
                manifest=manifest,
                description=f"Generated VE corrections from {Path(csv_path).name}",
            )
            logger.info("Recorded analysis in session timeline")
    except Exception as exc:
        logger.warning("Could not record timeline event: %s", exc)
