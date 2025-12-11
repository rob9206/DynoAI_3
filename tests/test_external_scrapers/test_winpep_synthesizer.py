from __future__ import annotations

import numpy as np

from external_scrapers.dyno_models import DynoCurveSpec
from external_scrapers.winpep_synthesizer import COLUMN_ORDER, generate_synthetic_pull


def test_generate_synthetic_pull_shapes_curves() -> None:
    spec = DynoCurveSpec(
        idle_rpm=900.0,
        redline_rpm=6700.0,
        hp_peak_rpm=5900.0,
        max_hp=120.0,
        tq_peak_rpm=3600.0,
        max_tq=130.0,
        engine_family="M8",
        displacement_ci=131.0,
    )

    df = generate_synthetic_pull(spec)
    assert list(df.columns) == COLUMN_ORDER

    torque_peak_idx = df["Torque"].idxmax()
    torque_peak_rpm = df.loc[torque_peak_idx, "Engine RPM"]
    assert abs(df.loc[torque_peak_idx, "Torque"] - spec.max_tq) < 0.5
    assert abs(torque_peak_rpm - spec.tq_peak_rpm) < 200

    hp_series = df["Torque"] * df["Engine RPM"] / 5252.0
    hp_peak_idx = hp_series.idxmax()
    hp_peak_rpm = df.loc[hp_peak_idx, "Engine RPM"]
    assert abs(hp_series.iloc[hp_peak_idx] - spec.max_hp) < 0.5
    assert abs(hp_peak_rpm - spec.hp_peak_rpm) < 200

    calculated_hp = df["Torque"] * df["Engine RPM"] / 5252.0
    assert np.allclose(calculated_hp.values, hp_series.values)
