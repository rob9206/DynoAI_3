from __future__ import annotations

import csv
import hashlib
import json
import os
import platform
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jsonschema import ValidationError as JSValidationError
from jsonschema import validate as js_validate

SCHEMA_ID = "dynoai.manifest@1"
REQUIRED_COLUMNS = ("rpm", "map_kpa", "torque")


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def make_run_id(prefix: str = "") -> str:
    tail = hashlib.sha256(os.urandom(16)).hexdigest()[:6]
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    return f"{prefix}{timestamp}-{tail}" if prefix else f"{timestamp}-{tail}"


def file_sha256(path: str, bufsize: int = 65536) -> str:
    """Compute SHA256 hash of a file.
    
    Performance: Uses 64KB buffer size (optimal for most filesystems).
    Previous default was 1MB which is less efficient for smaller files.
    
    Args:
        path: Path to file to hash
        bufsize: Read buffer size in bytes (default: 64KB)
        
    Returns:
        Hexadecimal SHA256 hash string
    """
    h = hashlib.sha256()
def file_sha256(path: str, bufsize: int = 1 << 20) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(bufsize), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def safe_path(path: str, allow_parent_dir: bool = False) -> Path:
    """
    Resolves and validates a path to prevent directory traversal attacks.

    Args:
        path: The path to validate.
        allow_parent_dir: If True, allows the path to be outside the current
                          working directory's direct tree, but still resolves
                          safely. Use with extreme caution.

    Returns:
        A resolved, safe Path object.

    Raises:
        ValueError: If the path is invalid or attempts to traverse outside
                    the allowed project directory.
    """
    try:
        # Resolve the path, handling symlinks and relative components (like '..')
        # strict=False allows resolving paths that don't exist yet.
        resolved_path = Path(path).resolve(strict=False)

        # Get the project's root directory, also resolved.
        root = Path.cwd().resolve()

        # For most operations, we must ensure the path is within the project root.
        if not allow_parent_dir:
            # This is the primary security check.
            # Path.is_relative_to() was added in Python 3.9.
            # For broader compatibility, we check if the resolved path string
            # starts with the root path string.
            if not str(resolved_path).startswith(str(root)):
                raise ValueError(
                    f"Path '{path}' is outside the allowed project directory '{root}'."
                )

        return resolved_path
    except Exception as e:
        # Catch any resolution errors or our custom ValueError.
        raise ValueError(
            f"Invalid or unsafe path specified: '{path}'. Reason: {e}"
        ) from e


def write_json_atomic(data: Dict[str, Any], out_path: str) -> None:
    safe_out_path = safe_path(out_path)
    outdir = safe_out_path.parent
    outdir.mkdir(parents=True, exist_ok=True)

    # Use tempfile securely within the validated directory.
    fd, tmp = tempfile.mkstemp(prefix="._manifest_", suffix=".tmp", dir=str(outdir))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
            f.flush()
            os.fsync(f.fileno())
        # os.replace is atomic.
        os.replace(tmp, str(safe_out_path))
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def write_manifest_pair(manifest: Dict[str, Any], outdir: str, run_id: str) -> str:
    safe_outdir = safe_path(outdir)

    final_for_run = safe_outdir / f"{run_id}.manifest.json"
    latest = safe_outdir / "manifest.json"

    write_json_atomic(manifest, str(final_for_run))
    write_json_atomic(manifest, str(latest))

    return str(final_for_run)


def csv_schema_check(path: str) -> Dict[str, Any]:
    # Check if file exists before attempting to access it
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"CSV file not found: '{path}'. "
            f"Please verify the file path and ensure the file exists."
        )
    
    size = os.path.getsize(path)
    info: Dict[str, Any] = {
        "path": path,
        "size_bytes": size,
        "sha256": file_sha256(path) if size > 0 else "",
        "dialect": {"sep": ",", "encoding": "utf-8", "newline": "auto"},
        "required_columns_present": False,
        "missing_columns": [],
    }
    with open(path, "r", encoding="utf-8", newline="") as f:
        header = csv.DictReader(f).fieldnames or []
    miss = [c for c in REQUIRED_COLUMNS if c not in (header or [])]
    info["missing_columns"] = miss
    info["required_columns_present"] = len(miss) == 0
    return info


