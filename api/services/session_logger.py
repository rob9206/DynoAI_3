"""
VE Table Time Machine - Session Logger

Records every VE operation (analysis, apply, rollback) with snapshots
to enable step-by-step replay of tuning sessions.

No new math - pure orchestration, logging, and visualization.
"""

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, TypedDict
from uuid import uuid4


class VESnapshot(TypedDict):
    """A snapshot of VE table state at a point in time."""

    id: str
    timestamp: str
    source_file: str
    sha256: str
    rows: int
    cols: int


class TimelineEvent(TypedDict):
    """A single event in the session timeline."""

    id: str
    sequence: int
    type: Literal["analysis", "apply", "rollback", "baseline"]
    timestamp: str
    description: str
    snapshot_before: Optional[VESnapshot]
    snapshot_after: Optional[VESnapshot]
    metadata: Dict[str, Any]


class SessionLog(TypedDict):
    """The complete session log for a run."""

    schema_version: str
    run_id: str
    created_at: str
    updated_at: str
    events: List[TimelineEvent]
    active_snapshot_id: Optional[str]


# Schema version for future compatibility
SCHEMA_VERSION = "1.0.0"

# Maximum snapshot file size (10MB)
MAX_SNAPSHOT_SIZE_BYTES = 10 * 1024 * 1024

# Maximum number of snapshots per session (prevents disk exhaustion)
MAX_SNAPSHOTS_PER_SESSION = 100


