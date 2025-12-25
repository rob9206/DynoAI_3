import time


def test_virtual_tune_start_and_status_smoke(client, monkeypatch):
    """
    Closed-loop autotune regression smoke test.

    Ensures the virtual tuning endpoints respond and the status payload includes
    the progress fields the frontend expects.
    """

    from api.services.virtual_tuning_session import TuningStatus, VirtualTuningOrchestrator

    orchestrator = VirtualTuningOrchestrator(max_age_minutes=1, max_sessions=5)

    def _fast_run_session(session):
        session.status = TuningStatus.RUNNING
        session.update_progress(50.0, "running (test stub)")
        session.current_iteration = 1
        session.status = TuningStatus.CONVERGED
        session.end_time = time.time()
        return session

    # Avoid long-running simulator work in tests: replace the orchestrator used by the route.
    monkeypatch.setattr(orchestrator, "run_session", _fast_run_session)
    monkeypatch.setattr("api.routes.virtual_tune.get_orchestrator", lambda: orchestrator)

    resp = client.post(
        "/api/virtual-tune/start",
        json={
            "engine_profile": "m8_114",
            "base_ve_scenario": "lean",
            "max_iterations": 1,
            "convergence_threshold_afr": 0.3,
        },
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body and "session_id" in body

    session_id = body["session_id"]
    status_resp = client.get(f"/api/virtual-tune/status/{session_id}")
    assert status_resp.status_code == 200
    status = status_resp.get_json()

    assert status["session_id"] == session_id
    assert "status" in status
    assert "current_iteration" in status
    assert "max_iterations" in status
    assert "progress_pct" in status
    assert "progress_message" in status