def start_manifest(
    tool_version: str,
    run_id: str,
    input_info: Dict[str, Any],
    args_cfg: Dict[str, Any],
    base_tables: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "schema_id": SCHEMA_ID,
        "tool_version": tool_version,
        "run_id": run_id,
        "session_id": session_id,
        "status": {"code": "running", "message": "Processing", "last_stage": "load"},
        "input": input_info,
        "config": {
            "args": args_cfg,
            "base_tables": base_tables or {"front": None, "rear": None},
        },
        "env": {
            "python": platform.python_version(),
            "os": platform.system(),
            "platform": platform.machine(),
            "hostname": platform.node(),
        },
        "timing": {"start": utc_now_iso(), "end": None, "duration_ms": None},
        "stats": {},
        "diagnostics": [],
        "outputs": [],
        "apply": {"allowed": False, "reasons_blocked": ["pending"]},
        "schema_id": SCHEMA_ID, "tool_version": tool_version, "run_id": run_id, "session_id": session_id,
        "status":{"code":"running","message":"Processing","last_stage":"load"},
        "input": input_info, "config":{"args":args_cfg, "base_tables": base_tables or {"front":None,"rear":None}},
        "env":{"python":platform.python_version(),"os":platform.system(),"platform":platform.machine(),"hostname":platform.node()},
        "timing":{"start": utc_now_iso(), "end": None, "duration_ms": None},
        "stats":{}, "diagnostics":{}, "outputs":[], "apply":{"allowed": False, "reasons_blocked":["pending"]}
    }


def add_output_entry(
    manifest: Dict[str, Any],
    name: str,
    path: str,
    ftype: str,
    schema: str,
    rows: Optional[int] = None,
    cols: Optional[int] = None,
):
    entry: Dict[str, Any] = {
        "name": name,
        "path": path,
        "type": ftype,
        "schema": schema,
        "rows": rows,
        "cols": cols,
        "size_bytes": os.path.getsize(path) if os.path.exists(path) else 0,
        "sha256": file_sha256(path) if os.path.exists(path) else "",
        "created": utc_now_iso(),
    }
    manifest["outputs"].append(entry)


def finish_manifest(
    manifest: Dict[str, Any],
    ok: bool,
    last_stage: str,
    message: str = "OK",
    stats: Optional[Dict[str, Any]] = None,
    diagnostics: Optional[List[Dict[str, Any]]] = None,
    apply_allowed: Optional[bool] = None,
    reasons_blocked: Optional[List[str]] = None,
) -> Dict[str, Any]:
    manifest["status"] = {
        "code": "success" if ok else ("partial" if last_stage == "export" else "error"),
        "message": message,
        "last_stage": last_stage,
    }
    if stats:
        manifest["stats"] = stats
    if diagnostics is not None:
        manifest["diagnostics"] = diagnostics
    if apply_allowed is not None:
        manifest["apply"]["allowed"] = bool(apply_allowed)
    if reasons_blocked is not None:
        manifest["apply"]["reasons_blocked"] = reasons_blocked
    start = manifest["timing"]["start"]
    manifest["timing"]["end"] = utc_now_iso()
def finish_manifest(manifest: Dict, ok: bool, last_stage: str, message: str="OK",
                    stats: Optional[Dict]=None, diagnostics: Optional[Dict]=None,
                    apply_allowed: Optional[bool]=None, reasons_blocked: Optional[List[str]]=None) -> Dict:
    manifest["status"]={"code":"success" if ok else ("partial" if last_stage=="export" else "error"),
                        "message":message,"last_stage":last_stage}
    if stats: manifest["stats"]=stats
    if diagnostics is not None: manifest["diagnostics"]=diagnostics
    if apply_allowed is not None: manifest["apply"]["allowed"]=bool(apply_allowed)
    if reasons_blocked is not None: manifest["apply"]["reasons_blocked"]=reasons_blocked
    start = manifest["timing"]["start"]; manifest["timing"]["end"]=utc_now_iso()
    try:
        start_time = datetime.fromisoformat(start.replace("Z", "+00:00"))
        end_time = datetime.fromisoformat(
            manifest["timing"]["end"].replace("Z", "+00:00")
        )
        manifest["timing"]["duration_ms"] = int(
            (end_time - start_time).total_seconds() * 1000
        )
    except Exception:
        manifest["timing"]["duration_ms"] = None
    return manifest


