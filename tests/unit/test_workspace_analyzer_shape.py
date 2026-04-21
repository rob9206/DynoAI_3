"""
Tests for :func:`api.services.workspace_analyzer._shape_for_autotune`.

Focus: ensure the JetDrive wideband-canonicalized column names
(``AFR Front`` / ``AFR Rear``, produced server-side by
:mod:`api.services.jetdrive.wideband_rescale`) flow into the single
``AFR Meas`` column that :class:`AutoTuneWorkflow` consumes.

Without this mapping, ``AutoTuneWorkflow.analyze_afr`` substring-matches
the raw channel names and can silently ingest the wrong column (or
miss AFR entirely) — the exact class of bug the no-physics-in-frontend
rule was written to prevent.
"""

from __future__ import annotations

import pandas as pd

from api.services.workspace_analyzer import _shape_for_autotune


class TestExistingAfrMeasColumnIsPreserved:
    def test_afr_meas_passes_through_untouched(self):
        df = pd.DataFrame(
            {
                "Engine RPM": [2000, 3000],
                "MAP kPa": [50, 60],
                "AFR Meas": [13.5, 14.1],
            }
        )
        shaped = _shape_for_autotune(df)
        assert list(shaped["AFR Meas"]) == [13.5, 14.1]

    def test_lowercase_afr_is_renamed(self):
        df = pd.DataFrame(
            {
                "RPM": [2000, 3000],
                "MAP": [50, 60],
                "afr": [13.5, 14.1],
            }
        )
        shaped = _shape_for_autotune(df)
        assert "AFR Meas" in shaped.columns
        assert list(shaped["AFR Meas"]) == [13.5, 14.1]


class TestCanonicalizedDualSensorAveraging:
    def test_front_and_rear_are_averaged_into_afr_meas(self):
        df = pd.DataFrame(
            {
                "Engine RPM": [2000, 3000, 4000],
                "MAP kPa": [50, 60, 70],
                "AFR Front": [13.0, 13.5, 14.0],
                "AFR Rear": [13.4, 13.7, 14.2],
            }
        )
        shaped = _shape_for_autotune(df)
        assert "AFR Meas" in shaped.columns
        assert list(shaped["AFR Meas"]) == [13.2, 13.6, 14.1]

    def test_front_only_becomes_afr_meas(self):
        df = pd.DataFrame(
            {
                "Engine RPM": [2000, 3000],
                "MAP kPa": [50, 60],
                "AFR Front": [13.5, 14.1],
            }
        )
        shaped = _shape_for_autotune(df)
        assert "AFR Meas" in shaped.columns
        assert list(shaped["AFR Meas"]) == [13.5, 14.1]

    def test_rear_only_becomes_afr_meas(self):
        df = pd.DataFrame(
            {
                "Engine RPM": [2000, 3000],
                "MAP kPa": [50, 60],
                "AFR Rear": [13.5, 14.1],
            }
        )
        shaped = _shape_for_autotune(df)
        assert "AFR Meas" in shaped.columns
        assert list(shaped["AFR Meas"]) == [13.5, 14.1]

    def test_mean_is_skipna(self):
        df = pd.DataFrame(
            {
                "Engine RPM": [2000, 3000, 4000],
                "MAP kPa": [50, 60, 70],
                "AFR Front": [13.0, float("nan"), 14.0],
                "AFR Rear": [13.4, 13.7, float("nan")],
            }
        )
        shaped = _shape_for_autotune(df)
        assert list(shaped["AFR Meas"]) == [13.2, 13.7, 14.0]


class TestCanonicalizedColumnsAreCaseInsensitive:
    def test_lowercase_afr_front_is_picked_up(self):
        df = pd.DataFrame(
            {
                "Engine RPM": [2000],
                "MAP kPa": [50],
                "afr front": [13.5],
            }
        )
        shaped = _shape_for_autotune(df)
        assert "AFR Meas" in shaped.columns
        assert list(shaped["AFR Meas"]) == [13.5]


class TestExistingAfrMeasWinsOverCanonicalized:
    """If both are present (shouldn't happen in practice), the authoritative
    AFR Meas column is preserved; front/rear are ignored."""

    def test_afr_meas_preserved_when_front_rear_also_present(self):
        df = pd.DataFrame(
            {
                "Engine RPM": [2000],
                "MAP kPa": [50],
                "AFR Meas": [14.0],
                "AFR Front": [10.0],
                "AFR Rear": [18.0],
            }
        )
        shaped = _shape_for_autotune(df)
        assert list(shaped["AFR Meas"]) == [14.0]
