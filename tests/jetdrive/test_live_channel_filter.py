from __future__ import annotations


def _entry(name: str, value: float = 1.0) -> dict[str, object]:
    return {
        "key": f"0x1000:1:{name}",
        "provider_id": 0x1000,
        "id": 1,
        "name": name,
        "value": value,
        "timestamp": 123,
        "category": "dyno",
        "units": "",
    }


def test_live_payload_filter_keeps_only_requested_channel_groups():
    from api.routes.jetdrive.hardware import _filter_live_display_channels

    channels = {
        "Digital RPM 1": _entry("Digital RPM 1", 3200.0),
        "Engine Speed": _entry("Engine Speed", 3210.0),
        "Air/Fuel Ratio 1": _entry("Air/Fuel Ratio 1", 13.2),
        "Wideband Front": _entry("Wideband Front", 13.1),
        "Lambda 1": _entry("Lambda 1", 0.9),
        "Horsepower": _entry("Horsepower", 93.4),
        "Wheel Power": _entry("Wheel Power", 93.0),
        "VE Front": _entry("VE Front", 88.0),
        "Volumetric Efficiency": _entry("Volumetric Efficiency", 89.0),
        "Torque": _entry("Torque", 112.0),
        "MAP kPa": _entry("MAP kPa", 88.0),
        "Temperature 1": _entry("Temperature 1", 72.0),
        "chan_10": _entry("Digital RPM 1", 3200.0),
    }

    filtered = _filter_live_display_channels(channels)

    assert set(filtered) == {
        "Digital RPM 1",
        "Engine Speed",
        "Air/Fuel Ratio 1",
        "Wideband Front",
        "Lambda 1",
        "Horsepower",
        "Wheel Power",
        "MAP kPa",
        "VE Front",
        "Volumetric Efficiency",
    }


def test_live_payload_filter_does_not_guess_ve_from_other_channels():
    from api.routes.jetdrive.hardware import _filter_live_display_channels

    channels = {
        "Digital RPM 1": _entry("Digital RPM 1", 3200.0),
        "Air/Fuel Ratio 1": _entry("Air/Fuel Ratio 1", 13.2),
        "Horsepower": _entry("Horsepower", 93.4),
        "MAP kPa": _entry("MAP kPa", 88.0),
    }

    filtered = _filter_live_display_channels(channels)

    assert "VE" not in filtered
    assert "Volumetric Efficiency" not in filtered


def test_live_payload_computed_horsepower_has_display_metadata():
    from api.routes.jetdrive._shared import (
        _live_data,
        _live_data_lock,
        _set_simulator_active,
    )
    from api.routes.jetdrive.hardware import _build_live_data_payload

    _set_simulator_active(False)
    with _live_data_lock:
        previous = dict(_live_data)
        _live_data["capturing"] = True
        _live_data["channels"] = {
            "Digital RPM 1": _entry("Digital RPM 1", 3200.0),
            "Force Drum 1": _entry("Force Drum 1", 75.0),
        }
        _live_data["last_update_ts"] = 1_700_000_000.0
        _live_data.pop("error", None)

    try:
        payload = _build_live_data_payload()
    finally:
        with _live_data_lock:
            _live_data.clear()
            _live_data.update(previous)

    hp = payload["channels"]["Horsepower"]
    assert hp["name"] == "Horsepower"
    assert hp["units"] == "HP"
    assert hp["category"] == "dyno"
    assert hp["timestamp"] == 1_700_000_000_000
    assert hp["computed"] is True


def test_prefer_canonical_source_breaks_ties_deterministically():
    from api.routes.jetdrive.hardware import _prefer_canonical_source

    # Same canonical and same unit score -> lower provider/channel wins.
    current = (0x1002, 40, 8)
    candidate = (0x1001, 40, 8)
    assert _prefer_canonical_source("Digital RPM 1", current, candidate) is True
    assert _prefer_canonical_source("Digital RPM 1", candidate, current) is False


def test_live_payload_status_reports_no_provider_condition():
    from api.routes.jetdrive._shared import _live_data, _live_data_lock, _set_simulator_active
    from api.routes.jetdrive.hardware import _build_live_data_payload

    _set_simulator_active(False)
    with _live_data_lock:
        previous = dict(_live_data)
        _live_data["capturing"] = False
        _live_data["channels"] = {}
        _live_data["last_update_ts"] = 1_700_000_000.0
        _live_data["error"] = "No JetDrive providers found."
        _live_data["error_code"] = "no_providers"

    try:
        payload = _build_live_data_payload()
    finally:
        with _live_data_lock:
            _live_data.clear()
            _live_data.update(previous)

    assert payload["status"]["state"] == "no_providers"
    assert payload["status"]["retryable"] is True
    assert payload["error_code"] == "no_providers"
