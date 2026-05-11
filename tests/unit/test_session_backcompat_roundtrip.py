"""Backward-compatibility roundtrip for legacy session.json payloads."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from api.services.tuning_workspace import TuningWorkspace

LEGACY_SESSION_PATH = (
    Path("vehicles") / "doodledyna" / "sessions" / "20260421_233219" / "session.json"
)


def test_doodledyna_legacy_session_roundtrip():
    if not LEGACY_SESSION_PATH.exists():
        pytest.skip(f"legacy fixture missing: {LEGACY_SESSION_PATH}")

    payload = json.loads(LEGACY_SESSION_PATH.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="ws_backcompat_") as tmp:
        ws = TuningWorkspace(root=tmp)
        session = ws._coerce_session_payload(payload)  # compatibility loader coverage

    dumped = session.to_dict()
    assert dumped["id"] == payload["id"]
    assert dumped["vehicle_id"] == payload["vehicle_id"]
    assert dumped["status"] == payload["status"]
    assert dumped["active_iteration_id"] == payload["active_iteration_id"]
    assert dumped["schema_version"] is None
    assert dumped["v3"] is None
