import pandas as pd

from api.services.autotune_workflow import AutoTuneWorkflow


def test_peak_extraction_is_case_insensitive_for_hp_and_torque():
    """
    Regression test: peak HP/TQ extraction should work even when columns are
    lowercase (common with some CSV exports).
    """
    df = pd.DataFrame(
        {
            "Engine RPM": [2000, 3000, 4000],
            "horsepower": [50.0, 75.0, 72.0],
            "torque": [120.0, 110.0, 105.0],
            "AFR Meas": [14.5, 13.2, 12.8],
            "MAP kPa": [50.0, 80.0, 95.0],
        }
    )

    workflow = AutoTuneWorkflow()
    session = workflow.create_session()
    ok = workflow.import_dataframe(session, df)
    assert ok is True

    assert session.peak_hp == 75.0
    assert session.peak_hp_rpm == 3000.0
    assert session.peak_tq == 120.0
    assert session.peak_tq_rpm == 2000.0


