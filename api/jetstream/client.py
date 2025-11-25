"""JetstreamClient for communicating with the Jetstream API."""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# Add parent directory to path for io_contracts import
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from io_contracts import safe_path

from .models import JetstreamRun, JetstreamRunMetadata


class JetstreamClient:
    """Client for communicating with Dynojet's Jetstream cloud service."""

    def __init__(self, base_url: str, api_key: str):
        """
        Initialize the Jetstream client.

        Args:
            base_url: Base URL for the Jetstream API
            api_key: API key for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._timeout = 30

    def _make_request(
        self,
        endpoint: str,
        method: str = "GET",
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to the Jetstream API.

        Args:
            endpoint: API endpoint (appended to base_url)
            method: HTTP method
            data: Optional JSON data for POST/PUT requests

        Returns:
            Parsed JSON response

        Raises:
            ConnectionError: If unable to connect to the API
            ValueError: If the response is not valid JSON
        """
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        body = None
        if data:
            body = json.dumps(data).encode("utf-8")

        request = Request(url, data=body, headers=headers, method=method)

        try:
            with urlopen(request, timeout=self._timeout) as response:
                response_data = response.read().decode("utf-8")
                if response_data:
                    return json.loads(response_data)
                return {}
        except HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else str(e)
            raise ConnectionError(
                f"Jetstream API error ({e.code}): {error_body}"
            ) from e
        except URLError as e:
            raise ConnectionError(
                f"Failed to connect to Jetstream API: {e.reason}"
            ) from e
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON response from Jetstream API: {e}") from e

    def test_connection(self) -> bool:
        """
        Test the connection to the Jetstream API.

        Returns:
            True if connection is successful
        """
        try:
            self._make_request("/api/v1/health")
            return True
        except (ConnectionError, ValueError):
            return False

    def list_runs(self, since: Optional[datetime] = None) -> List[JetstreamRun]:
        """
        List available runs from the Jetstream API.

        Args:
            since: Optional datetime to filter runs after this time

        Returns:
            List of JetstreamRun objects
        """
        endpoint = "/api/v1/runs"
        if since:
            endpoint += f"?since={since.isoformat()}"

        try:
            response = self._make_request(endpoint)
        except (ConnectionError, ValueError):
            return []

        runs = []
        for run_data in response.get("runs", []):
            runs.append(
                JetstreamRun(
                    run_id=run_data.get("id", ""),
                    timestamp=run_data.get("timestamp", ""),
                    vehicle=run_data.get("vehicle"),
                    dyno_type=run_data.get("dyno_type"),
                    duration_seconds=run_data.get("duration_seconds"),
                    data_points=run_data.get("data_points"),
                    processed=run_data.get("processed", False),
                )
            )
        return runs

    def get_run_metadata(self, run_id: str) -> JetstreamRunMetadata:
        """
        Get detailed metadata for a specific run.

        Args:
            run_id: The Jetstream run ID

        Returns:
            JetstreamRunMetadata object

        Raises:
            ConnectionError: If unable to connect to the API
            ValueError: If the run is not found
        """
        endpoint = f"/api/v1/runs/{run_id}"
        response = self._make_request(endpoint)

        return JetstreamRunMetadata(
            run_id=response.get("id", run_id),
            timestamp=response.get("timestamp", ""),
            vehicle=response.get("vehicle"),
            dyno_type=response.get("dyno_type"),
            engine_type=response.get("engine_type"),
            ambient_temp_f=response.get("ambient_temp_f"),
            ambient_pressure_inhg=response.get("ambient_pressure_inhg"),
            humidity_percent=response.get("humidity_percent"),
            duration_seconds=response.get("duration_seconds"),
            data_points=response.get("data_points"),
            peak_hp=response.get("peak_hp"),
            peak_torque=response.get("peak_torque"),
            raw_data_url=response.get("raw_data_url"),
            processed=response.get("processed", False),
            extra=response.get("extra", {}),
        )

    def download_run_data(self, run_id: str, dest_path: str) -> str:
        """
        Download raw run data from Jetstream.

        Args:
            run_id: The Jetstream run ID
            dest_path: Destination path for the downloaded data
                       MUST be validated with io_contracts.safe_path

        Returns:
            Path to the downloaded file

        Raises:
            ConnectionError: If unable to download the data
            ValueError: If the path is unsafe
        """
        # Validate the destination path using io_contracts.safe_path
        safe_dest = safe_path(dest_path)

        # Ensure parent directory exists
        safe_dest.parent.mkdir(parents=True, exist_ok=True)

        endpoint = f"/api/v1/runs/{run_id}/download"
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/octet-stream",
        }

        request = Request(url, headers=headers, method="GET")

        try:
            with urlopen(request, timeout=60) as response:
                with open(safe_dest, "wb") as f:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
            return str(safe_dest)
        except HTTPError as e:
            raise ConnectionError(
                f"Failed to download run data ({e.code}): {e.read().decode('utf-8') if e.fp else str(e)}"
            ) from e
        except URLError as e:
            raise ConnectionError(
                f"Failed to download run data: {e.reason}"
            ) from e

    def mark_run_processed(self, run_id: str) -> None:
        """
        Mark a run as processed on the Jetstream server.

        Args:
            run_id: The Jetstream run ID

        Raises:
            ConnectionError: If unable to update the run
        """
        endpoint = f"/api/v1/runs/{run_id}/processed"
        self._make_request(endpoint, method="POST")
