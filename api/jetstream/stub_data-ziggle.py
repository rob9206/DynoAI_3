"""Utilities for serving Jetstream stub data when the real API is unavailable."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from jetstream.models import RunError, RunStatus
from services.run_manager import get_run_manager

STUB_ENV = os.getenv("JETSTREAM_STUB_DATA") or os.getenv("JETSTREAM_USE_STUBS")
_STUB_ENABLED = bool(
    STUB_ENV and STUB_ENV.strip().lower() in {"1", "true", "yes", "on"}
)

VE_DELTA_SAMPLE = """RPM,0,10,20,30,40,50,60,70,80,100
1000,-2.5,-1.8,-0.3,0.5,1.2,2.8,4.5,6.2,8.1,10.5
1500,-3.2,-2.1,-0.8,0.2,0.8,2.1,3.8,5.5,7.8,9.2
2000,-4.1,-2.8,-1.5,-0.3,0.5,1.5,3.0,4.8,6.5,8.0
2500,-5.2,-3.5,-2.0,-0.8,0.1,1.0,2.5,4.0,5.5,7.0
3000,-6.5,-4.2,-2.5,-1.2,-0.2,0.8,2.0,3.5,5.0,6.5
3500,-8.0,-5.5,-3.2,-1.8,-0.5,0.5,1.5,3.0,4.5,6.0
4000,-10.2,-7.0,-4.5,-2.5,-1.0,0.2,1.2,2.5,4.0,5.5
"""

DIAGNOSTICS_REPORT = """DynoAI Diagnostics Summary
- Cells corrected: 132 / 256 (52%)
- Clamp limit: ±7%
- Max correction: +7.2%
- Min correction: -5.4%
- Avg correction: -1.8%
- Clamp hits: 8
"""

ANOMALY_SAMPLE = json.dumps(
    [
        {
            "id": "afr_wobble",
            "severity": "medium",
            "message": "Detected AFR oscillation between 3.0-3.5 seconds",
        },
        {
            "id": "knock_retard",
            "severity": "low",
            "message": "Rear cylinder knock retard spike @ 4800 RPM",
        },
    ],
    indent=2,
)


def is_stub_mode_enabled() -> bool:
    """Return True when Jetstream stub mode is active."""
    return _STUB_ENABLED


def initialize_stub_data() -> None:
    """Seed the run manager with sample data when stub mode is enabled."""
    if not is_stub_mode_enabled():
        return
    _ensure_stub_runs()


def get_stub_status() -> Dict[str, Any]:
    """Return a canned poller status payload."""
    now = datetime.now(timezone.utc)
    processing = next(
        (
            run
            for run in _SAMPLE_RUNS
            if run["status"] in {RunStatus.PROCESSING, RunStatus.VALIDATING}
        ),
        None,
    )
    pending = sum(
        1
        for run in _SAMPLE_RUNS
        if run["status"] in {RunStatus.PENDING, RunStatus.DOWNLOADING}
    )
    return {
        "connected": True,
        "last_poll": (now - timedelta(minutes=2)).isoformat(),
        "next_poll": (now + timedelta(seconds=45)).isoformat(),
        "pending_runs": pending,
        "processing_run": processing["run_id"] if processing else None,
        "error": None,
    }


def get_stub_sync_response() -> Dict[str, Any]:
    """Return a deterministic sync response."""
    newest = next(
        (run for run in _SAMPLE_RUNS if run["status"] != RunStatus.COMPLETE), None
    )
    if not newest:
        return {"new_runs_found": 0, "run_ids": [], "stubbed": True}
    return {"new_runs_found": 1, "run_ids": [newest["run_id"]], "stubbed": True}


def _iso_minutes_ago(minutes: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


_SAMPLE_RUNS: List[Dict[str, Any]] = [
    {
        "run_id": "run_jetstream_demo_complete",
        "jetstream_id": "JS-ALPHA-001",
        "status": RunStatus.COMPLETE,
        "current_stage": "export",
        "progress_percent": 100,
        "age_minutes": 45,
        "metadata": {
            "vehicle": "2021 Harley-Davidson FXLRST",
            "dyno_type": "Dynojet 250i",
            "engine_type": "Milwaukee-Eight 117",
            "ambient_temp_f": 68.0,
            "ambient_pressure_inhg": 29.52,
            "humidity_percent": 38.0,
            "duration_seconds": 14,
            "data_points": 1820,
            "peak_hp": 118.4,
            "peak_torque": 123.7,
        },
        "results_summary": {
            "avg_correction": -1.8,
            "max_correction": 7.2,
            "min_correction": -5.4,
            "cells_corrected": 132,
            "cells_clamped": 8,
        },
        "files": [
            {
                "name": "VE_Correction_Delta_DYNO.csv",
                "type": "csv",
                "content": VE_DELTA_SAMPLE,
            },
            {
                "name": "Diagnostics_Report.txt",
                "type": "text",
                "content": DIAGNOSTICS_REPORT,
            },
            {
                "name": "Anomaly_Hypotheses.json",
                "type": "json",
                "content": ANOMALY_SAMPLE,
            },
        ],
        "stats": {"rows_read": 18432, "front_accepted": 58, "rear_accepted": 54},
    },
    {
        "run_id": "run_jetstream_demo_processing",
        "jetstream_id": "JS-BETA-014",
        "status": RunStatus.PROCESSING,
        "current_stage": "Validating VE tables",
        "progress_percent": 62,
        "age_minutes": 8,
        "metadata": {
            "vehicle": "2019 Road Glide Special",
            "dyno_type": "Dynojet 224xLC",
            "engine_type": "M8 114",
            "ambient_temp_f": 72.0,
            "ambient_pressure_inhg": 29.40,
            "humidity_percent": 41.0,
            "duration_seconds": 11,
            "data_points": 1430,
        },
        "results_summary": None,
        "files": [],
        "stats": {"rows_read": 14300},
    },
    {
        "run_id": "run_jetstream_demo_error",
        "jetstream_id": "JS-GAMMA-404",
        "status": RunStatus.ERROR,
        "current_stage": "processing",
        "progress_percent": 24,
        "age_minutes": 18,
        "metadata": {
            "vehicle": "2020 Softail Standard",
            "dyno_type": "Dynojet 200",
            "engine_type": "M8 107",
            "ambient_temp_f": 75.0,
            "ambient_pressure_inhg": 29.10,
            "humidity_percent": 55.0,
        },
        "error": {
            "stage": "processing",
            "code": "VE-CSV-42",
            "message": "CSV conversion failed: missing MAP channel",
        },
        "results_summary": None,
        "files": [],
        "stats": {},
    },
]


def _ensure_stub_runs() -> None:
    manager = get_run_manager()
    for stub in _SAMPLE_RUNS:
        if manager.get_run(stub["run_id"]) is None:
            manager.create_run(
                source="jetstream",
                jetstream_id=stub.get("jetstream_id"),
                metadata=stub.get("metadata"),
                run_id=stub["run_id"],
            )
        _write_metadata(stub["run_id"], stub.get("metadata"))
        error_obj: Optional[RunError] = None
        if stub.get("error"):
            error_obj = RunError(
                stage=stub["error"]["stage"],
                code=stub["error"]["code"],
                message=stub["error"]["message"],
            )
        manager.update_run_status(
            run_id=stub["run_id"],
            status=stub["status"],
            current_stage=stub.get("current_stage"),
            progress_percent=stub.get("progress_percent"),
            error=error_obj,
            results_summary=stub.get("results_summary"),
            files=[file["name"] for file in stub.get("files", [])],
        )
        _write_stub_outputs(stub)


def _write_metadata(run_id: str, metadata: Optional[Dict[str, Any]]) -> None:
    if not metadata:
        return
    manager = get_run_manager()
    run_dir = manager.get_run_dir(run_id)
    if not run_dir:
        return
    (run_dir / "jetstream_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )


def _write_stub_outputs(stub: Dict[str, Any]) -> None:
    files = stub.get("files") or []
    if not files:
        return
    manager = get_run_manager()
    run_dir = manager.get_run_dir(stub["run_id"])
    if not run_dir:
        return
    output_dir = run_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for file_info in files:
        file_path = output_dir / file_info["name"]
        file_path.write_text(file_info.get("content", ""), encoding="utf-8")
        written.append(file_path)
    _write_manifest(stub, written)


def _write_manifest(stub: Dict[str, Any], files: List[Path]) -> None:
    manager = get_run_manager()
    run_dir = manager.get_run_dir(stub["run_id"])
    if not run_dir:
        return
    output_dir = run_dir / "output"
    start = _iso_minutes_ago(stub.get("age_minutes", 5))
    end = _iso_minutes_ago(max(stub.get("age_minutes", 5) - 1, 0))
    stats = stub.get("stats") or {}

    manifest_outputs = []
    for file_path in files:
        suffix = file_path.suffix.lower()
        file_type = "text"
        if suffix == ".csv":
            file_type = "csv"
        elif suffix == ".json":
            file_type = "json"
        manifest_outputs.append(
            {
                "name": file_path.name,
                "path": str(file_path),
                "type": file_type,
                "schema": "dynoai_stub",
                "rows": None,
                "cols": None,
                "size_bytes": file_path.stat().st_size,
                "sha256": "",
                "created": end,
            }
        )

    manifest = {
        "schema_id": "dynoai.manifest@1",
        "tool_version": "1.2.0",
        "run_id": stub["run_id"],
        "status": {"code": "success", "message": "Completed", "last_stage": "export"},
        "input": {
            "path": f"jetstream_raw/{stub['run_id']}.csv",
            "size_bytes": stats.get("rows_read", 0),
            "sha256": "",
            "dialect": {"sep": ",", "encoding": "utf-8", "newline": "auto"},
            "required_columns_present": True,
            "missing_columns": [],
        },
        "config": {"args": {"clamp": 7, "smooth_passes": 2}},
        "env": {"python": "3.11", "os": "Windows"},
        "timing": {"start": start, "end": end, "duration_ms": 42000},
        "stats": {
            "rows_read": stats.get("rows_read", 0),
            "front_accepted": stats.get("front_accepted", 0),
            "rear_accepted": stats.get("rear_accepted", 0),
        },
        "diagnostics": [],
        "outputs": manifest_outputs,
        "apply": {"allowed": True, "reasons_blocked": []},
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
