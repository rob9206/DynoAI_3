"""Tests for AFR Mean / AFR Delta derivation (server-side ingest)."""

from __future__ import annotations

import pytest

from api.services.jetdrive.derived_channels import (
    AFR_PAIR_WINDOW_MS,
    AfrDerivationState,
    DERIVED_AFR_DELTA_NAME,
    DERIVED_AFR_MEAN_NAME,
    DERIVED_PROVIDER_ID,
    LC2_AFR_CEILING,
)


def _record(state, name, value, ts_ms):
    return state.record(name, value, ts_ms)


def test_emits_mean_and_delta_when_pair_is_close():
    state = AfrDerivationState()

    # First front sample alone -> nothing.
    assert _record(state, "AFR Front", 13.20, 1000) == []

    # Rear arrives 30ms later (within 50ms window) -> emit pair.
    derived = _record(state, "AFR Rear", 13.40, 1030)
    names = [d.canonical_name for d in derived]
    assert names == [DERIVED_AFR_MEAN_NAME, DERIVED_AFR_DELTA_NAME]

    mean = derived[0]
    delta = derived[1]
    assert mean.value == pytest.approx((13.20 + 13.40) / 2.0)
    assert delta.value == pytest.approx(13.20 - 13.40, abs=1e-9)
    # gap 30ms > AFR_PAIR_WINDOW_MS // 2 (=25), so confidence is 'low'.
    assert mean.confidence == "low"
    assert delta.confidence == "low"
    # Emission timestamp follows the latest source sample.
    assert mean.timestamp_ms == 1030
    assert delta.timestamp_ms == 1030


def test_high_confidence_when_pair_is_tight():
    state = AfrDerivationState()
    _record(state, "AFR Front", 13.20, 1000)
    derived = _record(state, "AFR Rear", 13.30, 1010)  # 10 ms gap -> tight
    assert derived[0].confidence == "high"
    assert derived[1].confidence == "high"


def test_no_emit_when_one_input_pegged():
    state = AfrDerivationState()
    _record(state, "AFR Front", 13.20, 1000)
    # Rear pegged at the LC-2 ceiling -> reject the rear sample, no derivation.
    pegged = _record(state, "AFR Rear", LC2_AFR_CEILING, 1020)
    assert pegged == []
    # State should NOT have stored the pegged rear sample.
    assert state.last_rear is None
    # Any further valid rear within window emits as expected.
    derived = _record(state, "AFR Rear", 13.40, 1030)
    assert [d.canonical_name for d in derived] == [
        DERIVED_AFR_MEAN_NAME,
        DERIVED_AFR_DELTA_NAME,
    ]


def test_no_emit_when_timestamps_too_far_apart():
    state = AfrDerivationState()
    _record(state, "AFR Front", 13.20, 1000)
    # Rear arrives 200 ms later -> outside 50 ms window, skip.
    derived = _record(state, "AFR Rear", 13.40, 1200)
    assert derived == []
    # The samples are stored; a closer rear should still trigger emission.
    derived = _record(state, "AFR Rear", 13.40, 1230)
    # 1230 - 1200 = 30 -> still > AFR_PAIR_WINDOW_MS (50)? 1230 vs front=1000 -> 230, no emit
    # (front would need to update to within 50 ms of rear)
    assert derived == []
    derived = _record(state, "AFR Front", 13.20, 1240)
    assert [d.canonical_name for d in derived] == [
        DERIVED_AFR_MEAN_NAME,
        DERIVED_AFR_DELTA_NAME,
    ]


def test_reject_non_finite_inputs():
    state = AfrDerivationState()
    assert _record(state, "AFR Front", float("nan"), 1000) == []
    assert _record(state, "AFR Rear", float("inf"), 1000) == []
    assert _record(state, "AFR Front", -1.0, 1000) == []
    assert state.last_front is None
    assert state.last_rear is None


def test_derived_entries_carry_synthetic_provider():
    state = AfrDerivationState()
    _record(state, "AFR Front", 13.20, 1000)
    derived = _record(state, "AFR Rear", 13.40, 1010)
    entries = [d.to_live_entry(updated_at_ts=12345.0) for d in derived]

    mean_entry = entries[0]
    assert mean_entry["provider_id"] == DERIVED_PROVIDER_ID
    assert mean_entry["category"] == "afr"
    assert mean_entry["units"] == ":1"
    assert mean_entry["computed"] is True
    assert mean_entry["confidence"] in ("high", "low")
    assert mean_entry["source_name"].startswith("derived:afr_mean")

    delta_entry = entries[1]
    assert delta_entry["source_name"].startswith("derived:afr_delta")


def test_window_constant_matches_documented_50ms():
    assert AFR_PAIR_WINDOW_MS == 50


