import json
from pathlib import Path


def _write_simple_ve_csv(path: Path) -> None:
    # Minimal VE-like CSV that the snapshot parser can handle (RPM header + numeric cells)
    path.write_text(
        "RPM,20,40,60\n"
        "1000,50,55,60\n"
        "2000,52,56,61\n"
        "3000,53,57,62\n",
        encoding="utf-8",
    )


def test_timeline_pagination_default_limit(client, mock_output_folder):
    """
    Backend defaults to limit=50 and includes a pagination object.
    Ensure we can page through more than 50 events.
    """
    from api.services.session_logger import SessionLogger

    run_id = mock_output_folder["run_id"]
    run_dir: Path = mock_output_folder["run_dir"]

    # Create a VE source file for snapshotting
    ve_source = run_dir / "VE_TABLE.csv"
    _write_simple_ve_csv(ve_source)

    logger = SessionLogger(run_dir)

    # 60 events => should paginate (limit 50 by default)
    for i in range(60):
        logger.record_analysis(
            correction_path=ve_source,
            manifest={"stats": {"rows_read": i + 1}, "config": {"args": {}}},
            description=f"analysis #{i+1}",
        )

    r1 = client.get(f"/api/timeline/{run_id}")
    assert r1.status_code == 200
    data1 = json.loads(r1.data)

    assert "pagination" in data1
    assert data1["pagination"]["limit"] == 50
    assert data1["pagination"]["offset"] == 0
    assert data1["pagination"]["total"] == 60
    assert data1["pagination"]["has_more"] is True
    assert len(data1["events"]) == 50

    r2 = client.get(f"/api/timeline/{run_id}?limit=50&offset=50")
    assert r2.status_code == 200
    data2 = json.loads(r2.data)

    assert data2["pagination"]["limit"] == 50
    assert data2["pagination"]["offset"] == 50
    assert data2["pagination"]["total"] == 60
    assert data2["pagination"]["has_more"] is False
    assert len(data2["events"]) == 10


