"""Apply-endpoint tests: explicit user-confirmed PVV mutation over HTTP.

Critical safety-surface tests. Every assertion here exists to make a
specific class of failure impossible:

  - Missing confirmation token must reject (400) — guards against
    accidental client-side invocations.
  - Bad plan structure must reject (400) — guards against malformed JSON.
  - Unknown tool must reject — guards against fabricated tool names.
  - Gate failures must return success=False (200, not 500) — gate refusal
    is by-design, not a server error.
  - Successful apply must produce byte-identical SHA against the seanbike
    reference — proves the apply path doesn't drift from the same
    tool.apply() that the slice tests exercise directly.
  - Audit log must record every attempt (success and failure).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from dynoai.diagnostics.detector import DetectionContext
from dynoai.diagnostics.finding import Finding
from dynoai.tools.spark_feathered_ramp import (
    DEFAULT_TARGET_ITEM_ID,
    SparkFeatheredRampTool,
    TOOL_NAME as SPARK_TOOL,
)
from dynoai.tools.tool import ToolPlan


REPO_ROOT = Path(__file__).resolve().parents[2]
SEANBIKE_SESSION_DIR = (
    REPO_ROOT
    / "vehicles"
    / "seanbike"
    / "sessions"
    / "dai_2026_0518_pcv_bake_verify"
)
SPARK_INPUT_PVV = (
    SEANBIKE_SESSION_DIR
    / "iterations"
    / "iter_0"
    / "patches"
    / "v_pc_advanced_translation_safeavg140_gpsmooth.pvv"
)
REFERENCE_SPARK_OUTPUT_SHA = (
    "b5a69006943b65ec9a5c7dc647e32874908839b929c874b56024d1a8099a9a76"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _build_spark_plan_dict(*, output_dir: Path) -> dict:
    """Build a ToolPlan dict equivalent to what GET /patches would return.

    Uses the same defaults the seanbike script + spark_feathered_ramp test
    use, so applying this plan produces the reference SHA b5a69006...
    """
    finding = Finding(
        kind="spark_valley",
        severity=0.8,
        confidence=0.85,
        evidence={"rpm_center": 5500.0, "cylinder": "front"},
        suggested_tool=SPARK_TOOL,
        tool_params={},
        source="spark_valley_detector",
    )
    tool = SparkFeatheredRampTool()
    iter_dir = output_dir
    iter_dir.mkdir(parents=True, exist_ok=True)
    ctx = DetectionContext(
        base_pvv_path=SPARK_INPUT_PVV,
        vehicle_profile={"id": "seanbike", "tool_overrides": {}},
        iteration_dir=iter_dir,
    )
    plan = tool.plan(finding, ctx)
    return {
        "tool": plan.tool,
        "bound_params": dict(plan.bound_params),
        "input_pvv_path": str(plan.input_pvv_path),
        "output_pvv_path": str(plan.output_pvv_path),
        "predicted_cells_changed": plan.predicted_cells_changed,
        "predicted_max_delta": dict(plan.predicted_max_delta),
        "risk_score": plan.risk_score,
        "finding": {
            "kind": finding.kind,
            "severity": finding.severity,
            "confidence": finding.confidence,
            "evidence": dict(finding.evidence),
            "suggested_tool": finding.suggested_tool,
            "tool_params": dict(finding.tool_params),
            "source": finding.source,
        },
    }


# ---------------------------------------------------------------------------
# Service-layer tests (apply_patch_request) - direct, no HTTP
# ---------------------------------------------------------------------------


def test_apply_request_rejects_missing_confirmation(tmp_path):
    from api.services.patch_recommender import (
        PatchApplyRequest,
        apply_patch_request,
    )

    plan_dict = _build_spark_plan_dict(output_dir=tmp_path / "for_plan")
    req = PatchApplyRequest(
        run_id="r1",
        vehicle_id="seanbike",
        session_id="dai_2026_0518_pcv_bake_verify",
        plan_dict=plan_dict,
        confirmation="",  # missing
    )
    result = apply_patch_request(req)
    assert result.success is False
    assert "confirmation" in (result.error or "").lower()
    assert result.audit_log_path is None  # no apply attempt -> no log entry


def test_apply_request_rejects_malformed_plan(tmp_path):
    from api.services.patch_recommender import (
        APPLY_CONFIRMATION_TOKEN,
        PatchApplyRequest,
        apply_patch_request,
    )

    req = PatchApplyRequest(
        run_id="r1",
        vehicle_id="seanbike",
        session_id="dai_2026_0518_pcv_bake_verify",
        plan_dict={"tool": "spark_feathered_ramp"},  # missing required fields
        confirmation=APPLY_CONFIRMATION_TOKEN,
    )
    result = apply_patch_request(req)
    assert result.success is False
    assert "plan" in (result.error or "").lower()


def test_apply_request_rejects_unknown_tool(tmp_path):
    from api.services.patch_recommender import (
        APPLY_CONFIRMATION_TOKEN,
        PatchApplyRequest,
        apply_patch_request,
    )

    plan_dict = _build_spark_plan_dict(output_dir=tmp_path / "for_plan")
    plan_dict["tool"] = "fictional_unknown_tool"
    req = PatchApplyRequest(
        run_id="r1",
        vehicle_id="seanbike",
        session_id="dai_2026_0518_pcv_bake_verify",
        plan_dict=plan_dict,
        confirmation=APPLY_CONFIRMATION_TOKEN,
    )
    result = apply_patch_request(req)
    assert result.success is False
    assert "fictional_unknown_tool" in (result.error or "")


def test_apply_request_happy_path_matches_reference_sha(tmp_path):
    """The full apply path must produce the byte-identical seanbike SHA."""
    from api.services.patch_recommender import (
        APPLY_CONFIRMATION_TOKEN,
        PatchApplyRequest,
        apply_patch_request,
    )

    plan_dict = _build_spark_plan_dict(output_dir=tmp_path / "for_plan")
    req = PatchApplyRequest(
        run_id="apply_e2e",
        vehicle_id="seanbike",
        session_id="dai_2026_0518_pcv_bake_verify",
        plan_dict=plan_dict,
        confirmation=APPLY_CONFIRMATION_TOKEN,
    )
    result = apply_patch_request(req)

    assert result.success, f"apply failed: {result.error}"
    assert result.result_dict is not None
    assert result.result_dict["sha256"] == REFERENCE_SPARK_OUTPUT_SHA
    assert result.result_dict["cells_changed"] == 77
    assert "item_integrity" in result.result_dict["gates_passed"]
    assert result.result_dict["gates_failed"] == []
    # Audit log entry written.
    assert result.audit_log_path is not None and result.audit_log_path.exists()
    # Patch file exists at the path the manifest recorded.
    patch_path = Path(result.result_dict["patch_path"])
    assert patch_path.exists()
    assert _sha256(patch_path) == REFERENCE_SPARK_OUTPUT_SHA


def test_apply_request_gate_failure_returns_success_false_not_exception(tmp_path):
    """An overcommit plan must abort cleanly (success=False) — not raise."""
    from api.services.patch_recommender import (
        APPLY_CONFIRMATION_TOKEN,
        PatchApplyRequest,
        apply_patch_request,
    )

    plan_dict = _build_spark_plan_dict(output_dir=tmp_path / "for_plan")
    # Override the ramp to one that trips the per-cell spark clamp gate.
    plan_dict["bound_params"]["ramp"] = [(4.5, 0.0), (5.0, 2.0), (5.5, 5.0), (6.0, 10.0)]
    plan_dict["bound_params"]["max_retard_deg"] = 3.0
    # The plan's predicted_max_delta would also need to match what the tool
    # computes from this ramp, so re-derive it via a fresh plan call would
    # be necessary in a real flow. Here we deliberately set it high enough
    # that plan/apply parity passes — we want the SparkClampGate to fire,
    # not plan-parity. predicted_cells_changed stays the same (77 cells).
    plan_dict["predicted_max_delta"] = {"spark_deg": 10.0}

    req = PatchApplyRequest(
        run_id="apply_overcommit",
        vehicle_id="seanbike",
        session_id="dai_2026_0518_pcv_bake_verify",
        plan_dict=plan_dict,
        confirmation=APPLY_CONFIRMATION_TOKEN,
    )
    result = apply_patch_request(req)

    assert result.success is False, "overcommit must fail the gate, not succeed"
    assert result.result_dict is not None
    gate_failures = result.result_dict["gates_failed"]
    assert any(gf["gate"] == "spark_clamp" for gf in gate_failures)
    # Audit log STILL records the attempt even though no patch was written.
    assert result.audit_log_path is not None and result.audit_log_path.exists()
    # No patch file at the planned output path.
    output_path = Path(plan_dict["output_pvv_path"])
    assert output_path.exists() is False


def test_audit_log_appends_one_jsonl_line_per_attempt(tmp_path):
    """Two apply attempts must produce two JSONL entries in the audit log."""
    from api.services.patch_recommender import (
        APPLY_CONFIRMATION_TOKEN,
        PatchApplyRequest,
        apply_patch_request,
    )

    plan_dict = _build_spark_plan_dict(output_dir=tmp_path / "for_plan")
    req = PatchApplyRequest(
        run_id="apply_audit",
        vehicle_id="seanbike",
        session_id="dai_2026_0518_pcv_bake_verify",
        plan_dict=plan_dict,
        confirmation=APPLY_CONFIRMATION_TOKEN,
    )
    result_a = apply_patch_request(req)
    result_b = apply_patch_request(req)
    assert result_a.success and result_b.success
    # Both attempts land in the same audit log (session-active iteration_dir).
    assert result_a.audit_log_path == result_b.audit_log_path
    entries = [
        json.loads(line)
        for line in result_a.audit_log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(entries) >= 2
    for entry in entries[-2:]:
        assert entry["run_id"] == "apply_audit"
        assert entry["vehicle_id"] == "seanbike"
        assert entry["result"]["success"] is True
        assert entry["result"]["sha256"] == REFERENCE_SPARK_OUTPUT_SHA


# ---------------------------------------------------------------------------
# ToolPlan round-trip (the JSON contract between /patches and /patches/apply)
# ---------------------------------------------------------------------------


def test_finding_from_dict_round_trip():
    original = Finding(
        kind="spark_valley",
        severity=0.5,
        confidence=0.8,
        evidence={"rpm_center": 5500.0},
        suggested_tool="spark_feathered_ramp",
        tool_params={"load_min_kpa": 70.0},
        source="spark_valley_detector",
    )
    d = {
        "kind": original.kind,
        "severity": original.severity,
        "confidence": original.confidence,
        "evidence": dict(original.evidence),
        "suggested_tool": original.suggested_tool,
        "tool_params": dict(original.tool_params),
        "source": original.source,
        # rank_score field on the wire (from _finding_to_dict) must be ignored
        # by from_dict, since it's a derived property.
        "rank_score": original.rank_score(),
    }
    restored = Finding.from_dict(d)
    assert restored.kind == original.kind
    assert restored.severity == original.severity
    assert restored.confidence == original.confidence
    assert dict(restored.evidence) == dict(original.evidence)
    assert restored.suggested_tool == original.suggested_tool
    assert dict(restored.tool_params) == dict(original.tool_params)
    assert restored.source == original.source


def test_tool_plan_from_dict_round_trip(tmp_path):
    """Equivalent JSON round-trip for the full ToolPlan structure."""
    plan_dict = _build_spark_plan_dict(output_dir=tmp_path / "for_plan")
    restored = ToolPlan.from_dict(plan_dict)
    assert restored.tool == plan_dict["tool"]
    assert restored.predicted_cells_changed == plan_dict["predicted_cells_changed"]
    assert restored.input_pvv_path == Path(plan_dict["input_pvv_path"])
    assert restored.output_pvv_path == Path(plan_dict["output_pvv_path"])
    assert restored.finding.kind == plan_dict["finding"]["kind"]
    assert dict(restored.bound_params) == dict(plan_dict["bound_params"])


def test_tool_plan_from_dict_rejects_missing_finding():
    with pytest.raises(ValueError, match="finding"):
        ToolPlan.from_dict({
            "tool": "spark_feathered_ramp",
            "bound_params": {},
            "input_pvv_path": "x",
            "output_pvv_path": "y",
            "predicted_cells_changed": 0,
            "predicted_max_delta": {},
        })


# ---------------------------------------------------------------------------
# HTTP layer (Flask test client) -- /api/nextgen/<run_id>/patches/apply
# ---------------------------------------------------------------------------


@pytest.fixture
def flask_client():
    """Minimal Flask app with just the nextgen blueprint loaded."""
    from flask import Flask
    from api.routes.nextgen import nextgen_bp

    app = Flask(__name__)
    app.register_blueprint(nextgen_bp)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_http_apply_rejects_missing_body(flask_client):
    resp = flask_client.post("/api/nextgen/apply_run/patches/apply")
    assert resp.status_code == 400


def test_http_apply_rejects_missing_confirmation(flask_client, tmp_path):
    plan_dict = _build_spark_plan_dict(output_dir=tmp_path / "for_plan")
    resp = flask_client.post(
        "/api/nextgen/apply_run/patches/apply",
        json={
            "vehicle_id": "seanbike",
            "session_id": "dai_2026_0518_pcv_bake_verify",
            "plan": plan_dict,
            # no confirmation
        },
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False
    assert "confirmation" in body["error"].lower()


def test_http_apply_rejects_invalid_session_id(flask_client, tmp_path):
    plan_dict = _build_spark_plan_dict(output_dir=tmp_path / "for_plan")
    resp = flask_client.post(
        "/api/nextgen/apply_run/patches/apply",
        json={
            "vehicle_id": "seanbike",
            "session_id": "../../etc/passwd",  # path traversal attempt
            "plan": plan_dict,
            "confirmation": "apply_patch",
        },
    )
    assert resp.status_code == 400


def test_http_apply_happy_path_returns_reference_sha(flask_client, tmp_path):
    plan_dict = _build_spark_plan_dict(output_dir=tmp_path / "for_plan")
    resp = flask_client.post(
        "/api/nextgen/apply_http_e2e/patches/apply",
        json={
            "vehicle_id": "seanbike",
            "session_id": "dai_2026_0518_pcv_bake_verify",
            "plan": plan_dict,
            "confirmation": "apply_patch",
        },
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["result"]["sha256"] == REFERENCE_SPARK_OUTPUT_SHA
    assert body["audit_log_path"]
    assert body["context"]["tool"] == SPARK_TOOL


def test_http_apply_gate_failure_returns_200_with_success_false(flask_client, tmp_path):
    plan_dict = _build_spark_plan_dict(output_dir=tmp_path / "for_plan")
    plan_dict["bound_params"]["ramp"] = [(4.5, 0.0), (5.0, 2.0), (5.5, 5.0), (6.0, 10.0)]
    plan_dict["bound_params"]["max_retard_deg"] = 3.0
    plan_dict["predicted_max_delta"] = {"spark_deg": 10.0}

    resp = flask_client.post(
        "/api/nextgen/apply_overcommit_http/patches/apply",
        json={
            "vehicle_id": "seanbike",
            "session_id": "dai_2026_0518_pcv_bake_verify",
            "plan": plan_dict,
            "confirmation": "apply_patch",
        },
    )
    # 200, not 500 — gate failure is by-design, not a server error.
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is False
    assert any(
        gf["gate"] == "spark_clamp" for gf in body["result"]["gates_failed"]
    )