def test_other_canonical_names_are_ignored():
    state = AfrDerivationState()
    assert _record(state, "Engine RPM", 3000.0, 1000) == []
    assert _record(state, "MAP kPa", 95.0, 1000) == []
    assert state.last_front is None
    assert state.last_rear is None


# ---------------------------------------------------------------------------
# cyl_imbalance enrichment (item 5 of reliability tranche v3)
# ---------------------------------------------------------------------------


def _drive_pairs(state, *, front_value, rear_value, count, start_ms=1000, dt_ms=100):
    """Drive ``count`` accepted Front/Rear pairs ``dt_ms`` apart."""
    last_emit = []
    for i in range(count):
        ts_front = start_ms + i * dt_ms
        ts_rear = ts_front + 10  # tight pair within window
        state.record("AFR Front", front_value, ts_front)
        last_emit = state.record("AFR Rear", rear_value, ts_rear)
    return last_emit


def test_sustained_imbalance_sets_flag_on_afr_mean():
    state = AfrDerivationState()
    # 8 sustained pairs with |delta| = 1.5, which exceeds the 1.0 threshold.
    last = _drive_pairs(state, front_value=12.5, rear_value=14.0, count=8)
    mean = next(d for d in last if d.canonical_name == DERIVED_AFR_MEAN_NAME)
    delta = next(d for d in last if d.canonical_name == DERIVED_AFR_DELTA_NAME)
    assert "cyl_imbalance" in mean.flags
    # Delta channel itself stays a raw subtraction with no enrichment flags.
    assert delta.flags == ()
    # AFR Mean entry serializes the flag for the renderer/board.
    entry = mean.to_live_entry(updated_at_ts=12345.0)
    assert "cyl_imbalance" in entry["flags"]


def test_transient_single_pair_above_threshold_does_not_flag():
    state = AfrDerivationState()
    # First a stretch of balanced pairs (well below threshold).
    _drive_pairs(state, front_value=13.2, rear_value=13.3, count=6)
    # One transient noisy pair.
    state.record("AFR Front", 12.0, 2000)
    last = state.record("AFR Rear", 14.0, 2010)
    mean = next(d for d in last if d.canonical_name == DERIVED_AFR_MEAN_NAME)
    assert "cyl_imbalance" not in mean.flags


def test_pegged_input_excluded_from_imbalance_window():
    state = AfrDerivationState()
    # Drive enough valid balanced pairs for the window to be populated.
    _drive_pairs(state, front_value=13.2, rear_value=13.3, count=8)
    # Now a series of pegged rear samples — they must NOT be counted into
    # the imbalance window, so no flag should appear on subsequent pairs.
    for i in range(6):
        state.record("AFR Front", 13.2, 2500 + i * 100)
        rejected = state.record("AFR Rear", LC2_AFR_CEILING, 2510 + i * 100)
        # Pegged rear is rejected outright; no derived emission produced.
        assert rejected == []

    # Final balanced pair must still NOT be flagged because the imbalance
    # window holds only the earlier balanced samples.
    state.record("AFR Front", 13.2, 4000)
    last = state.record("AFR Rear", 13.3, 4010)
    mean = next(d for d in last if d.canonical_name == DERIVED_AFR_MEAN_NAME)
    assert "cyl_imbalance" not in mean.flags


def test_flag_clears_when_imbalance_ends():
    state = AfrDerivationState()
    # Establish sustained imbalance.
    last = _drive_pairs(state, front_value=12.0, rear_value=14.0, count=10)
    mean = next(d for d in last if d.canonical_name == DERIVED_AFR_MEAN_NAME)
    assert "cyl_imbalance" in mean.flags

    # Now drive enough balanced pairs to age out the imbalanced ones by
    # advancing the timestamp past CYL_IMBALANCE_WINDOW_MS (1500 ms).
    last = _drive_pairs(
        state,
        front_value=13.2,
        rear_value=13.25,
        count=12,
        start_ms=20_000,  # well outside the imbalance window
        dt_ms=100,
    )
    mean = next(d for d in last if d.canonical_name == DERIVED_AFR_MEAN_NAME)
    assert "cyl_imbalance" not in mean.flags


def test_reset_clears_imbalance_history():
    state = AfrDerivationState()
    _drive_pairs(state, front_value=12.0, rear_value=14.0, count=10)
    state.reset()
    # Single new pair after reset cannot have built up enough samples to
    # flag again.
    state.record("AFR Front", 12.0, 100_000)
    last = state.record("AFR Rear", 14.0, 100_010)
    mean = next(d for d in last if d.canonical_name == DERIVED_AFR_MEAN_NAME)
    assert "cyl_imbalance" not in mean.flags
