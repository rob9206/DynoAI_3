"""Tests for api.services.parsers.dynojet_txt_parser."""

from __future__ import annotations

import pytest

from api.services.parsers.dynojet_txt_parser import (
    looks_like_dynojet_txt,
    parse_dynojet_txt,
)


def test_empty_input():
    df, rep = parse_dynojet_txt("")
    assert df.empty
    assert rep.row_count == 0


def test_six_column_tab_header_and_rows():
    text = (
        "Time (s)\tSpeed (mph)\tTorque (ft-lbs)\tPower (hp)\tLC1 AFR\tLC2 AFR\n"
        "0.5\t30.0\t18.0\t10.3\t13.5\t13.3\n"
        "1.0\t40.0\t28.0\t22.1\t13.1\t13.0\n"
        "1.5\t55.0\t34.0\t35.9\t12.8\t12.6\n"
        "2.0\t70.0\t45.0\t60.0\t12.4\t12.3\n"
    )
    df, rep = parse_dynojet_txt(text)
    assert list(df.columns) == [
        "time_s",
        "mph",
        "torque_ftlb",
        "hp",
        "lc1_afr",
        "lc2_afr",
    ]
    assert rep.row_count == 4
    assert rep.has_time and rep.has_mph and rep.has_hp
    assert rep.has_torque and rep.has_afr
    assert rep.peak_hp == pytest.approx(60.0)
    assert rep.peak_hp_mph == pytest.approx(70.0)


def test_five_column_no_torque():
    text = (
        "Time (s)\tSpeed (mph)\tPower (hp)\tLC1 AFR\tLC2 AFR\n"
        "0.5\t30.0\t10.3\t13.5\t13.3\n"
        "1.0\t40.0\t22.1\t13.1\t13.0\n"
        "1.5\t55.0\t35.9\t12.8\t12.6\n"
    )
    df, rep = parse_dynojet_txt(text)
    assert "hp" in df.columns
    assert rep.has_torque is False
    assert rep.peak_torque is None


def test_space_aligned_dynojet_header_chunking():
    text = (
        "Time     mph      ft-lbs    hp       LC1 Volts Petrol AFR    LC2 Volts Petrol AFR2\n"
        "  0.5    30.0     18.0      10.3     13.5                    13.3\n"
        "  1.0    40.0     28.0      22.1     13.1                    13.0\n"
        "  1.5    55.0     34.0      35.9     12.8                    12.6\n"
    )
    df, rep = parse_dynojet_txt(text)
    assert "torque_ftlb" in df.columns
    assert "hp" in df.columns
    assert "lc1_afr" in df.columns
    assert "lc2_afr" in df.columns
    assert rep.row_count == 3


def test_looks_like_dynojet_txt_positive():
    text = (
        "Time\tSpeed\tPower\tLC1 AFR\tLC2 AFR\n"
        "0.5\t30.0\t10.3\t13.5\t13.3\n"
        "1.0\t40.0\t22.1\t13.1\t13.0\n"
        "1.5\t55.0\t35.9\t12.8\t12.6\n"
    )
    assert looks_like_dynojet_txt(text) is True


def test_looks_like_dynojet_txt_negative():
    text = "not a data file, just prose"
    assert looks_like_dynojet_txt(text) is False


def test_column_inference_without_header():
    text = (
        "0.5 30.0 10.3 13.5 13.3\n"
        "1.0 41.5 22.1 13.1 13.0\n"
        "1.5 55.4 35.9 12.8 12.6\n"
        "2.0 70.2 60.0 12.4 12.3\n"
        "2.5 85.1 81.6 12.3 12.2\n"
    )
    df, rep = parse_dynojet_txt(text)
    assert rep.row_count == 5
    assert "mph" in df.columns
    assert "hp" in df.columns
    assert any(c in df.columns for c in ("lc1_afr", "lc2_afr"))
