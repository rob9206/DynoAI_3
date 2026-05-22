"""Tests for api.services.parsers.dynoware_txt_parser."""

from __future__ import annotations

import pandas as pd
import pytest

from api.services.parsers.dynojet_txt_parser import looks_like_dynojet_txt
from api.services.parsers.dynoware_txt_parser import (
    looks_like_dynoware_txt,
    parse_dynoware_txt,
)


def test_empty_input():
    df, rep = parse_dynoware_txt("")
    assert df.empty
    assert rep.row_count == 0


def test_header_only_no_rows():
    text = """
Dynojet Research Inc.

Run Name: C:\\Users\\dawso\\OneDrive\\Desktop\\hd\\roadglide\\2003\\travisdecamp\\crank_7.txt
Date: Friday, May 15, 2026

      Time      mph       rpmx1000  VE Front
      --------- --------- --------- ---------
Max:                      1.397     67.000
Min:                      0.000     0.000
""".strip()
    df, rep = parse_dynoware_txt(text)
    assert df.empty
    assert rep.row_count == 0


def test_minimal_pv_namespace_row():
    text = (
        "Time, (PV) Engine Speed, (PV) Battery Voltage, "
        "(PV) Manifold Absolute Pressure,\n"
        "0.2, 450, 10.5, 95.4,\n"
    )
    df, rep = parse_dynoware_txt(text)
    assert list(df.columns) == ["time_s", "rpm", "vbatt", "map_kpa"]
    assert df["rpm"].iloc[0] == pytest.approx(450.0)
    assert df["vbatt"].iloc[0] == pytest.approx(10.5)
    assert rep.has_rpm is True
    assert rep.has_vbatt is True
    assert rep.has_map is True


def test_empty_cells_become_nan():
    text = (
        "Time, (PV) Engine Speed, (PV) Battery Voltage, "
        "(PV) Manifold Absolute Pressure,\n"
        "0.2, , 11.2, 100.3,\n"
        "0.25, 300, , ,\n"
    )
    df, _ = parse_dynoware_txt(text)

    assert pd.isna(df["rpm"].iloc[0])
    assert pd.isna(df["vbatt"].iloc[1])
    assert pd.isna(df["map_kpa"].iloc[1])
    assert df["rpm"].iloc[1] == pytest.approx(300.0)


def test_falls_back_to_harley_namespace_when_pv_absent():
    text = (
        "Time, (Harley - ECU Type 11 SW Level 999) Engine Speed, "
        "(Harley - ECU Type 11 SW Level 999) Battery Voltage,\n"
        "0.2, 510, 10.8,\n"
    )
    df, rep = parse_dynoware_txt(text)
    assert "rpm" in df.columns
    assert "vbatt" in df.columns
    assert df["rpm"].iloc[0] == pytest.approx(510.0)
    assert rep.has_rpm is True
    assert rep.has_vbatt is True


def test_sniffer_rejects_hp_tq_dynojet_txt():
    dynojet_text = (
        "Time (s)\tSpeed (mph)\tPower (hp)\tLC1 AFR\tLC2 AFR\n"
        "0.5\t30.0\t10.3\t13.5\t13.3\n"
        "1.0\t40.0\t22.1\t13.1\t13.0\n"
        "1.5\t55.0\t35.9\t12.8\t12.6\n"
    )
    assert looks_like_dynoware_txt(dynojet_text) is False
    assert looks_like_dynojet_txt(dynojet_text) is True


def test_real_crank_6_sample():
    # Small excerpt matching the crank_6.txt channel-log shape.
    text = (
        "Time, (PV) Battery Voltage, (PV) Desired Air/Fuel, (PV) Engine Speed, "
        "(PV) Idle Air Control Motor Position, (PV) Injector Time Front, "
        "(PV) Injector Time Rear, (PV) Manifold Absolute Pressure, "
        "(PV) Spark Advance Front, (PV) Spark Advance Rear, "
        "(PV) Warm-up Fuel AFR (Ratio),\n"
        "1.30, 10.498, 12.2, 60, 145, 0.011, 0.011, 99.495, 0.000, 0.000, 2.5,\n"
        "1.35, 10.241, 12.2, 59, 145, 0.011, 0.011, 99.453, 0.000, 0.000, 2.5,\n"
        "1.40, 9.450, 12.2, 430, 145, 0.010, 0.010, 95.540, 0.000, 0.000, 2.5,\n"
        "1.45, 11.726, 11.954, 1406, 84, 0.005, 0.005, 38.563, 20.229, 20.000, 2.5,\n"
        "1.50, 12.497, 11.8, 1026, 73.058, 0.006, 0.005, 41.897, 20.000, 20.000, 2.5,\n"
    )
    df, rep = parse_dynoware_txt(text)

    assert rep.row_count == 5
    assert rep.sample_rate_hz == pytest.approx(20.0, rel=1e-4)
    assert df["rpm"].max() > 1300
    assert df["vbatt"].min() <= 9.5
    assert "warm_up_afr" in df.columns
