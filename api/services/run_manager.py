"""Run lifecycle management service."""

import json
import os
import sys
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent directory to path for io_contracts import
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from io_contracts import safe_path, make_run_id, utc_now_iso

# Import models
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jetstream.models import RunError, RunState, RunStatus


class RunManager:
    """
    Manages the lifecycle of runs in the DynoAI system.

    Run directory structure:
    runs/{run_id}/
    ├── run_state.json
    ├── jetstream_metadata.json
    ├── jetstream_raw/
    ├── input/dynoai_input.csv
    └── output/
    """

    def __init__(self, runs_dir: str = "runs"):
        """
        Initialize the run manager.

        Args:
            runs_dir: Base directory for storing runs
        """
        self._runs_dir = safe_path(runs_dir)
        self._runs_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._runs_dir / "index.json"

    def create_run(
        self,
        source: str,
        jetstream_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RunState:
        """
        Create a new run directory structure.

        Args:
            source: Source of the run ('jetstream' or 'manual_upload')
            jetstream_id: Optional Jetstream run ID
            metadata: Optional metadata to store

        Returns:
            The created RunState
        """
        run_id = make_run_id(prefix="run_")
        run_dir = self._runs_dir / run_id

        # Create directory structure
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "jetstream_raw").mkdir(exist_ok=True)
        (run_dir / "input").mkdir(exist_ok=True)
        (run_dir / "output").mkdir(exist_ok=True)

        now = utc_now_iso()
        state = RunState(
            run_id=run_id,
            status=RunStatus.PENDING,
            source=source,
            created_at=now,
            updated_at=now,
            jetstream_id=jetstream_id,
        )

        # Save run state
        self._save_run_state(run_id, state)

        # Save jetstream metadata if provided
        if metadata:
            self._save_jetstream_metadata(run_id, metadata)

        # Update index
        self._update_index()

        return state

    def get_run(self, run_id: str) -> Optional[RunState]:
        """
        Get the state of a run.

        Args:
            run_id: The run ID

        Returns:
            RunState if found, None otherwise
        """
        run_dir = self._runs_dir / run_id
        state_path = run_dir / "run_state.json"

        if not state_path.exists():
            return None

        try:
            with open(state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return RunState.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return None

    def get_run_dir(self, run_id: str) -> Optional[Path]:
        """
        Get the directory path for a run.

        Args:
            run_id: The run ID

        Returns:
            Path to run directory if exists, None otherwise
        """
        run_dir = self._runs_dir / run_id
        if run_dir.exists():
            return run_dir
        return None

    def update_run_status(
        self,
        run_id: str,
        status: RunStatus,
        current_stage: Optional[str] = None,
        progress_percent: Optional[int] = None,
        error: Optional[RunError] = None,
        results_summary: Optional[Dict[str, Any]] = None,
        files: Optional[List[str]] = None,
    ) -> Optional[RunState]:
        """
        Update the status of a run.

        Args:
            run_id: The run ID
            status: New status
            current_stage: Current processing stage
            progress_percent: Progress percentage (0-100)
            error: Error information if status is ERROR
            results_summary: Summary of results if complete
            files: List of output files

        Returns:
            Updated RunState if found, None otherwise
        """
        state = self.get_run(run_id)
        if not state:
            return None

        state.status = status
        state.updated_at = utc_now_iso()

        if current_stage is not None:
            state.current_stage = current_stage
        if progress_percent is not None:
            state.progress_percent = progress_percent
        if error is not None:
            state.error = error
        if results_summary is not None:
            state.results_summary = results_summary
        if files is not None:
            state.files = files

        self._save_run_state(run_id, state)
        self._update_index()

        return state

    def list_runs(
        self,
        status: Optional[RunStatus] = None,
        source: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        List runs with optional filtering.

        Args:
            status: Filter by status
            source: Filter by source
            limit: Maximum number of runs to return
            offset: Number of runs to skip

        Returns:
            Dictionary with 'runs' list and 'total' count
        """
        all_runs = []

        # Read from index if available
        if self._index_path.exists():
            try:
                with open(self._index_path, "r", encoding="utf-8") as f:
                    index_data = json.load(f)
                all_runs = index_data.get("runs", [])
            except (json.JSONDecodeError, IOError):
                # Fall back to scanning directories
                all_runs = self._scan_runs()
        else:
            all_runs = self._scan_runs()

        # Apply filters
        filtered = all_runs
        if status:
            status_val = status.value if isinstance(status, RunStatus) else status
            filtered = [r for r in filtered if r.get("status") == status_val]
        if source:
            filtered = [r for r in filtered if r.get("source") == source]

        # Sort by created_at descending
        filtered.sort(key=lambda r: r.get("created_at", ""), reverse=True)

        total = len(filtered)
        runs = filtered[offset : offset + limit]

        return {"runs": runs, "total": total}

    def get_run_input_path(self, run_id: str) -> Optional[Path]:
        """Get the input CSV path for a run."""
        run_dir = self.get_run_dir(run_id)
        if run_dir:
            return run_dir / "input" / "dynoai_input.csv"
        return None

    def get_run_output_dir(self, run_id: str) -> Optional[Path]:
        """Get the output directory for a run."""
        run_dir = self.get_run_dir(run_id)
        if run_dir:
            return run_dir / "output"
        return None

    def get_run_raw_dir(self, run_id: str) -> Optional[Path]:
        """Get the raw data directory for a run."""
        run_dir = self.get_run_dir(run_id)
        if run_dir:
            return run_dir / "jetstream_raw"
        return None

    def delete_run(self, run_id: str) -> bool:
        """
        Delete a run and all its data.

        Args:
            run_id: The run ID

        Returns:
            True if deleted, False if not found
        """
        run_dir = self._runs_dir / run_id
        if not run_dir.exists():
            return False

        shutil.rmtree(run_dir)
        self._update_index()
        return True

    def _save_run_state(self, run_id: str, state: RunState) -> None:
        """Save run state to JSON file."""
        run_dir = self._runs_dir / run_id
        state_path = run_dir / "run_state.json"
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state.to_dict(), f, indent=2)

    def _save_jetstream_metadata(self, run_id: str, metadata: Dict[str, Any]) -> None:
        """Save Jetstream metadata to JSON file."""
        run_dir = self._runs_dir / run_id
        metadata_path = run_dir / "jetstream_metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

    def _scan_runs(self) -> List[Dict[str, Any]]:
        """Scan run directories and collect state data."""
        runs = []
        if not self._runs_dir.exists():
            return runs

        for run_dir in self._runs_dir.iterdir():
            if not run_dir.is_dir():
                continue
            if run_dir.name == "index.json":
                continue

            state_path = run_dir / "run_state.json"
            if state_path.exists():
                try:
                    with open(state_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    runs.append(data)
                except (json.JSONDecodeError, IOError):
                    continue

        return runs

    def _update_index(self) -> None:
        """Rebuild the index.json file."""
        runs = self._scan_runs()
        runs.sort(key=lambda r: r.get("created_at", ""), reverse=True)

        index_data = {
            "updated_at": utc_now_iso(),
            "total": len(runs),
            "runs": runs,
        }

        with open(self._index_path, "w", encoding="utf-8") as f:
            json.dump(index_data, f, indent=2)


# Global run manager instance
_run_manager: Optional[RunManager] = None


def get_run_manager() -> RunManager:
    """Get or create the global run manager instance."""
    global _run_manager
    if _run_manager is None:
        _run_manager = RunManager()
    return _run_manager
