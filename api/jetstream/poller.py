"""Background polling service for Jetstream runs."""

import json
import logging
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Callable, Dict, List, Optional

from io_contracts import safe_path

from .client import JetstreamClient
from .models import JetstreamConfig, JetstreamRun, PollerStatus, RunStatus

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

logger = logging.getLogger(__name__)


class JetstreamPoller:
    """Background service for polling Jetstream API for new runs."""

    def __init__(
        self,
        config: JetstreamConfig,
        on_new_run: Optional[Callable[[JetstreamRun], None]] = None,
    ):
        """
        Initialize the poller.

        Args:
            config: Jetstream configuration
            on_new_run: Callback function when a new run is discovered
        """
        self._config = config
        self._client: Optional[JetstreamClient] = None
        self._on_new_run = on_new_run
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._status = PollerStatus(connected=False)
        self._last_poll_time: Optional[datetime] = None
        self._pending_runs: List[JetstreamRun] = []
        self._processing_run: Optional[str] = None
        self._run_queue: Queue = Queue()
        self._lock = threading.Lock()

    @property
    def status(self) -> PollerStatus:
        """Get the current poller status."""
        with self._lock:
            return PollerStatus(
                connected=self._status.connected,
                last_poll=self._status.last_poll,
                next_poll=self._status.next_poll,
                pending_runs=len(self._pending_runs),
                processing_run=self._processing_run,
                error=self._status.error,
            )

    @property
    def is_running(self) -> bool:
        """Check if the poller is running."""
        return self._thread is not None and self._thread.is_alive()

    def configure(self, config: JetstreamConfig) -> None:
        """
        Update the configuration.

        Args:
            config: New configuration
        """
        was_running = self.is_running
        if was_running:
            self.stop()

        self._config = config
        self._client = None  # Reset client to use new config

        if was_running and config.enabled:
            self.start()

    def start(self) -> bool:
        """
        Start the polling service.

        Returns:
            True if started successfully
        """
        if self.is_running:
            return True

        if not self._config.enabled:
            logger.info("Jetstream poller not enabled")
            return False

        if not self._config.api_url or not self._config.api_key:
            logger.error("Jetstream API URL and key are required")
            with self._lock:
                self._status.error = "Missing API URL or key"
            return False

        # Create client
        self._client = JetstreamClient(
            base_url=self._config.api_url,
            api_key=self._config.api_key,
        )

        # Test connection
        if not self._client.test_connection():
            logger.error("Failed to connect to Jetstream API")
            with self._lock:
                self._status.error = "Failed to connect to Jetstream API"
                self._status.connected = False
            return False

        # Start polling thread
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

        with self._lock:
            self._status.connected = True
            self._status.error = None

        logger.info("Jetstream poller started")
        return True

    def stop(self) -> None:
        """Stop the polling service."""
        if not self.is_running:
            return

        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

        with self._lock:
            self._status.connected = False
            self._status.next_poll = None

        logger.info("Jetstream poller stopped")

    def restart(self) -> bool:
        """
        Restart the polling service.

        Returns:
            True if restarted successfully
        """
        self.stop()
        return self.start()

    def trigger_sync(self) -> List[str]:
        """
        Trigger an immediate poll and return new run IDs.

        Returns:
            List of newly discovered run IDs
        """
        if not self._client:
            if not self._config.api_url or not self._config.api_key:
                return []
            self._client = JetstreamClient(
                base_url=self._config.api_url,
                api_key=self._config.api_key,
            )

        new_runs = self._poll_for_runs()
        return [run.run_id for run in new_runs]

    def _poll_loop(self) -> None:
        """Main polling loop running in background thread."""
        while not self._stop_event.is_set():
            try:
                self._poll_for_runs()
            except Exception as e:
                logger.error(f"Error polling Jetstream: {e}")
                with self._lock:
                    self._status.error = str(e)

            # Calculate next poll time
            interval = self._config.poll_interval_seconds
            next_poll = datetime.now(timezone.utc).timestamp() + interval
            with self._lock:
                self._status.next_poll = datetime.fromtimestamp(
                    next_poll, tz=timezone.utc
                ).isoformat()

            # Wait for next poll or stop event
            self._stop_event.wait(timeout=interval)

    def _poll_for_runs(self) -> List[JetstreamRun]:
        """
        Poll for new runs from Jetstream.

        Returns:
            List of newly discovered runs
        """
        if not self._client:
            return []

        try:
            runs = self._client.list_runs(since=self._last_poll_time)
        except Exception as e:
            logger.error(f"Failed to list runs: {e}")
            with self._lock:
                self._status.error = str(e)
                self._status.connected = False
            return []

        # Update status
        now = datetime.now(timezone.utc)
        with self._lock:
            self._last_poll_time = now
            self._status.last_poll = now.isoformat()
            self._status.connected = True
            self._status.error = None

        # Filter out already processed runs
        new_runs = [run for run in runs if not run.processed]

        if new_runs:
            logger.info(f"Found {len(new_runs)} new runs from Jetstream")

            with self._lock:
                self._pending_runs.extend(new_runs)

            # Notify callback for each new run
            if self._on_new_run:
                for run in new_runs:
                    try:
                        self._on_new_run(run)
                    except Exception as e:
                        logger.error(f"Error in new run callback: {e}")

        return new_runs

    def get_pending_runs(self) -> List[JetstreamRun]:
        """Get the list of pending runs."""
        with self._lock:
            return list(self._pending_runs)

    def mark_run_processing(self, run_id: str) -> None:
        """Mark a run as currently being processed."""
        with self._lock:
            self._processing_run = run_id

    def mark_run_complete(self, run_id: str) -> None:
        """Mark a run as complete and remove from pending."""
        with self._lock:
            self._pending_runs = [r for r in self._pending_runs if r.run_id != run_id]
            if self._processing_run == run_id:
                self._processing_run = None

        # Mark as processed on Jetstream
        if self._client:
            try:
                self._client.mark_run_processed(run_id)
            except Exception as e:
                logger.warning(
                    f"Failed to mark run {run_id} as processed on Jetstream: {e}"
                )


# Global poller instance
_poller: Optional[JetstreamPoller] = None


def get_poller() -> Optional[JetstreamPoller]:
    """Get the global poller instance."""
    return _poller


def init_poller(
    config: JetstreamConfig, on_new_run: Optional[Callable] = None
) -> JetstreamPoller:
    """
    Initialize the global poller instance.

    Args:
        config: Jetstream configuration
        on_new_run: Callback for new runs

    Returns:
        The poller instance
    """
    global _poller
    _poller = JetstreamPoller(config, on_new_run)
    return _poller
