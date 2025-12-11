from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from synthetic.winpep8_synthesizer import (
    PeakInfo,
    generate_winpep8_like_run,
    save_winpep8_run,
)


def _build_m8_peak() -> PeakInfo:
    return PeakInfo(
        max_hp=120.0,
        hp_peak_rpm=5900.0,
        max_tq=130.0,
        tq_peak_rpm=3800.0,
    )


def test_generate_winpep8_like_run_hits_requested_peaks() -> None:
    peaks = _build_m8_peak()
    df = generate_winpep8_like_run(peaks=peaks, family="M8", displacement_ci=117.0)

    assert not df.empty
    required_columns = {
        "Engine RPM",
        "Torque",
        "Horsepower",
        "MAP kPa",
        "AFR Target F",
        "AFR Target R",
        "VE F",
        "VE R",
        "AFR Cmd F",
        "AFR Cmd R",
        "AFR Meas F",
        "AFR Meas R",
        "IAT F",
        "Knock",
        "VBatt",
        "TPS",
    }
    assert required_columns.issubset(df.columns)

    hp_max = df["Horsepower"].max()
    tq_max = df["Torque"].max()
    assert abs(hp_max - peaks.max_hp) <= peaks.max_hp * 0.03
    assert abs(tq_max - peaks.max_tq) <= peaks.max_tq * 0.03

    hp_peak_rpm = float(df.loc[df["Horsepower"].idxmax(), "Engine RPM"])
    tq_peak_rpm = float(df.loc[df["Torque"].idxmax(), "Engine RPM"])
    assert abs(hp_peak_rpm - peaks.hp_peak_rpm) <= 200
    assert abs(tq_peak_rpm - peaks.tq_peak_rpm) <= 200

    sample_indices = np.linspace(0, len(df) - 1, 20, dtype=int)
    rpm = df["Engine RPM"].to_numpy()[sample_indices]
    hp = df["Horsepower"].to_numpy()[sample_indices]
    tq = df["Torque"].to_numpy()[sample_indices]
    assert np.allclose(hp, tq * rpm / 5252.0, atol=0.5)


def test_save_winpep8_run_writes_csv(monkeypatch, tmp_path) -> None:
    peaks = _build_m8_peak()
    df = generate_winpep8_like_run(peaks=peaks, family="M8", displacement_ci=117.0)

    monkeypatch.chdir(tmp_path)
    path = save_winpep8_run("fuelmoto/demo", df)
    csv_path = Path(path)
    assert csv_path.exists()

    loaded = pd.read_csv(csv_path)
    assert list(loaded.columns) == list(df.columns)
    assert len(loaded) == len(df)
