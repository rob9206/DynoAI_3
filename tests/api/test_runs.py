"""
Tests for /api/runs and /api/runs/<run_id> endpoints.

Covers:
- Customer can only see their own runs
- Tech can see all runs
- Owner can see all runs
- GET /api/runs returns correct shape
- GET /api/runs/{run_id} returns 403 for wrong customer
- Pagination (limit/offset)
- Status filter
- Unauthenticated request returns 401
"""

import os
import sys
from pathlib import Path

import pytest
from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.models.base import Base
from api.models.run import Run
from api.models.user import User
from api.routes.auth import _encode_token, auth_bp
from api.routes.runs import runs_bp

_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

os.environ.setdefault("DYNOAI_DEBUG", "false")
os.environ.setdefault("JETSTREAM_STUB_MODE", "true")
os.environ.setdefault("JETSTREAM_ENABLED", "false")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("SECRET_KEY", "test-jwt-secret-key-for-testing-only")

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def runs_app(tmp_path):
    """Isolated Flask app with an in-memory SQLite DB for runs endpoint tests."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(auth_bp)
    app.register_blueprint(runs_bp)

    db_path = f"sqlite:///{tmp_path}/test_runs.db"
    engine = create_engine(db_path, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)

    # Patch the SessionLocal used by runs and auth blueprints
    import api.routes.auth as auth_module
    import api.routes.runs as runs_module

    original_auth_session = auth_module.SessionLocal
    original_runs_session = runs_module.SessionLocal

    auth_module.SessionLocal = TestSession
    runs_module.SessionLocal = TestSession

    yield app

    auth_module.SessionLocal = original_auth_session
    runs_module.SessionLocal = original_runs_session

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def client(runs_app):
    with runs_app.test_client() as c:
        yield c


def _create_user(session_factory, email, role, name=None):
    """Helper: create a user and return (user_dict, token)."""
    with session_factory() as session:
        u = User(
            email=email,
            name=name or email.split("@")[0],
            role=role,
        )
        u.set_password("password12345")
        session.add(u)
        session.commit()
        session.refresh(u)
        user_dict = u.to_dict()
    token = _encode_token(user_dict["id"])
    return user_dict, token


def _create_run(session_factory,
                user_id,
                run_id=None,
                status="queued",
                input_file="test.csv"):
    """Helper: create a Run record and return its run_id."""
    import uuid as _uuid

    rid = run_id or str(_uuid.uuid4())
    with session_factory() as session:
        session.add(
            Run(
                run_id=rid,
                user_id=user_id,
                status=status,
                input_file=input_file,
            ))
        session.commit()
    return rid


# ---------------------------------------------------------------------------
# Unauthenticated access
# ---------------------------------------------------------------------------


class TestUnauthenticatedAccess:

    def test_list_runs_without_token_returns_401(self, client):
        resp = client.get("/api/runs")
        assert resp.status_code == 401

    def test_get_run_without_token_returns_401(self, client):
        resp = client.get("/api/runs/some-run-id")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------


class TestResponseShape:

    def test_list_runs_returns_correct_shape(self, runs_app, client):
        import api.routes.runs as runs_module

        owner, token = _create_user(runs_module.SessionLocal,
                                    "owner@example.com", "owner")
        _create_run(runs_module.SessionLocal, owner["id"], status="completed")

        resp = client.get("/api/runs",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

        data = resp.get_json()
        assert "runs" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert isinstance(data["runs"], list)

    def test_run_object_has_expected_fields(self, runs_app, client):
        import api.routes.runs as runs_module

        owner, token = _create_user(runs_module.SessionLocal,
                                    "owner2@example.com", "owner")
        _create_run(runs_module.SessionLocal,
                    owner["id"],
                    run_id="shape-test-run")

        resp = client.get("/api/runs",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        runs = resp.get_json()["runs"]
        assert len(runs) >= 1
        run = runs[0]

        for field in (
                "runId",
                "userId",
                "userEmail",
                "userName",
                "status",
                "inputFile",
                "createdAt",
                "completedAt",
                "rowsProcessed",
                "correctionsApplied",
                "analysisMetrics",
                "outputFiles",
        ):
            assert field in run, f"Missing field: {field}"

        assert "avgCorrection" in run["analysisMetrics"]
        assert "maxCorrection" in run["analysisMetrics"]


# ---------------------------------------------------------------------------
# Role-based access
# ---------------------------------------------------------------------------


class TestCustomerSeesOnlyOwnRuns:

    def test_customer_only_sees_own_runs(self, runs_app, client):
        import api.routes.runs as runs_module

        customer1, tok1 = _create_user(runs_module.SessionLocal,
                                       "c1@example.com", "customer")
        customer2, tok2 = _create_user(runs_module.SessionLocal,
                                       "c2@example.com", "customer")

        _create_run(runs_module.SessionLocal,
                    customer1["id"],
                    run_id="run-c1-001")
        _create_run(runs_module.SessionLocal,
                    customer2["id"],
                    run_id="run-c2-001")

        resp = client.get("/api/runs",
                          headers={"Authorization": f"Bearer {tok1}"})
        assert resp.status_code == 200
        runs = resp.get_json()["runs"]
        run_ids = [r["runId"] for r in runs]
        assert "run-c1-001" in run_ids
        assert "run-c2-001" not in run_ids

    def test_customer_total_reflects_own_runs_only(self, runs_app, client):
        import api.routes.runs as runs_module

        customer, token = _create_user(runs_module.SessionLocal,
                                       "solo@example.com", "customer")
        other, _ = _create_user(runs_module.SessionLocal, "other@example.com",
                                "customer")

        _create_run(runs_module.SessionLocal,
                    customer["id"],
                    run_id="run-solo-1")
        _create_run(runs_module.SessionLocal,
                    customer["id"],
                    run_id="run-solo-2")
        _create_run(runs_module.SessionLocal,
                    other["id"],
                    run_id="run-other-1")

        resp = client.get("/api/runs",
                          headers={"Authorization": f"Bearer {token}"})
        data = resp.get_json()
        assert data["total"] == 2


class TestTechSeesAllRuns:

    def test_tech_sees_all_runs(self, runs_app, client):
        import api.routes.runs as runs_module

        tech, tok = _create_user(runs_module.SessionLocal, "tech@example.com",
                                 "tech")
        customer, _ = _create_user(runs_module.SessionLocal,
                                   "cust@example.com", "customer")

        _create_run(runs_module.SessionLocal, tech["id"], run_id="run-tech-1")
        _create_run(runs_module.SessionLocal,
                    customer["id"],
                    run_id="run-cust-1")

        resp = client.get("/api/runs",
                          headers={"Authorization": f"Bearer {tok}"})
        assert resp.status_code == 200
        run_ids = [r["runId"] for r in resp.get_json()["runs"]]
        assert "run-tech-1" in run_ids
        assert "run-cust-1" in run_ids


class TestOwnerSeesAllRuns:

    def test_owner_sees_all_runs(self, runs_app, client):
        import api.routes.runs as runs_module

        owner, tok = _create_user(runs_module.SessionLocal,
                                  "owner@example.com", "owner")
        customer, _ = _create_user(runs_module.SessionLocal,
                                   "cust2@example.com", "customer")

        _create_run(runs_module.SessionLocal,
                    owner["id"],
                    run_id="run-owner-1")
        _create_run(runs_module.SessionLocal,
                    customer["id"],
                    run_id="run-cust-2")

        resp = client.get("/api/runs",
                          headers={"Authorization": f"Bearer {tok}"})
        assert resp.status_code == 200
        run_ids = [r["runId"] for r in resp.get_json()["runs"]]
        assert "run-owner-1" in run_ids
        assert "run-cust-2" in run_ids


# ---------------------------------------------------------------------------
# Single-run endpoint
# ---------------------------------------------------------------------------


class TestGetSingleRun:

    def test_owner_can_get_any_run(self, runs_app, client):
        import api.routes.runs as runs_module

        owner, tok = _create_user(runs_module.SessionLocal,
                                  "owner3@example.com", "owner")
        customer, _ = _create_user(runs_module.SessionLocal,
                                   "cust3@example.com", "customer")
        _create_run(runs_module.SessionLocal,
                    customer["id"],
                    run_id="run-single-1")

        resp = client.get("/api/runs/run-single-1",
                          headers={"Authorization": f"Bearer {tok}"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["runId"] == "run-single-1"

    def test_customer_can_get_own_run(self, runs_app, client):
        import api.routes.runs as runs_module

        customer, tok = _create_user(runs_module.SessionLocal,
                                     "cust4@example.com", "customer")
        _create_run(runs_module.SessionLocal,
                    customer["id"],
                    run_id="run-own-1")

        resp = client.get("/api/runs/run-own-1",
                          headers={"Authorization": f"Bearer {tok}"})
        assert resp.status_code == 200

    def test_customer_gets_403_for_other_run(self, runs_app, client):
        import api.routes.runs as runs_module

        customer1, tok1 = _create_user(runs_module.SessionLocal,
                                       "cust5@example.com", "customer")
        customer2, _ = _create_user(runs_module.SessionLocal,
                                    "cust6@example.com", "customer")
        _create_run(runs_module.SessionLocal,
                    customer2["id"],
                    run_id="run-other-2")

        resp = client.get("/api/runs/run-other-2",
                          headers={"Authorization": f"Bearer {tok1}"})
        assert resp.status_code == 403

    def test_get_nonexistent_run_returns_404(self, runs_app, client):
        import api.routes.runs as runs_module

        owner, tok = _create_user(runs_module.SessionLocal,
                                  "owner4@example.com", "owner")
        resp = client.get("/api/runs/nonexistent-run",
                          headers={"Authorization": f"Bearer {tok}"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


class TestPagination:

    def test_limit_parameter(self, runs_app, client):
        import api.routes.runs as runs_module

        owner, tok = _create_user(runs_module.SessionLocal,
                                  "pager@example.com", "owner")
        for i in range(10):
            _create_run(runs_module.SessionLocal,
                        owner["id"],
                        run_id=f"page-run-{i:03d}")

        resp = client.get("/api/runs?limit=3",
                          headers={"Authorization": f"Bearer {tok}"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["runs"]) == 3
        assert data["limit"] == 3

    def test_offset_parameter(self, runs_app, client):
        import api.routes.runs as runs_module

        owner, tok = _create_user(runs_module.SessionLocal,
                                  "pager2@example.com", "owner")
        for i in range(5):
            _create_run(runs_module.SessionLocal,
                        owner["id"],
                        run_id=f"offs-run-{i:03d}")

        resp_full = client.get("/api/runs?limit=5",
                               headers={"Authorization": f"Bearer {tok}"})
        resp_offset = client.get("/api/runs?limit=5&offset=2",
                                 headers={"Authorization": f"Bearer {tok}"})

        full_ids = [r["runId"] for r in resp_full.get_json()["runs"]]
        offset_ids = [r["runId"] for r in resp_offset.get_json()["runs"]]

        assert len(offset_ids) == 3
        assert offset_ids == full_ids[2:]

    def test_limit_capped_at_200(self, runs_app, client):
        import api.routes.runs as runs_module

        owner, tok = _create_user(runs_module.SessionLocal,
                                  "capper@example.com", "owner")
        resp = client.get("/api/runs?limit=999",
                          headers={"Authorization": f"Bearer {tok}"})
        assert resp.status_code == 200
        assert resp.get_json()["limit"] == 200

    def test_total_reflects_all_matching_runs(self, runs_app, client):
        import api.routes.runs as runs_module

        owner, tok = _create_user(runs_module.SessionLocal,
                                  "totaller@example.com", "owner")
        for i in range(7):
            _create_run(runs_module.SessionLocal,
                        owner["id"],
                        run_id=f"total-run-{i:03d}")

        resp = client.get("/api/runs?limit=3",
                          headers={"Authorization": f"Bearer {tok}"})
        data = resp.get_json()
        assert data["total"] == 7
        assert len(data["runs"]) == 3


# ---------------------------------------------------------------------------
# Status filter
# ---------------------------------------------------------------------------


class TestStatusFilter:

    def test_status_filter_returns_only_matching_runs(self, runs_app, client):
        import api.routes.runs as runs_module

        owner, tok = _create_user(runs_module.SessionLocal,
                                  "filterer@example.com", "owner")
        _create_run(
            runs_module.SessionLocal,
            owner["id"],
            run_id="filter-queued",
            status="queued",
        )
        _create_run(
            runs_module.SessionLocal,
            owner["id"],
            run_id="filter-completed",
            status="completed",
        )
        _create_run(runs_module.SessionLocal,
                    owner["id"],
                    run_id="filter-error",
                    status="error")

        resp = client.get("/api/runs?status=completed",
                          headers={"Authorization": f"Bearer {tok}"})
        assert resp.status_code == 200
        runs = resp.get_json()["runs"]
        assert all(r["status"] == "completed" for r in runs)
        run_ids = [r["runId"] for r in runs]
        assert "filter-completed" in run_ids
        assert "filter-queued" not in run_ids

    def test_status_filter_queued(self, runs_app, client):
        import api.routes.runs as runs_module

        owner, tok = _create_user(runs_module.SessionLocal,
                                  "filterer2@example.com", "owner")
        _create_run(runs_module.SessionLocal,
                    owner["id"],
                    run_id="qf-1",
                    status="queued")
        _create_run(runs_module.SessionLocal,
                    owner["id"],
                    run_id="qf-2",
                    status="completed")

        resp = client.get("/api/runs?status=queued",
                          headers={"Authorization": f"Bearer {tok}"})
        data = resp.get_json()
        assert data["total"] == 1
        assert data["runs"][0]["runId"] == "qf-1"
