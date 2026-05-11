"""Safety clamp and sentinel guard tests for AutoTuneWorkflow."""

from __future__ import annotations

import numpy as np
import pandas as pd

from api.services.autotune_workflow import AFRAnalysisResult, AutoTuneWorkflow
from dynoai.core.ve_operations import DEFAULT_MAX_ADJUST_PCT


def _build_session_with_single_cell(
    workflow: AutoTuneWorkflow, ve_delta_pct: float, *, hits: int = 10
):
    session = workflow.create_session(run_id="safety_clamp_test")
    error_df = pd.DataFrame([[ve_delta_pct]], index=[2000], columns=[50])
    ve_delta_df = pd.DataFrame([[ve_delta_pct]], index=[2000], columns=[50])
    hit_df = pd.DataFrame([[hits]], index=[2000], columns=[50])
    session.afr_analysis = AFRAnalysisResult(
        mean_error_pct=float(ve_delta_pct),
        mean_afr_error=1.0,
        zones_rich=0,
        zones_lean=1,
        zones_ok=0,
        zones_no_data=0,
        max_lean_pct=float(max(0.0, ve_delta_pct)),
        max_rich_pct=float(min(0.0, ve_delta_pct)),
        error_by_zone=error_df,
        ve_delta_by_zone=ve_delta_df,
        hit_count_by_zone=hit_df,
    )
    return session


def test_clamp_floors_are_locked():
    """
    Regression guard:
    - AutoTune workflow correction ceiling remains ±10%
    - VE apply/rollback ceiling remains ±7%
    """
    assert AutoTuneWorkflow.MAX_CORRECTION_PCT == 10.0
    assert DEFAULT_MAX_ADJUST_PCT == 7.0


def test_sentinel_cannot_expand_correction_authority():
    """
    Session sentinel may tighten clamp authority but must never widen it.
    """
    workflow = AutoTuneWorkflow(
        max_correction_pct=10.0,
        kernel_sentinel_config={"ve_clamp_pct_per_cell": 25.0},
    )
    session = _build_session_with_single_cell(workflow, ve_delta_pct=30.0)
    result = workflow.calculate_corrections(session)
    assert result is not None
    assert np.isclose(result.correction_table[0, 0], 1.10, atol=1e-6)
    assert result.max_correction_pct <= 10.0001


def test_sentinel_can_tighten_correction_authority():
    workflow = AutoTuneWorkflow(
        max_correction_pct=10.0,
        kernel_sentinel_config={"ve_clamp_pct_per_cell": 5.0},
    )
    session = _build_session_with_single_cell(workflow, ve_delta_pct=30.0)
    result = workflow.calculate_corrections(session)
    assert result is not None
    assert np.isclose(result.correction_table[0, 0], 1.05, atol=1e-6)
    assert result.max_correction_pct <= 5.0001


def test_sentinel_halts_on_lean_streak_grid():
    workflow = AutoTuneWorkflow(
        kernel_sentinel_config={
            "max_consecutive_lean_cells": 1,
            "halt_on_breach": True,
        }
    )
    session = workflow.create_session(run_id="lean_streak_test")
    ve_delta_df = pd.DataFrame([[0.5, 0.6, 0.7]], index=[2500], columns=[50, 60, 70])
    hit_df = pd.DataFrame([[10, 10, 10]], index=[2500], columns=[50, 60, 70])
    session.afr_analysis = AFRAnalysisResult(
        mean_error_pct=0.6,
        mean_afr_error=0.6,
        zones_rich=0,
        zones_lean=3,
        zones_ok=0,
        zones_no_data=0,
        max_lean_pct=0.7,
        max_rich_pct=0.0,
        error_by_zone=ve_delta_df.copy(),
        ve_delta_by_zone=ve_delta_df,
        hit_count_by_zone=hit_df,
    )
    result = workflow.calculate_corrections(session)
    assert result is None
    assert session.status == "halted_on_sentinel"
    assert any("Lean streak" in e for e in session.errors)
