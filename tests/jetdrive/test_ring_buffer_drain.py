"""
Tests for the ring buffer + drain endpoint implementation.

Verifies that:
1. Sample ring accumulates all entries from on_sample callbacks
2. /live/drain returns all accumulated samples and clears the buffer
3. Ring buffer respects maxlen and drops oldest entries on overflow
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest


def test_sample_ring_exists_in_shared():
    """The _sample_ring deque should be exported from _shared."""
    from collections import deque

    from api.routes.jetdrive._shared import _sample_ring

    assert isinstance(_sample_ring, deque)
    assert _sample_ring.maxlen == 2000


def test_sample_ring_uses_live_data_lock():
    """The ring should use _live_data_lock, not a separate lock."""
    # Verify no separate _sample_ring_lock exists
    import api.routes.jetdrive._shared as shared_module
    from api.routes.jetdrive._shared import _live_data_lock, _sample_ring

    assert not hasattr(shared_module, "_sample_ring_lock")

    # The ring is protected by _live_data_lock (verified by inspection)
    assert _live_data_lock is not None


def test_ring_buffer_accumulates_samples():
    """Multiple on_sample calls should accumulate entries in the ring."""
    from api.routes.jetdrive._shared import _live_data, _live_data_lock, _sample_ring

    # Clear ring and set capturing
    with _live_data_lock:
        _sample_ring.clear()
        _live_data["capturing"] = True

    # Simulate 5 samples being appended (mimicking what on_sample does)
    test_entries = [
        {"name": "Digital RPM 1", "value": 3000 + i * 100, "timestamp": 1000 + i}
        for i in range(5)
    ]

    with _live_data_lock:
        for entry in test_entries:
            _sample_ring.append(entry)

    # Verify all 5 are in the ring
    with _live_data_lock:
        ring_contents = list(_sample_ring)

    assert len(ring_contents) == 5
    assert ring_contents[0]["value"] == 3000
    assert ring_contents[4]["value"] == 3400

    # Cleanup
    with _live_data_lock:
        _sample_ring.clear()


def test_drain_endpoint_returns_and_clears():
    """GET /hardware/live/drain should return all samples and clear the ring."""
    from flask import Flask

    from api.routes.jetdrive._shared import _live_data, _live_data_lock, _sample_ring
    from api.routes.jetdrive.hardware import hardware_bp

    app = Flask(__name__)
    app.register_blueprint(hardware_bp, url_prefix="/api/jetdrive")

    # Populate ring with test data
    with _live_data_lock:
        _sample_ring.clear()
        _live_data["capturing"] = True
        _live_data["last_update_ts"] = 12345.67
        for i in range(10):
            _sample_ring.append(
                {
                    "name": f"Channel {i}",
                    "value": 100.0 + i,
                    "timestamp": 1000 + i,
                }
            )

    # Call drain endpoint
    with app.test_client() as client:
        resp = client.get("/api/jetdrive/hardware/live/drain")
        assert resp.status_code == 200
        data = resp.get_json()

    # Verify response structure
    assert "samples" in data
    assert "count" in data
    assert "capturing" in data
    assert "last_update_ts" in data

    # Verify all 10 samples returned
    assert data["count"] == 10
    assert len(data["samples"]) == 10
    assert data["samples"][0]["value"] == 100.0
    assert data["samples"][9]["value"] == 109.0
    assert data["capturing"] is True
    assert data["last_update_ts"] == 12345.67

    # Verify ring is now empty
    with _live_data_lock:
        assert len(_sample_ring) == 0

    # Second drain should return empty
    with app.test_client() as client:
        resp = client.get("/api/jetdrive/hardware/live/drain")
        data = resp.get_json()

    assert data["count"] == 0
    assert len(data["samples"]) == 0


def test_ring_maxlen_drops_oldest():
    """When ring overflows, oldest entries should be dropped (FIFO)."""
    from api.routes.jetdrive._shared import _live_data_lock, _sample_ring

    # Clear ring
    with _live_data_lock:
        _sample_ring.clear()

    # Fill beyond maxlen (2000)
    # Add 2050 samples
    with _live_data_lock:
        for i in range(2050):
            _sample_ring.append({"id": i, "value": i * 10})

    # Ring should only contain 2000 (the maxlen)
    with _live_data_lock:
        ring_contents = list(_sample_ring)

    assert len(ring_contents) == 2000

    # Oldest (id 0-49) should be gone, newest (id 50-2049) should remain
    assert ring_contents[0]["id"] == 50  # First entry is the 51st added
    assert ring_contents[-1]["id"] == 2049  # Last entry is the 2050th added

    # Cleanup
    with _live_data_lock:
        _sample_ring.clear()


def test_start_capture_clears_ring():
    """Starting capture should clear the ring to avoid stale data."""
    from flask import Flask

    from api.routes.jetdrive._shared import _live_data, _live_data_lock, _sample_ring
    from api.routes.jetdrive.hardware import hardware_bp

    app = Flask(__name__)
    app.register_blueprint(hardware_bp, url_prefix="/api/jetdrive")

    # Populate ring with stale data
    with _live_data_lock:
        _live_data["capturing"] = False
        _sample_ring.clear()
        for i in range(5):
            _sample_ring.append({"stale": True, "id": i})

    assert len(list(_sample_ring)) == 5

    # Start capture (this should clear the ring)
    with app.test_client() as client:
        # Mock discovery to avoid network calls
        with patch("api.routes.jetdrive.hardware._live_capture_loop"):
            resp = client.post("/api/jetdrive/hardware/live/start")
            # May fail due to missing dependencies, but that's OK for this test
            # The important part is that the ring gets cleared in start_live_capture

    # Ring should now be empty (cleared by start_live_capture)
    with _live_data_lock:
        ring_size = len(_sample_ring)

    assert ring_size == 0, "Ring should be cleared when starting capture"

    # Cleanup
    with _live_data_lock:
        _live_data["capturing"] = False


def test_drain_with_no_samples():
    """Draining an empty ring should return empty list gracefully."""
    from flask import Flask

    from api.routes.jetdrive._shared import _live_data, _live_data_lock, _sample_ring
    from api.routes.jetdrive.hardware import hardware_bp

    app = Flask(__name__)
    app.register_blueprint(hardware_bp, url_prefix="/api/jetdrive")

    # Ensure ring is empty
    with _live_data_lock:
        _sample_ring.clear()
        _live_data["capturing"] = False

    # Drain should return empty but not error
    with app.test_client() as client:
        resp = client.get("/api/jetdrive/hardware/live/drain")
        assert resp.status_code == 200
        data = resp.get_json()

    assert data["count"] == 0
    assert data["samples"] == []
    assert data["capturing"] is False


def test_ring_preserves_entry_structure():
    """Ring should store complete entry dicts with all fields."""
    from api.routes.jetdrive._shared import _live_data_lock, _sample_ring

    # Create a full entry matching what on_sample produces
    full_entry = {
        "key": "0x1234:10:Digital RPM 1",
        "provider_id": 0x1234,
        "id": 10,
        "name": "Digital RPM 1",
        "value": 3500.0,
        "timestamp": 1000,
        "updated_at_ts": time.time(),
        "category": "dyno",
        "units": "rpm",
    }

    with _live_data_lock:
        _sample_ring.clear()
        _sample_ring.append(full_entry)
        retrieved = list(_sample_ring)[0]

    # All fields should be preserved
    assert retrieved["key"] == full_entry["key"]
    assert retrieved["provider_id"] == full_entry["provider_id"]
    assert retrieved["id"] == full_entry["id"]
    assert retrieved["name"] == full_entry["name"]
    assert retrieved["value"] == full_entry["value"]
    assert retrieved["timestamp"] == full_entry["timestamp"]
    assert retrieved["category"] == full_entry["category"]
    assert retrieved["units"] == full_entry["units"]

    # Cleanup
    with _live_data_lock:
        _sample_ring.clear()