class SessionLogger:
    """
    Records VE operations and manages session timeline.

    Usage:
        logger = SessionLogger(run_dir)
        logger.record_analysis(ve_before, ve_after, manifest)
        logger.record_apply(ve_before, ve_after, apply_metadata)
        timeline = logger.get_timeline()
    """

    def __init__(self, run_dir: Path):
        """
        Initialize session logger for a run.

        Args:
            run_dir: Path to the run directory (e.g., runs/run_123/)
        """
        self.run_dir = Path(run_dir)
        self.session_log_path = self.run_dir / "session_log.json"
        self.snapshots_dir = self.run_dir / "snapshots"

        # Ensure directories exist
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(exist_ok=True)

        # Load or create session log
        self._session_log = self._load_or_create()

    def _load_or_create(self) -> SessionLog:
        """Load existing session log or create new one."""
        if self.session_log_path.exists():
            with open(self.session_log_path, "r") as f:
                return json.load(f)

        # Create new session log
        run_id = self.run_dir.name
        now = datetime.now(timezone.utc).isoformat()

        return SessionLog(
            schema_version=SCHEMA_VERSION,
            run_id=run_id,
            created_at=now,
            updated_at=now,
            events=[],
            active_snapshot_id=None,
        )

    def _save(self) -> None:
        """Persist session log to disk."""
        self._session_log["updated_at"] = datetime.now(timezone.utc).isoformat()
        with open(self.session_log_path, "w") as f:
            json.dump(self._session_log, f, indent=2)

    def _create_snapshot(self, source_path: Path, label: str) -> VESnapshot:
        """
        Create a snapshot of a VE table file.

        Args:
            source_path: Path to the VE CSV file
            label: Human-readable label for the snapshot

        Returns:
            VESnapshot with metadata

        Raises:
            ValueError: If file is too large or too many snapshots exist
        """
        import hashlib

        # Check file size before proceeding
        file_size = source_path.stat().st_size
        if file_size > MAX_SNAPSHOT_SIZE_BYTES:
            raise ValueError(
                f"Snapshot file too large: {file_size:,} bytes "
                f"(max: {MAX_SNAPSHOT_SIZE_BYTES:,} bytes). "
                f"File: {source_path.name}"
            )

        # Check total snapshot count
        existing_snapshots = list(self.snapshots_dir.glob("*.csv"))
        if len(existing_snapshots) >= MAX_SNAPSHOTS_PER_SESSION:
            raise ValueError(
                f"Too many snapshots in session: {len(existing_snapshots)} "
                f"(max: {MAX_SNAPSHOTS_PER_SESSION}). "
                f"Consider starting a new session."
            )

        snapshot_id = f"snap_{uuid4().hex[:8]}"
        timestamp = datetime.now(timezone.utc).isoformat()

        # Copy file to snapshots directory
        dest_path = self.snapshots_dir / f"{snapshot_id}.csv"
        shutil.copy2(source_path, dest_path)

        # Compute hash and dimensions
        with open(dest_path, "rb") as f:
            sha256 = hashlib.sha256(f.read()).hexdigest()

        # Count rows/cols (quick parse)
        with open(dest_path, "r") as f:
            lines = f.readlines()
            rows = len(lines) - 1  # Minus header
            cols = len(lines[0].split(",")) - 1 if lines else 0  # Minus RPM column

        return VESnapshot(
            id=snapshot_id,
            timestamp=timestamp,
            source_file=str(source_path.name),
            sha256=sha256,
            rows=rows,
            cols=cols,
        )

    def _next_sequence(self) -> int:
        """Get next sequence number for events."""
        if not self._session_log["events"]:
            return 1
        return max(e["sequence"] for e in self._session_log["events"]) + 1

    def record_baseline(
        self, ve_path: Path, description: str = "Initial VE table baseline"
    ) -> TimelineEvent:
        """
        Record the initial baseline VE table.

        Args:
            ve_path: Path to the baseline VE CSV
            description: Event description

        Returns:
            The created TimelineEvent
        """
        snapshot = self._create_snapshot(ve_path, "baseline")

        event = TimelineEvent(
            id=f"evt_{uuid4().hex[:8]}",
            sequence=self._next_sequence(),
            type="baseline",
            timestamp=datetime.now(timezone.utc).isoformat(),
            description=description,
            snapshot_before=None,
            snapshot_after=snapshot,
            metadata={},
        )

        self._session_log["events"].append(event)
        self._session_log["active_snapshot_id"] = snapshot["id"]
        self._save()

        return event

    def record_analysis(
        self,
        correction_path: Path,
        manifest: Dict[str, Any],
        description: str = "Generated VE corrections from dyno log",
    ) -> TimelineEvent:
        """
        Record an analysis operation that generated VE corrections.

        Args:
            correction_path: Path to the VE correction delta CSV
            manifest: Analysis manifest with stats
            description: Event description

        Returns:
            The created TimelineEvent
        """
        snapshot = self._create_snapshot(correction_path, "correction_delta")

        event = TimelineEvent(
            id=f"evt_{uuid4().hex[:8]}",
            sequence=self._next_sequence(),
            type="analysis",
            timestamp=datetime.now(timezone.utc).isoformat(),
            description=description,
            snapshot_before=None,  # Analysis doesn't modify existing VE
            snapshot_after=snapshot,
            metadata={
                "rows_processed": manifest.get("stats", {}).get("rows_read", 0),
                "avg_correction": manifest.get("stats", {}).get("avg_correction"),
                "max_correction": manifest.get("stats", {}).get("max_correction"),
                "config": manifest.get("config", {}),
            },
        )

        self._session_log["events"].append(event)
        self._save()

        return event

    def record_apply(
        self,
        ve_before_path: Path,
        ve_after_path: Path,
        apply_metadata: Dict[str, Any],
        description: str = "Applied VE corrections",
    ) -> TimelineEvent:
        """
        Record a VEApply operation.

        Args:
            ve_before_path: Path to VE table before apply
            ve_after_path: Path to VE table after apply
            apply_metadata: Metadata from VEApply operation
            description: Event description

        Returns:
            The created TimelineEvent
        """
        snapshot_before = self._create_snapshot(ve_before_path, "before_apply")
        snapshot_after = self._create_snapshot(ve_after_path, "after_apply")

        event = TimelineEvent(
            id=f"evt_{uuid4().hex[:8]}",
            sequence=self._next_sequence(),
            type="apply",
            timestamp=datetime.now(timezone.utc).isoformat(),
            description=description,
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
            metadata={
                "max_adjust_pct": apply_metadata.get("max_adjust_pct"),
                "cells_modified": apply_metadata.get("cells_modified"),
                "applied_at": apply_metadata.get("applied_at_utc"),
            },
        )

        self._session_log["events"].append(event)
        self._session_log["active_snapshot_id"] = snapshot_after["id"]
        self._save()

        return event

    def record_rollback(
        self,
        ve_before_path: Path,
        ve_after_path: Path,
        rollback_info: Dict[str, Any],
        description: str = "Rolled back VE corrections",
    ) -> TimelineEvent:
        """
        Record a VERollback operation.

        Args:
            ve_before_path: Path to VE table before rollback
            ve_after_path: Path to VE table after rollback
            rollback_info: Metadata from VERollback operation
            description: Event description

        Returns:
            The created TimelineEvent
        """
        snapshot_before = self._create_snapshot(ve_before_path, "before_rollback")
        snapshot_after = self._create_snapshot(ve_after_path, "after_rollback")

        event = TimelineEvent(
            id=f"evt_{uuid4().hex[:8]}",
            sequence=self._next_sequence(),
            type="rollback",
            timestamp=datetime.now(timezone.utc).isoformat(),
            description=description,
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
            metadata={
                "rolled_back_at": rollback_info.get("rolled_back_at_utc"),
                "original_apply_at": rollback_info.get(
                    "original_apply_metadata", {}
                ).get("applied_at_utc"),
            },
        )

        self._session_log["events"].append(event)
        self._session_log["active_snapshot_id"] = snapshot_after["id"]
        self._save()

        return event

    def get_timeline(self) -> List[TimelineEvent]:
        """Get all events in chronological order."""
        return sorted(self._session_log["events"], key=lambda e: e["sequence"])

    def get_event(self, event_id: str) -> Optional[TimelineEvent]:
        """Get a specific event by ID."""
        for event in self._session_log["events"]:
            if event["id"] == event_id:
                return event
        return None

    def get_snapshot_path(self, snapshot_id: str) -> Optional[Path]:
        """Get the file path for a snapshot."""
        # Validate snapshot ID format to prevent path traversal.
        if not re.match(r"^snap_[a-f0-9]{8}$", snapshot_id):
            return None

        base = self.snapshots_dir.resolve()
        path = (base / f"{snapshot_id}.csv").resolve()
        try:
            path.relative_to(base)
        except ValueError:
            return None

        if path.exists():
            return path
        return None

    def get_snapshot_data(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """
        Load and parse snapshot data.

        Returns:
            Dict with rpm, load, and data (2D array of values)
        """
        path = self.get_snapshot_path(snapshot_id)
        if not path:
            return None

        import csv

        with open(path, "r", newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)

        if not rows:
            return None

        # Parse header (RPM, kPa values...)
        header = rows[0]
        load = [float(x) for x in header[1:]]

        # Parse data rows
        rpm = []
        data = []
        for row in rows[1:]:
            if not row or not row[0].strip():
                continue
            rpm.append(float(row[0]))
            data.append([float(x) if x.strip() else 0.0 for x in row[1:]])

        return {"rpm": rpm, "load": load, "data": data}

    def compute_diff(
        self, from_snapshot_id: str, to_snapshot_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Compute the difference between two snapshots.

        Args:
            from_snapshot_id: Earlier snapshot ID
            to_snapshot_id: Later snapshot ID

        Returns:
            Dict with rpm, load, diff (2D array), and summary stats
        """
        from_data = self.get_snapshot_data(from_snapshot_id)
        to_data = self.get_snapshot_data(to_snapshot_id)

        if not from_data or not to_data:
            return None

        # Verify dimensions match
        if from_data["rpm"] != to_data["rpm"] or from_data["load"] != to_data["load"]:
            return None

        # Compute cell-by-cell difference
        diff = []
        changes = []
        for i, (from_row, to_row) in enumerate(zip(from_data["data"], to_data["data"])):
            diff_row = []
            for j, (from_val, to_val) in enumerate(zip(from_row, to_row)):
                delta = to_val - from_val
                diff_row.append(round(delta, 4))
                if abs(delta) > 0.001:
                    changes.append(
                        {
                            "rpm": from_data["rpm"][i],
                            "load": from_data["load"][j],
                            "from": round(from_val, 4),
                            "to": round(to_val, 4),
                            "delta": round(delta, 4),
                        }
                    )
            diff.append(diff_row)

        # Summary stats
        flat_diff = [d for row in diff for d in row]
        non_zero = [d for d in flat_diff if abs(d) > 0.001]

        return {
            "rpm": from_data["rpm"],
            "load": from_data["load"],
            "diff": diff,
            "from_snapshot_id": from_snapshot_id,
            "to_snapshot_id": to_snapshot_id,
            "summary": {
                "cells_changed": len(non_zero),
                "total_cells": len(flat_diff),
                "avg_change": (
                    round(sum(non_zero) / len(non_zero), 4) if non_zero else 0
                ),
                "max_change": round(max(non_zero), 4) if non_zero else 0,
                "min_change": round(min(non_zero), 4) if non_zero else 0,
            },
            "changes": sorted(changes, key=lambda c: abs(c["delta"]), reverse=True)[
                :20
            ],  # Top 20 changes
        }

    def get_session_summary(self) -> Dict[str, Any]:
        """Get summary stats for the session."""
        events = self.get_timeline()

        return {
            "run_id": self._session_log["run_id"],
            "created_at": self._session_log["created_at"],
            "updated_at": self._session_log["updated_at"],
            "total_events": len(events),
            "event_counts": {
                "baseline": sum(1 for e in events if e["type"] == "baseline"),
                "analysis": sum(1 for e in events if e["type"] == "analysis"),
                "apply": sum(1 for e in events if e["type"] == "apply"),
                "rollback": sum(1 for e in events if e["type"] == "rollback"),
            },
            "active_snapshot_id": self._session_log["active_snapshot_id"],
        }
