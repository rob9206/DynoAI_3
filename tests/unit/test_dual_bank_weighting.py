"""Dual-bank AFR weighting tests for AutoTuneWorkflow."""

from __future__ import annotations

import pandas as pd

from api.services.autotune_workflow import AutoTuneWorkflow


def _sample_dual_bank_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Engine RPM": [3000.0, 3000.0, 3000.0],
            "MAP kPa": [60.0, 60.0, 60.0],
            "AFR Front": [12.0, 12.0, 12.0],
            "AFR Rear": [14.0, 14.0, 14.0],
            "Time_ms": [0, 10, 20],
        }
    )


def test_dual_bank_weighting_biases_toward_rear_bank():
    df = _sample_dual_bank_df()

    # Baseline path: picks one AFR column (front-biased in this fixture).
    single = AutoTuneWorkflow(use_dual_bank_weighting=False)
    single_session = single.create_session(run_id="single")
    assert single.import_dataframe(single_session, df)
    single_result = single.analyze_afr(single_session)
    assert single_result is not None

    # Dual-bank path blends front + rear with rear weighted +15%.
    dual = AutoTuneWorkflow(use_dual_bank_weighting=True, rear_bank_weight=1.15)
    dual_session = dual.create_session(run_id="dual")
    assert dual.import_dataframe(dual_session, df)
    dual_result = dual.analyze_afr(dual_session)
    assert dual_result is not None

    # At MAP 60 target is 13.5. Front-only (12.0) is richer than weighted blend (~13.07).
    assert dual_result.mean_afr_error > single_result.mean_afr_error
