from __future__ import annotations

import struct

from synthetic import jetdrive_client as jc


def _channel_info_frame() -> bytes:
    provider_name = b"TestProvider".ljust(jc.PROVIDER_NAME_LEN, b"\0")
    channels = [
        (1, "RPM", jc.JDUnit.EngineSpeed),
        (2, "Torque", jc.JDUnit.Torque),
        (3, "AFR", jc.JDUnit.AFR),
    ]
    payload = bytearray(provider_name)
    for chan_id, name, unit in channels:
        payload.extend(struct.pack("<H", chan_id))
        payload.append(0)  # vendor-specific
        payload.extend(name.encode("utf-8").ljust(jc.CHANNEL_NAME_LEN, b"\0"))
        payload.append(int(unit))
    return jc._Wire.encode(
        jc.KEY_CHANNEL_INFO, host=0x1234, dest=jc.ALL_HOSTS, seq=1, value=bytes(payload)
    )


def _channel_values_frame() -> bytes:
    samples = [
        (1, 1_000, 1600.0),
        (2, 1_000, 200.0),
        (3, 1_000, 13.5),
    ]
    payload = bytearray()
    for chan_id, ts, value in samples:
        payload.extend(struct.pack("<HIf", chan_id, ts, float(value)))
    return jc._Wire.encode(
        jc.KEY_CHANNEL_VALUES,
        host=0x1234,
        dest=jc.ALL_HOSTS,
        seq=2,
        value=bytes(payload),
    )


def test_parse_channel_info_frame():
    key, provider = jc.parse_frame(_channel_info_frame())
    assert key == jc.KEY_CHANNEL_INFO
    assert provider is not None
    assert provider.provider_id == 0x1234
    assert provider.name == "TestProvider"
    assert set(provider.channels.keys()) == {1, 2, 3}
    assert provider.channels[1].name == "RPM"
    assert provider.channels[2].unit == jc.JDUnit.Torque
    assert provider.channels[3].name == "AFR"


def test_parse_channel_values_frame():
    _, provider = jc.parse_frame(_channel_info_frame())
    key, parsed = jc.parse_frame(
        _channel_values_frame(), channel_lookup=provider.channels
    )
    assert key == jc.KEY_CHANNEL_VALUES
    assert isinstance(parsed, list)
    assert len(parsed) == 3
    rpm, tq, afr = parsed
    assert rpm.channel_id == 1 and rpm.channel_name == "RPM"
    assert tq.channel_id == 2 and tq.value == 200.0
    assert afr.channel_id == 3 and afr.timestamp_ms == 1_000


def test_malformed_frame_is_ignored():
    # Truncate the payload so the length field no longer matches
    truncated = _channel_values_frame()[:-3]
    result = jc.parse_frame(truncated, channel_lookup={})
    assert result is None or result[1] in (None, [], ())