MANIFEST_JSON_SCHEMA_V1: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "DynoAI Run Manifest v1",
    "type": "object",
    "required": [
        "schema_id",
        "tool_version",
        "run_id",
        "status",
        "input",
        "config",
        "timing",
        "outputs",
    ],
    "properties": {
        "schema_id": {"type": "string", "const": SCHEMA_ID},
        "tool_version": {"type": "string"},
        "run_id": {"type": "string"},
        "session_id": {"type": ["string", "null"]},
        "status": {
            "type": "object",
            "required": ["code", "message", "last_stage"],
            "properties": {
                "code": {
                    "type": "string",
                    "enum": ["queued", "running", "success", "error", "partial"],
                },
                "message": {"type": "string"},
                "last_stage": {
                    "type": "string",
                    "enum": ["load", "validate", "compute", "export"],
                },
            },
        },
        "input": {
            "type": "object",
            "required": [
                "path",
                "size_bytes",
                "sha256",
                "dialect",
                "required_columns_present",
                "missing_columns",
            ],
            "properties": {
                "path": {"type": "string"},
                "size_bytes": {"type": "integer", "minimum": 0},
                "sha256": {"type": "string"},
                "dialect": {
                    "type": "object",
                    "properties": {
                        "sep": {"type": "string"},
                        "encoding": {"type": "string"},
                        "newline": {"type": "string"},
                    },
                },
                "required_columns_present": {"type": "boolean"},
                "missing_columns": {"type": "array", "items": {"type": "string"}},
            },
        },
        "config": {"type": "object"},
        "env": {"type": "object"},
        "timing": {
            "type": "object",
            "required": ["start", "end", "duration_ms"],
            "properties": {
                "start": {"type": "string"},
                "end": {"type": "string"},
                "duration_ms": {"type": ["integer", "null"], "minimum": 0},
            },
        },
        "stats": {"type": "object"},
        "diagnostics": {"type": "array"},
        "outputs": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": [
                    "name",
                    "path",
                    "type",
                    "schema",
                    "size_bytes",
                    "sha256",
                    "created",
                ],
                "properties": {
                    "name": {"type": "string"},
                    "path": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": ["csv", "json", "text", "png", "zip"],
                    },
                    "schema": {"type": "string"},
                    "rows": {"type": ["integer", "null"], "minimum": 0},
                    "cols": {"type": ["integer", "null"], "minimum": 0},
                    "size_bytes": {"type": "integer", "minimum": 0},
                    "sha256": {"type": "string"},
                    "created": {"type": "string"},
                },
            },
        },
        "apply": {
            "type": "object",
            "required": ["allowed", "reasons_blocked"],
            "properties": {
                "allowed": {"type": "boolean"},
                "reasons_blocked": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
}
MANIFEST_JSON_SCHEMA_V1 = {
  "$schema":"http://json-schema.org/draft-07/schema#","title":"DynoAI Run Manifest v1",
  "type":"object",
  "required":["schema_id","tool_version","run_id","status","input","config","timing","outputs"],
  "properties":{
    "schema_id":{"type":"string","const":SCHEMA_ID},
    "tool_version":{"type":"string"},"run_id":{"type":"string"},"session_id":{"type":["string","null"]},
    "status":{"type":"object","required":["code","message","last_stage"],
      "properties":{"code":{"type":"string","enum":["queued","running","success","error","partial"]},
                    "message":{"type":"string"},"last_stage":{"type":"string","enum":["load","validate","compute","export"]}}},
    "input":{"type":"object","required":["path","size_bytes","sha256","dialect","required_columns_present","missing_columns"],
      "properties":{"path":{"type":"string"},"size_bytes":{"type":"integer","minimum":0},
                    "sha256":{"type":"string"},"dialect":{"type":"object",
                      "properties":{"sep":{"type":"string"},"encoding":{"type":"string"},"newline":{"type":"string"}}},
                    "required_columns_present":{"type":"boolean"},
                    "missing_columns":{"type":"array","items":{"type":"string"}}}},
    "config":{"type":"object"},"env":{"type":"object"},
    "timing":{"type":"object","required":["start","end","duration_ms"],
              "properties":{"start":{"type":"string"},"end":{"type":"string"},
                            "duration_ms":{"type":["integer","null"],"minimum":0}}},
    "stats":{"type":"object"},"diagnostics":{"type":"object"},
    "outputs":{"type":"array","minItems":1,"items":{"type":"object",
      "required":["name","path","type","schema","size_bytes","sha256","created"],
      "properties":{"name":{"type":"string"},"path":{"type":"string"},
                    "type":{"type":"string","enum":["csv","json","text","png","zip"]},
                    "schema":{"type":"string"},"rows":{"type":["integer","null"],"minimum":0},
                    "cols":{"type":["integer","null"],"minimum":0},
                    "size_bytes":{"type":"integer","minimum":0},"sha256":{"type":"string"},
                    "created":{"type":"string"}}}},
    "apply":{"type":"object","required":["allowed","reasons_blocked"],
             "properties":{"allowed":{"type":"boolean"},
                           "reasons_blocked":{"type":"array","items":{"type":"string"}}}}
  }
}


def validate_manifest_schema(manifest: Dict[str, Any]) -> Tuple[bool, str]:
    try:
        js_validate(instance=manifest, schema=MANIFEST_JSON_SCHEMA_V1)
        return True, "OK"
    except JSValidationError as e:
        return False, f"Manifest schema error: {e.message}"


NUMERIC_RANGES: Dict[str, Tuple[float, float]] = {
    "rpm": (400, 8000),
    "map_kpa": (10, 110),
    "torque": (0, 300),
    "spark_f": (-10, 50),
    "spark_r": (-10, 50),
    "afr_cmd_f": (10.0, 16.5),
    "afr_cmd_r": (10.0, 16.5),
    "afr_meas_f": (9.0, 18.0),
    "afr_meas_r": (9.0, 18.0),
    "iat": (30.0, 300.0),
    "vbatt": (10.5, 15.5),
    "tps": (0.0, 100.0),
}


def validate_input_values(
    csv_path: str, sample_rows: int = 50000
) -> Tuple[bool, str, Dict[str, int]]:
    stats: Dict[str, int] = {"rows_read": 0, "nan_ct": 0, "out_of_range_ct": 0}
    try:
        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i >= sample_rows:
                    break
                stats["rows_read"] += 1
                for col, (lo, hi) in NUMERIC_RANGES.items():
                    if col not in row or row[col] in ("", None):
                        continue
                    try:
                        value = float(row[col])
                    except Exception:
                        stats["nan_ct"] += 1
                        continue
                    if not (lo <= value <= hi):
                        stats["out_of_range_ct"] += 1
        if stats["rows_read"] == 0:
            return False, "No data rows found in CSV.", stats
        if (
            stats["out_of_range_ct"] > 0
            and (stats["out_of_range_ct"] / max(1, stats["rows_read"])) > 0.05
        ):
            return (
                False,
                f"Too many out-of-range values: {stats['out_of_range_ct']}",
                stats,
            )
        return True, "OK", stats
    except FileNotFoundError:
        return False, f"CSV not found: {csv_path}", stats


def validate_outputs_against_manifest(
    outdir: str, manifest: Dict[str, Any]
) -> Tuple[bool, str]:
    safe_outdir = safe_path(outdir)

    for out in manifest.get("outputs", []):
        # Each path from the manifest is joined to the safe, validated base directory.
        path = safe_outdir / out["path"]
        if not path.exists():
            return False, f"Missing output: {out['path']}"

        size = path.stat().st_size
        if size != out["size_bytes"]:
            return (
                False,
                f"Size mismatch for {out['path']}: expected {out['size_bytes']}, got {size}",
            )

        # file_sha256 can now safely operate on the validated path.
        if file_sha256(str(path)) != out["sha256"]:
            return False, f"SHA mismatch for {out['path']}"

    return True, "OK"


def sanitize_csv_cell(value: Any) -> Any:
    """
    Sanitizes a value to prevent CSV formula injection.
    If the value is a string and starts with '=', '+', '-', or '@',
    it prepends a single quote.
    """
    if isinstance(value, str):
        if value.startswith(("=", "+", "-", "@")):
            return "'" + value
    return value
