"""Promote watched files into DynoAI run directories."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from api.services.parsers.file_index import FileType
from api.services.powercore_integration import (
    parse_powervision_log,
    powervision_log_to_dynoai_format,
)

RUN_AUTO_PREFIX = "auto"


@dataclass
class RunPromotion:
    """Result of a promotion attempt."""

    run_id: str
    run_dir: Path
    source_path: Path
    target_csv: Optional[Path]
    format: str
    bytes_copied: int
    created: bool
    reason: str

    def to_json(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["run_dir"] = str(self.run_dir)
        payload["source_path"] = str(self.source_path)
        payload["target_csv"] = str(self.target_csv) if self.target_csv else None
        return payload


def classify_csv(path: Path) -> str:
    """
    Classify CSV flavor.

    Returns one of: "powervision", "dynoai", "unknown".
    """
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            first = (handle.readline() or "").strip()
            second = (handle.readline() or "").strip()
    except OSError:
        return "unknown"

    probe = f"{first}\n{second}"
    if "Dynojet Power Vision Log File" in probe:
        return "powervision"
    if "Engine RPM" in probe:
        return "dynoai"
    return "unknown"


def derive_run_id(source_path: Path, now: datetime) -> str:
    """Build auto run id: auto/YYYYMMDD/<sanitized_stem>."""
    date_part = now.strftime("%Y%m%d")
    stem = source_path.stem.strip().lower()
    stem = re.sub(r"[^a-z0-9._-]+", "_", stem)
    stem = stem.strip("._-") or "run"
    return f"{RUN_AUTO_PREFIX}/{date_part}/{stem}"


def _manifest_path(run_dir: Path) -> Path:
    return run_dir / "manifest.json"


def _load_manifest(manifest_path: Path) -> dict[str, Any]:
    if not manifest_path.exists():
        return {}
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _source_fingerprint(path: Path) -> tuple[int, float]:
    stat = path.stat()
    return stat.st_size, stat.st_mtime


def _is_already_promoted(source_path: Path, run_dir: Path) -> bool:
    manifest = _load_manifest(_manifest_path(run_dir))
    size = manifest.get("source_size")
    mtime = manifest.get("source_mtime")
    if size is None or mtime is None:
        return False
    cur_size, cur_mtime = _source_fingerprint(source_path)
    return size == cur_size and mtime == cur_mtime


def _write_manifest(
    run_dir: Path,
    *,
    run_id: str,
    source_path: Path,
    fmt: str,
    origin: str,
) -> None:
    size, mtime = _source_fingerprint(source_path)
    manifest = {
        "run_id": run_id,
        "promoted_at": datetime.now(timezone.utc).isoformat(),
        "origin": origin,
        "format": fmt,
        "source_path": str(source_path),
        "source_size": size,
        "source_mtime": mtime,
    }
    _manifest_path(run_dir).write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _build_noop(
    run_id: str,
    run_dir: Path,
    source_path: Path,
    fmt: str,
    reason: str,
) -> RunPromotion:
    return RunPromotion(
        run_id=run_id,
        run_dir=run_dir,
        source_path=source_path,
        target_csv=run_dir / "run.csv",
        format=fmt,
        bytes_copied=0,
        created=False,
        reason=reason,
    )


def _promote_csv(source_path: Path, run_dir: Path) -> tuple[str, int]:
    fmt = classify_csv(source_path)
    target_csv = run_dir / "run.csv"

    if fmt == "powervision":
        pv = parse_powervision_log(str(source_path))
        normalized = powervision_log_to_dynoai_format(pv)
        normalized.to_csv(target_csv, index=False)
    else:
        shutil.copy2(source_path, target_csv)
        if fmt == "unknown":
            fmt = "csv_unknown"

    return fmt, target_csv.stat().st_size


def _promote_wp8(source_path: Path, run_dir: Path) -> tuple[Path, int]:
    target = run_dir / "source.wp8"
    shutil.copy2(source_path, target)
    return target, target.stat().st_size


def promote_path(path: Path, runs_dir: Path) -> RunPromotion:
    """
    Promote an absolute path into runs/<run_id>/.

    Supports .csv and .wp8 only.
    """
    source_path = path.expanduser().resolve()
    if not source_path.exists() or not source_path.is_file():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    ext = source_path.suffix.lower()
    now = datetime.now(timezone.utc)
    run_id = derive_run_id(source_path, now)
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    if _is_already_promoted(source_path, run_dir):
        return _build_noop(run_id, run_dir, source_path, ext.lstrip("."), "already_promoted")

    if ext == ".csv":
        fmt, bytes_copied = _promote_csv(source_path, run_dir)
        _write_manifest(
            run_dir,
            run_id=run_id,
            source_path=source_path,
            fmt=fmt,
            origin="watch_auto",
        )
        return RunPromotion(
            run_id=run_id,
            run_dir=run_dir,
            source_path=source_path,
            target_csv=run_dir / "run.csv",
            format=fmt,
            bytes_copied=bytes_copied,
            created=True,
            reason="promoted",
        )

    if ext == ".wp8":
        target, bytes_copied = _promote_wp8(source_path, run_dir)
        _write_manifest(
            run_dir,
            run_id=run_id,
            source_path=source_path,
            fmt="wp8",
            origin="watch_auto",
        )
        return RunPromotion(
            run_id=run_id,
            run_dir=run_dir,
            source_path=source_path,
            target_csv=target,
            format="wp8",
            bytes_copied=bytes_copied,
            created=True,
            reason="promoted",
        )

    return _build_noop(run_id, run_dir, source_path, ext.lstrip("."), "unsupported_extension")


def maybe_promote(event: dict[str, Any], runs_dir: Path) -> Optional[RunPromotion]:
    """
    Promote watcher event payload to a run directory when eligible.
    """
    file_type = (event.get("file_type") or "").lower()
    if file_type == FileType.TUNE.value:
        return None
    if file_type not in {FileType.LOG.value, FileType.WP8.value}:
        return None
    if file_type == FileType.LOG.value and not event.get("parse_ok", False):
        return None

    path_raw = event.get("path")
    if not isinstance(path_raw, str) or not path_raw.strip():
        return None

    source_path = Path(path_raw).expanduser().resolve()
    if not source_path.exists() or not source_path.is_file():
        return None

    promotion = promote_path(source_path, runs_dir=runs_dir)
    if not promotion.created and promotion.reason.startswith("unsupported"):
        return None
    return promotion

