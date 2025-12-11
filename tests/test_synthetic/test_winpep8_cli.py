from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pandas as pd


def test_winpep8_cli_generates_csv(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    run_id = "cli/demo"
    cmd = [
        sys.executable,
        "-m",
        "synthetic.winpep8_cli",
        "peaks",
        "--run-id",
        run_id,
        "--family",
        "M8",
        "--displacement-ci",
        "128",
        "--max-hp",
        "130",
        "--hp-peak-rpm",
        "6000",
        "--max-tq",
        "140",
        "--tq-peak-rpm",
        "3800",
        "--rpm-points",
        "120",
    ]
    env = os.environ.copy()
    repo_root = Path(__file__).resolve().parents[2]
    existing_pythonpath = env.get("PYTHONPATH")
    combined_pythonpath = str(repo_root)
    if existing_pythonpath:
        combined_pythonpath = os.pathsep.join(
            [combined_pythonpath, existing_pythonpath]
        )
    env["PYTHONPATH"] = combined_pythonpath

    result = subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
    )
    assert "Saved synthetic WinPEP8 run" in result.stdout

    csv_path = Path("runs") / run_id / "run.csv"
    assert csv_path.exists()

    df = pd.read_csv(csv_path)
    assert not df.empty
    assert "Horsepower" in df.columns
    assert len(df) == 120
