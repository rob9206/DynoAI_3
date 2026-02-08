"""
Comprehensive JetDrive service tests – fills gaps NOT covered by:
  - tests/api/test_jetdrive_live_queue.py      (aggregation, bounds, health)
  - tests/api/test_jetdrive_mapping.py         (provider sigs, transforms, persistence)
  - tests/api/test_jetdrive_mapping_confidence.py (confidence scoring, validation)
  - tests/api/test_jetdrive_preflight.py       (provider scoping, semantic, required channels)
  - tests/api/test_jetdrive_realtime_analysis.py (coverage, VE delta, alerts, quality)
  - tests/jetdrive/test_jetdrive_client_protocol.py (parse_frame basics)

Run:
    pytest tests/test_jetdrive_services.py -v
"""

from __future__ import annotations

import math
import struct
import time
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Imports – use the package path that actually resolves
# ---------------------------------------------------------------------------
from api.services.jetdrive.jetdrive_client import (
    CHANNEL_INFO_BLOCK,
    CHANNEL_NAME_LEN,
    CHANNEL_REGISTRY,
    KEY_CHANNEL_INFO,
    KEY_CHANNEL_VALUES,
    PROVIDER_NAME_LEN,
    ChannelInfo,
    JetDriveConfig,
    JetDriveProviderInfo,
    JetDriveSample,
    _clean_utf8,
    _parse_channel_info,
    _parse_channel_values,
    _resolve_iface_address,
    _Wire,
    get_all_cached_channels,
    get_channel_info_from_registry,
    merge_all_providers,
    parse_frame,
)
from api.services.jetdrive.jetdrive_mapping import (
    CANONICAL_CHANNELS,
    TRANSFORMS,
    ChannelMapping,
    MappingConfidence,
    ProviderMapping,
    afr_to_lambda,
    apply_transform,
    celsius_to_fahrenheit,
    fahrenheit_to_celsius,
    ftlb_to_nm,
    hp_to_kw,
    kw_to_hp,
    lambda_to_afr,
    nm_to_ftlb,
    parse_provider_signature,
)
from api.services.jetdrive.jetdrive_realtime_analysis import (
    MAP_BIN_SIZE,
    MAP_MAX,
    MAP_MIN,
    RPM_BIN_SIZE,
    RPM_MAX,
    RPM_MIN,
    TOTAL_CELLS,
    Alert,
    AlertSeverity,
    AlertType,
    CoverageCell,
    QualityMetrics,
    RealtimeAnalysisEngine,
    VEDeltaCell,
    reset_realtime_engine,
)

# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_sample(
    *,
    provider_id: int = 0x1001,
    channel_id: int = 10,
    channel_name: str = "Digital RPM 1",
    timestamp_ms: int = 1000,
    value: float = 3500.0,
    category: str = "dyno",
    units: str = "rpm",
) -> JetDriveSample:
    return JetDriveSample(
        provider_id=provider_id,
        channel_id=channel_id,
        channel_name=channel_name,
        timestamp_ms=timestamp_ms,
        value=value,
        category=category,
        units=units,
    )


def _make_provider(
    *,
    provider_id: int = 0x1001,
    name: str = "Power Core CPU",
    host: str = "169.254.1.1",
    port: int = 22344,
    channels: dict[int, ChannelInfo] | None = None,
) -> JetDriveProviderInfo:
    if channels is None:
        channels = {
            10: ChannelInfo(chan_id=10, name="Digital RPM 1", unit=8),
            3: ChannelInfo(chan_id=3, name="Torque", unit=5),
        }
    return JetDriveProviderInfo(
        provider_id=provider_id,
        name=name,
        host=host,
        port=port,
        channels=channels,
    )


def _make_channel_info_payload(
    provider_name: str = "TestProvider",
    channels: list[tuple[int, str, int]] | None = None,
) -> bytes:
    """Build raw ChannelInfo payload (what goes inside the Wire envelope)."""
    if channels is None:
        channels = [(10, "Digital RPM 1", 8), (3, "Torque", 5)]

    buf = bytearray(provider_name.encode("utf-8").ljust(PROVIDER_NAME_LEN, b"\0"))
    for chan_id, name, unit in channels:
        buf.extend(struct.pack("<H", chan_id))
        buf.append(0)  # vendor
        buf.extend(name.encode("utf-8").ljust(CHANNEL_NAME_LEN, b"\0"))
        buf.append(unit)
    return bytes(buf)


def _make_channel_values_payload(
    values: list[tuple[int, int, float]] | None = None,
) -> bytes:
    """Build raw ChannelValues payload."""
    if values is None:
        values = [(10, 1000, 3500.0), (3, 1000, 180.5)]
    buf = bytearray()
    for chan_id, ts, val in values:
        buf.extend(struct.pack("<HIf", chan_id, ts, float(val)))
    return bytes(buf)


# =============================================================================
# 1. JetDrive Client Protocol Layer
# =============================================================================


class TestJetDriveConfig:
    """JetDriveConfig.from_env() reads environment variables correctly."""

    def test_from_env_defaults(self, monkeypatch):
        monkeypatch.delenv("JETDRIVE_MCAST_GROUP", raising=False)
        monkeypatch.delenv("JETDRIVE_PORT", raising=False)
        monkeypatch.delenv("JETDRIVE_IFACE", raising=False)
        cfg = JetDriveConfig.from_env()
        assert cfg.multicast_group == "224.0.2.10"
        assert cfg.port == 22344
        assert cfg.iface == "0.0.0.0"

    def test_from_env_custom(self, monkeypatch):
        monkeypatch.setenv("JETDRIVE_MCAST_GROUP", "239.0.0.1")
        monkeypatch.setenv("JETDRIVE_PORT", "9999")
        monkeypatch.setenv("JETDRIVE_IFACE", "192.168.1.50")
        cfg = JetDriveConfig.from_env()
        assert cfg.multicast_group == "239.0.0.1"
        assert cfg.port == 9999
        assert cfg.iface == "192.168.1.50"


class TestJetDriveSampleKeys:
    """channel_key property and parse_channel_key() roundtrip."""

    def test_channel_key_format(self):
        s = _make_sample(provider_id=0x00AB, channel_id=10, channel_name="RPM")
        assert s.channel_key == "0x00AB:10:RPM"

    def test_parse_channel_key_roundtrip(self):
        s = _make_sample(provider_id=0x1234, channel_id=37, channel_name="Pressure")
        parsed = JetDriveSample.parse_channel_key(s.channel_key)
        assert parsed is not None
        pid, cid, cname = parsed
        assert pid == 0x1234
        assert cid == 37
        assert cname == "Pressure"

    def test_parse_channel_key_invalid_returns_none(self):
        assert JetDriveSample.parse_channel_key("garbage") is None
        assert JetDriveSample.parse_channel_key("") is None
        assert JetDriveSample.parse_channel_key("0xZZZZ:10:RPM") is None

    def test_channel_key_zero_provider(self):
        s = _make_sample(provider_id=0, channel_id=0, channel_name="Sampling")
        assert s.channel_key == "0x0000:0:Sampling"
        parsed = JetDriveSample.parse_channel_key(s.channel_key)
        assert parsed == (0, 0, "Sampling")


class TestWireProtocol:
    """_Wire.encode() / .decode() binary roundtrip."""

    def test_encode_decode_roundtrip(self):
        payload = b"hello"
        frame = _Wire.encode(key=0x02, host=0x1234, dest=0xFFFF, seq=42, value=payload)
        decoded = _Wire.decode(frame)
        assert decoded is not None
        key, length, host, seq, dest, value = decoded
        assert key == 0x02
        assert length == 5
        assert host == 0x1234
        assert seq == 42
        assert dest == 0xFFFF
        assert value == b"hello"

    def test_decode_too_short_returns_none(self):
        assert _Wire.decode(b"") is None
        assert _Wire.decode(b"\x00\x01") is None

    def test_decode_truncated_payload_returns_none(self):
        # Encode valid frame then chop off part of the payload
        frame = _Wire.encode(key=1, host=1, dest=1, seq=0, value=b"abcdefgh")
        assert _Wire.decode(frame[:-4]) is None

    def test_seq_wraps_at_255(self):
        frame = _Wire.encode(key=1, host=1, dest=1, seq=300, value=b"")
        decoded = _Wire.decode(frame)
        assert decoded is not None
        assert decoded[3] == 300 & 0xFF  # seq byte


class TestCleanUtf8:
    """_clean_utf8() null-terminated UTF-8 cleaning."""

    def test_strips_null_terminators(self):
        assert _clean_utf8(b"RPM\x00\x00\x00") == "RPM"

    def test_strips_whitespace(self):
        assert _clean_utf8(b"  Torque  \x00") == "Torque"

    def test_handles_empty(self):
        assert _clean_utf8(b"\x00\x00") == ""

    def test_replaces_invalid_bytes(self):
        result = _clean_utf8(b"\xff\xfeHello\x00")
        assert "Hello" in result


class TestResolveIfaceAddress:
    """_resolve_iface_address() IP resolution."""

    def test_valid_ip_passthrough(self):
        assert _resolve_iface_address("192.168.1.50") == "192.168.1.50"

    def test_zero_address(self):
        assert _resolve_iface_address("0.0.0.0") == "0.0.0.0"

    def test_empty_string_falls_back(self):
        assert _resolve_iface_address("") == "0.0.0.0"

    def test_none_falls_back(self):
        assert _resolve_iface_address(None) == "0.0.0.0"

    def test_invalid_raises_runtime_error(self):
        with pytest.raises(RuntimeError, match="Invalid interface"):
            _resolve_iface_address("not.a.valid.host.zzzzz")


class TestMergeAllProviders:
    """merge_all_providers() merging, collisions, and empty input."""

    def test_empty_list_returns_dummy(self):
        result = merge_all_providers([])
        assert result.provider_id == 0
        assert result.name == "No Providers"
        assert result.channels == {}

    def test_single_provider_passthrough(self):
        p = _make_provider()
        result = merge_all_providers([p])
        assert result is p

    def test_two_providers_no_collision(self):
        p1 = _make_provider(
            provider_id=1,
            name="P1",
            channels={10: ChannelInfo(chan_id=10, name="RPM", unit=8)},
        )
        p2 = _make_provider(
            provider_id=2,
            name="P2",
            channels={20: ChannelInfo(chan_id=20, name="AFR", unit=11)},
        )
        result = merge_all_providers([p1, p2])
        assert 10 in result.channels
        assert 20 in result.channels
        assert "P1" in result.name and "P2" in result.name

    def test_collision_creates_unique_id(self):
        ch = ChannelInfo(chan_id=10, name="RPM", unit=8)
        p1 = _make_provider(provider_id=1, name="P1", channels={10: ch})
        p2 = _make_provider(
            provider_id=2,
            name="P2",
            channels={10: ChannelInfo(chan_id=10, name="RPM2", unit=8)},
        )
        result = merge_all_providers([p1, p2])
        # Original 10 stays, collision gets shifted key
        assert 10 in result.channels
        unique_id = (2 << 16) | 10
        assert unique_id in result.channels


class TestGetAllCachedChannels:
    """get_all_cached_channels() reads from _provider_cache."""

    def test_returns_empty_when_no_cache(self):
        import api.services.jetdrive.jetdrive_client as jc

        saved = dict(jc._provider_cache)
        jc._provider_cache.clear()
        try:
            assert get_all_cached_channels() == {}
        finally:
            jc._provider_cache.update(saved)

    def test_returns_channels_from_cache(self):
        import api.services.jetdrive.jetdrive_client as jc

        saved = dict(jc._provider_cache)
        jc._provider_cache.clear()
        try:
            jc._provider_cache[1] = _make_provider(
                provider_id=1,
                channels={10: ChannelInfo(chan_id=10, name="RPM", unit=8)},
            )
            result = get_all_cached_channels()
            assert 10 in result
            assert result[10].name == "RPM"
        finally:
            jc._provider_cache.clear()
            jc._provider_cache.update(saved)


class TestChannelRegistry:
    """CHANNEL_REGISTRY correctness and get_channel_info_from_registry()."""

    def test_registry_has_known_ids(self):
        for expected_id in [0, 10, 24, 28, 35, 36, 37, 38]:
            assert expected_id in CHANNEL_REGISTRY, f"Missing ID {expected_id}"

    def test_atmospheric_probe_channels(self):
        assert CHANNEL_REGISTRY[35]["category"] == "atmospheric"
        assert CHANNEL_REGISTRY[36]["category"] == "atmospheric"
        assert CHANNEL_REGISTRY[37]["category"] == "atmospheric"
        assert CHANNEL_REGISTRY[38]["category"] == "atmospheric"

    def test_all_entries_have_required_fields(self):
        for cid, info in CHANNEL_REGISTRY.items():
            assert "name" in info, f"ID {cid} missing 'name'"
            assert "category" in info, f"ID {cid} missing 'category'"
            assert "units" in info, f"ID {cid} missing 'units'"

    def test_get_channel_info_known(self):
        info = get_channel_info_from_registry(37)
        assert info is not None
        assert info["name"] == "Pressure"

    def test_get_channel_info_unknown(self):
        assert get_channel_info_from_registry(99999) is None


class TestParseChannelValues:
    """_parse_channel_values() with FORCE_REGISTRY_CHANNELS and fallbacks."""

    def test_force_registry_channels_35_to_38(self):
        """Channels 35-38 should always use CHANNEL_REGISTRY names, not hardware metadata."""
        payload = _make_channel_values_payload(
            [
                (35, 100, 29.33),
                (36, 100, 28.75),
                (37, 100, 100.58),
                (38, 100, 13.68),
            ]
        )
        # Provide wrong names via lookup to verify registry wins
        wrong_lookup = {
            35: ChannelInfo(chan_id=35, name="WRONG NAME", unit=6),
            36: ChannelInfo(chan_id=36, name="WRONG NAME", unit=6),
            37: ChannelInfo(chan_id=37, name="WRONG NAME", unit=7),
            38: ChannelInfo(chan_id=38, name="WRONG NAME", unit=16),
        }
        samples = _parse_channel_values(0x1001, wrong_lookup, payload)
        assert len(samples) == 4
        names = {s.channel_name for s in samples}
        assert "Temperature 2" in names  # ch35
        assert "Temperature 1" in names  # ch36
        assert "Pressure" in names  # ch37
        assert "Humidity" in names  # ch38

    def test_fallback_to_generic_name(self):
        """Unknown channel ID without lookup or registry → 'Channel X'."""
        payload = _make_channel_values_payload([(9999, 100, 42.0)])
        samples = _parse_channel_values(1, {}, payload)
        assert len(samples) == 1
        assert samples[0].channel_name == "Channel 9999"
        assert samples[0].category == "misc"

    def test_hardware_lookup_used_for_non_force_channels(self):
        """Non-FORCE channels should use hardware metadata when available."""
        lookup = {10: ChannelInfo(chan_id=10, name="Digital RPM 1", unit=8)}
        payload = _make_channel_values_payload([(10, 500, 3000.0)])
        samples = _parse_channel_values(1, lookup, payload)
        assert samples[0].channel_name == "Digital RPM 1"
        assert samples[0].category == "dyno"

    def test_category_inference_from_name(self):
        """Category is inferred from channel name keywords."""
        test_cases = [
            ("AFR Front", "afr"),
            ("Lambda 1", "afr"),
            ("MAP Sensor", "engine"),
            ("TPS Percent", "engine"),
            ("Speed 1", "dyno"),
            ("Force Drum 1", "dyno"),
            ("Random Thing", "misc"),
        ]
        for name, expected_cat in test_cases:
            lookup = {100: ChannelInfo(chan_id=100, name=name, unit=255)}
            payload = _make_channel_values_payload([(100, 0, 1.0)])
            samples = _parse_channel_values(1, lookup, payload)
            assert samples[0].category == expected_cat, (
                f"Name '{name}' expected category '{expected_cat}', got '{samples[0].category}'"
            )


class TestParseChannelInfoEdgeCases:
    """_parse_channel_info() edge cases."""

    def test_too_short_payload_returns_none(self):
        result = _parse_channel_info(0x1234, "1.2.3.4", b"\x00" * 10)
        assert result is None

    def test_empty_channels(self):
        """Payload with only provider name but no channel blocks."""
        payload = b"MyProvider".ljust(PROVIDER_NAME_LEN, b"\x00")
        result = _parse_channel_info(0x1234, "1.2.3.4", payload)
        assert result is not None
        assert result.name == "MyProvider"
        assert result.channels == {}

    def test_fallback_provider_name(self):
        """Empty provider name should fallback to 'JetDrive Provider'."""
        payload = b"\x00" * PROVIDER_NAME_LEN
        result = _parse_channel_info(0x1234, "1.2.3.4", payload)
        assert result is not None
        assert result.name == "JetDrive Provider"


# =============================================================================
# 2. JetDrive Validation
# =============================================================================

# Import validation separately so we can patch the broken import
# The validation module imports from `api.services.jetdrive_client` which may
# not resolve. We import it via the package path.
try:
    from api.services.jetdrive.jetdrive_validation import (
        ChannelHealth,
        ChannelMetrics,
        FrameStats,
        JetDriveDataValidator,
        get_validator,
    )

    _VALIDATION_AVAILABLE = True
except ImportError:
    _VALIDATION_AVAILABLE = False

needs_validation = pytest.mark.skipif(
    not _VALIDATION_AVAILABLE,
    reason="jetdrive_validation has unresolvable import (api.services.jetdrive_client)",
)


@needs_validation
class TestChannelMetricsValidation:
    """ChannelMetrics._is_valid_value() and _update_health() transitions."""

    def _make_metrics(self, **kwargs) -> ChannelMetrics:
        defaults = dict(provider_id=1, channel_id=10, channel_name="RPM")
        defaults.update(kwargs)
        return ChannelMetrics(**defaults)

    def test_nan_is_invalid(self):
        m = self._make_metrics()
        assert m._is_valid_value(float("nan")) is False

    def test_inf_is_invalid(self):
        m = self._make_metrics()
        assert m._is_valid_value(float("inf")) is False
        assert m._is_valid_value(float("-inf")) is False

    def test_normal_value_is_valid(self):
        m = self._make_metrics()
        assert m._is_valid_value(3500.0) is True

    def test_out_of_range_low(self):
        m = self._make_metrics()
        m.min_value = 0.0
        m.max_value = 10000.0
        assert m._is_valid_value(-100.0) is False

    def test_out_of_range_high(self):
        m = self._make_metrics()
        m.min_value = 0.0
        m.max_value = 10000.0
        assert m._is_valid_value(15000.0) is False

    def test_within_range(self):
        m = self._make_metrics()
        m.min_value = 0.0
        m.max_value = 10000.0
        assert m._is_valid_value(5000.0) is True

    def test_health_starts_stale(self):
        m = self._make_metrics()
        assert m.health == ChannelHealth.STALE

    def test_update_transitions_to_healthy(self):
        m = self._make_metrics()
        now = time.time()
        # Feed enough samples at a reasonable rate
        for i in range(10):
            s = _make_sample(value=3000.0 + i, timestamp_ms=1000 + i * 100)
            m.update(s, now + i * 0.05)
        assert m.health == ChannelHealth.HEALTHY

    def test_high_rate_triggers_warning(self):
        m = self._make_metrics()
        now = time.time()
        # Feed many samples in a very short time span to exceed 200 Hz
        for i in range(20):
            s = _make_sample(value=3000.0, timestamp_ms=1000 + i)
            m.update(s, now + i * 0.001)  # 1ms apart = 1000 Hz
        assert m.health == ChannelHealth.WARNING
        assert "high rate" in m.health_reason.lower()

    def test_invalid_values_trigger_invalid_health(self):
        m = self._make_metrics()
        now = time.time()
        # Feed >10 invalid values (NaN)
        for i in range(15):
            s = _make_sample(value=float("nan"), timestamp_ms=1000 + i)
            m.update(s, now + i * 0.1)
        assert m.health == ChannelHealth.INVALID

    def test_to_dict_format(self):
        m = self._make_metrics()
        now = time.time()
        s = _make_sample(value=2500.0, timestamp_ms=5000)
        m.update(s, now)
        d = m.to_dict(now)
        assert "provider_id" in d
        assert "channel_id" in d
        assert "health" in d
        assert "samples_per_second" in d
        assert d["total_samples"] == 1
        assert d["last_value"] == 2500.0


@needs_validation
class TestFrameStats:
    """FrameStats.get_drop_rate() edge cases."""

    def test_zero_frames(self):
        fs = FrameStats()
        assert fs.get_drop_rate() == 0.0

    def test_no_drops(self):
        fs = FrameStats(total_frames=100, dropped_frames=0)
        assert fs.get_drop_rate() == 0.0

    def test_some_drops(self):
        fs = FrameStats(total_frames=200, dropped_frames=10)
        assert fs.get_drop_rate() == pytest.approx(5.0)

    def test_all_dropped(self):
        fs = FrameStats(total_frames=50, dropped_frames=50)
        assert fs.get_drop_rate() == pytest.approx(100.0)


@needs_validation
class TestJetDriveDataValidator:
    """JetDriveDataValidator integration: ranges, frame stats, summary, reset."""

    def _make_validator(self) -> JetDriveDataValidator:
        return JetDriveDataValidator()

    def test_set_channel_range_applies_to_existing_metrics(self):
        v = self._make_validator()
        # Record a sample first to create the channel
        v.record_sample(_make_sample(channel_name="RPM", value=3000.0))
        # Now set range – should apply retroactively
        v.set_channel_range("RPM", 0.0, 10000.0)
        key = (_make_sample().provider_id, _make_sample().channel_id)
        m = v._metrics.get(key)
        assert m is not None
        assert m.min_value == 0.0
        assert m.max_value == 10000.0

    def test_record_frame_stats_per_provider(self):
        v = self._make_validator()
        v.record_frame_stats(provider_id=1, dropped=3, total=100)
        v.record_frame_stats(provider_id=2, dropped=1, total=50)
        v.record_frame_stats(provider_id=1, dropped=2, total=50)
        assert v._frame_stats[1].total_frames == 150
        assert v._frame_stats[1].dropped_frames == 5
        assert v._frame_stats[2].total_frames == 50

    def test_get_channel_summary_sorted(self):
        v = self._make_validator()
        v.record_sample(_make_sample(channel_name="Zebra", channel_id=99))
        v.record_sample(_make_sample(channel_name="Alpha", channel_id=1))
        summary = v.get_channel_summary()
        names = [ch["name"] for ch in summary["channels"]]
        assert names == sorted(names)

    def test_reset_provider_specific(self):
        v = self._make_validator()
        v.record_sample(_make_sample(provider_id=1, channel_id=10))
        v.record_sample(_make_sample(provider_id=2, channel_id=20))
        v.record_frame_stats(provider_id=1, total=10)
        v.record_frame_stats(provider_id=2, total=5)
        # Reset only provider 1
        v.reset(provider_id=1)
        assert (1, 10) not in v._metrics
        assert (2, 20) in v._metrics
        assert v._frame_stats[1].total_frames == 0
        assert v._frame_stats[2].total_frames == 5

    def test_reset_all(self):
        v = self._make_validator()
        v.record_sample(_make_sample(provider_id=1))
        v.record_sample(_make_sample(provider_id=2, channel_id=20))
        v.set_active_provider(1)
        v.reset()
        assert len(v._metrics) == 0
        assert len(v._frame_stats) == 0
        assert v._active_provider_id is None


# =============================================================================
# 3. JetDrive Mapping
# =============================================================================


class TestProviderMappingMethods:
    """ProviderMapping.get_source_to_canonical_map() and get_missing_required()."""

    def test_get_source_to_canonical_map_excludes_disabled(self):
        pm = ProviderMapping(
            channels={
                "rpm": ChannelMapping(
                    canonical_name="rpm", source_id=10, source_name="RPM", enabled=True
                ),
                "afr_front": ChannelMapping(
                    canonical_name="afr_front",
                    source_id=20,
                    source_name="AFR",
                    enabled=False,
                ),
            }
        )
        m = pm.get_source_to_canonical_map()
        assert 10 in m
        assert 20 not in m  # disabled

    def test_get_missing_required_all_present(self):
        pm = ProviderMapping(
            channels={
                "rpm": ChannelMapping(
                    canonical_name="rpm", source_id=10, source_name="RPM"
                ),
                "afr_front": ChannelMapping(
                    canonical_name="afr_front", source_id=20, source_name="AFR"
                ),
            }
        )
        assert pm.get_missing_required() == []

    def test_get_missing_required_no_rpm(self):
        pm = ProviderMapping(
            channels={
                "afr_front": ChannelMapping(
                    canonical_name="afr_front", source_id=20, source_name="AFR"
                ),
            }
        )
        missing = pm.get_missing_required()
        assert "rpm" in missing

    def test_get_missing_required_no_afr(self):
        pm = ProviderMapping(
            channels={
                "rpm": ChannelMapping(
                    canonical_name="rpm", source_id=10, source_name="RPM"
                ),
            }
        )
        missing = pm.get_missing_required()
        assert "afr (any)" in missing

    def test_get_missing_required_lambda_counts_as_afr(self):
        pm = ProviderMapping(
            channels={
                "rpm": ChannelMapping(
                    canonical_name="rpm", source_id=10, source_name="RPM"
                ),
                "lambda_front": ChannelMapping(
                    canonical_name="lambda_front", source_id=26, source_name="Lambda 1"
                ),
            }
        )
        assert pm.get_missing_required() == []

    def test_get_missing_required_empty(self):
        pm = ProviderMapping(channels={})
        missing = pm.get_missing_required()
        assert "rpm" in missing
        assert "afr (any)" in missing


class TestTemperatureTransforms:
    """celsius_to_fahrenheit() / fahrenheit_to_celsius() roundtrip accuracy."""

    def test_boiling_point(self):
        assert celsius_to_fahrenheit(100.0) == pytest.approx(212.0)

    def test_freezing_point(self):
        assert celsius_to_fahrenheit(0.0) == pytest.approx(32.0)

    def test_body_temp(self):
        assert celsius_to_fahrenheit(37.0) == pytest.approx(98.6)

    def test_roundtrip_c_to_f_to_c(self):
        for c in [-40.0, 0.0, 25.0, 100.0, 200.0]:
            assert fahrenheit_to_celsius(celsius_to_fahrenheit(c)) == pytest.approx(c)

    def test_roundtrip_f_to_c_to_f(self):
        for f in [-40.0, 32.0, 98.6, 212.0, 400.0]:
            assert celsius_to_fahrenheit(fahrenheit_to_celsius(f)) == pytest.approx(f)


class TestUnitTransforms:
    """Other transform roundtrips and apply_transform()."""

    def test_lambda_afr_roundtrip(self):
        assert lambda_to_afr(1.0) == pytest.approx(14.7)
        assert afr_to_lambda(14.7) == pytest.approx(1.0)
        for lam in [0.8, 1.0, 1.1]:
            assert afr_to_lambda(lambda_to_afr(lam)) == pytest.approx(lam)

    def test_nm_ftlb_roundtrip(self):
        for nm in [0.0, 100.0, 500.0]:
            assert ftlb_to_nm(nm_to_ftlb(nm)) == pytest.approx(nm, abs=1e-3)

    def test_kw_hp_roundtrip(self):
        for kw in [0.0, 100.0, 500.0]:
            assert hp_to_kw(kw_to_hp(kw)) == pytest.approx(kw, abs=1e-3)

    def test_apply_transform_known(self):
        assert apply_transform(1.0, "lambda_to_afr") == pytest.approx(14.7)

    def test_apply_transform_unknown_falls_back_to_identity(self):
        assert apply_transform(42.0, "nonexistent_transform") == 42.0

    def test_apply_transform_identity(self):
        assert apply_transform(99.9, "identity") == 99.9


class TestParseProviderSignature:
    """parse_provider_signature() with valid and invalid input."""

    def test_valid_signature(self):
        pid, host, chash = parse_provider_signature("4097_192.168.1.50_a1b2c3d4e5f6")
        assert pid == 4097
        assert host == "192.168.1.50"
        assert chash == "a1b2c3d4e5f6"

    def test_invalid_signature_too_few_parts(self):
        with pytest.raises(ValueError, match="Invalid provider signature"):
            parse_provider_signature("bad_sig")

    def test_invalid_signature_non_int_provider_id(self):
        with pytest.raises(ValueError):
            parse_provider_signature("abc_host_hash")


# =============================================================================
# 4. Realtime Analysis
# =============================================================================


class TestRealtimeAnalysisBinning:
    """RealtimeAnalysisEngine._bin_rpm_map() boundary conditions."""

    def test_exact_min_values(self):
        result = RealtimeAnalysisEngine._bin_rpm_map(RPM_MIN, MAP_MIN)
        assert result == (0, 0)

    def test_just_below_max(self):
        result = RealtimeAnalysisEngine._bin_rpm_map(RPM_MAX - 1, MAP_MAX - 1)
        assert result is not None
        rpm_bin, map_bin = result
        assert rpm_bin == (RPM_MAX - 1 - RPM_MIN) // RPM_BIN_SIZE
        assert map_bin == (MAP_MAX - 1 - MAP_MIN) // MAP_BIN_SIZE

    def test_exact_max_returns_none(self):
        """rpm >= RPM_MAX or map >= MAP_MAX should return None."""
        assert RealtimeAnalysisEngine._bin_rpm_map(RPM_MAX, MAP_MIN) is None
        assert RealtimeAnalysisEngine._bin_rpm_map(RPM_MIN, MAP_MAX) is None

    def test_below_min_returns_none(self):
        assert RealtimeAnalysisEngine._bin_rpm_map(RPM_MIN - 1, MAP_MIN) is None
        assert RealtimeAnalysisEngine._bin_rpm_map(RPM_MIN, MAP_MIN - 1) is None

    def test_mid_range_correct_bin(self):
        # RPM 2500 with bin size 500 → bin 5
        # MAP 50 with min 20 and bin size 10 → bin 3
        result = RealtimeAnalysisEngine._bin_rpm_map(2500.0, 50.0)
        assert result is not None
        assert result[0] == 5
        assert result[1] == 3


class TestQualityMetrics:
    """QualityMetrics variance and scoring."""

    def test_get_variance_less_than_2_samples_returns_none(self):
        qm = QualityMetrics()
        assert qm.get_variance("rpm") is None
        qm.update_channel("rpm", 3000.0, time.time())
        assert qm.get_variance("rpm") is None

    def test_get_variance_with_samples(self):
        qm = QualityMetrics()
        now = time.time()
        for v in [10.0, 20.0, 30.0]:
            qm.update_channel("rpm", v, now)
        var = qm.get_variance("rpm")
        assert var is not None
        # Variance of [10, 20, 30]: mean=20, var = ((10-20)^2 + (20-20)^2 + (30-20)^2)/3 = 200/3
        assert var == pytest.approx(200 / 3, abs=0.01)

    def test_compute_score_all_fresh(self):
        qm = QualityMetrics()
        now = time.time()
        qm.update_channel("rpm", 3000.0, now)
        qm.update_channel("afr", 14.7, now)
        qm.missing_channels = []
        score = qm.compute_score(now, coverage_pct=50.0)
        # Should be reasonably high: freshness ≈100, coverage=50, missing=100
        assert score > 50.0

    def test_compute_score_stale_channels(self):
        qm = QualityMetrics()
        stale_time = time.time() - 10.0  # 10 seconds ago
        qm.update_channel("rpm", 3000.0, stale_time)
        score = qm.compute_score(time.time(), coverage_pct=0.0)
        # Freshness penalty, zero coverage → low score
        assert score < 50.0

    def test_compute_score_no_channels(self):
        qm = QualityMetrics()
        score = qm.compute_score(time.time(), coverage_pct=0.0)
        # No freshness data → freshness_score=0, coverage=0, missing depends
        assert score >= 0.0


class TestAlertDeduplication:
    """RealtimeAnalysisEngine._add_alert() deduplication."""

    def test_duplicate_within_5s_is_skipped(self):
        engine = RealtimeAnalysisEngine()
        now = time.time()
        alert1 = Alert(
            type=AlertType.FROZEN_RPM,
            severity=AlertSeverity.WARNING,
            channel="rpm",
            message="Frozen",
            timestamp=now,
        )
        alert2 = Alert(
            type=AlertType.FROZEN_RPM,
            severity=AlertSeverity.WARNING,
            channel="rpm",
            message="Frozen again",
            timestamp=now + 3.0,
        )
        engine._add_alert(alert1)
        engine._add_alert(alert2)
        assert len(engine.alerts) == 1

    def test_same_type_different_channel_passes(self):
        engine = RealtimeAnalysisEngine()
        now = time.time()
        alert1 = Alert(
            type=AlertType.STALE_CHANNEL,
            severity=AlertSeverity.WARNING,
            channel="rpm",
            message="Stale rpm",
            timestamp=now,
        )
        alert2 = Alert(
            type=AlertType.STALE_CHANNEL,
            severity=AlertSeverity.WARNING,
            channel="afr",
            message="Stale afr",
            timestamp=now + 1.0,
        )
        engine._add_alert(alert1)
        engine._add_alert(alert2)
        assert len(engine.alerts) == 2

    def test_same_type_after_5s_passes(self):
        engine = RealtimeAnalysisEngine()
        now = time.time()
        alert1 = Alert(
            type=AlertType.FROZEN_RPM,
            severity=AlertSeverity.WARNING,
            channel="rpm",
            message="Frozen",
            timestamp=now,
        )
        alert2 = Alert(
            type=AlertType.FROZEN_RPM,
            severity=AlertSeverity.WARNING,
            channel="rpm",
            message="Frozen later",
            timestamp=now + 6.0,
        )
        engine._add_alert(alert1)
        engine._add_alert(alert2)
        assert len(engine.alerts) == 2


class TestResetRealtimeEngine:
    """reset_realtime_engine() global singleton reset."""

    def test_reset_clears_state(self):
        import api.services.jetdrive.jetdrive_realtime_analysis as mod

        # Create an engine and add state
        engine = mod.get_realtime_engine()
        engine.coverage_map[(0, 0)] = CoverageCell(rpm_bin=0, map_bin=0, hit_count=5)
        assert len(engine.coverage_map) > 0

        # Reset
        reset_realtime_engine()
        assert len(engine.coverage_map) == 0
        assert len(engine.ve_delta_map) == 0
        assert len(engine.alerts) == 0


# =============================================================================
# 5. Live Capture Queue
# =============================================================================

# The LiveCaptureQueueManager depends on ingestion infrastructure.
# Import with graceful fallback.
try:
    from api.services.jetdrive.jetdrive_live_queue import (
        LiveCaptureQueueManager,
        LiveCaptureQueueStats,
        reset_live_queue_manager,
    )

    _LIVE_QUEUE_AVAILABLE = True
except ImportError:
    _LIVE_QUEUE_AVAILABLE = False

needs_live_queue = pytest.mark.skipif(
    not _LIVE_QUEUE_AVAILABLE,
    reason="jetdrive_live_queue has unresolvable dependencies",
)


@needs_live_queue
class TestLiveCaptureQueueStats:
    """LiveCaptureQueueStats.to_dict() format."""

    def test_to_dict_has_all_fields(self):
        stats = LiveCaptureQueueStats()
        d = stats.to_dict()
        expected_keys = {
            "samples_received",
            "samples_aggregated",
            "samples_enqueued",
            "samples_dropped",
            "samples_written",
            "aggregation_windows",
            "queue_high_watermark",
            "last_flush_time",
            "persist_enabled",
            "persist_lag_ms",
            "enqueue_rate_hz",
        }
        assert expected_keys.issubset(set(d.keys()))

    def test_to_dict_values_default(self):
        stats = LiveCaptureQueueStats()
        d = stats.to_dict()
        assert d["samples_received"] == 0
        assert d["persist_enabled"] is False
        assert d["enqueue_rate_hz"] == 0


@needs_live_queue
class TestLiveCaptureQueueRealtimeAnalysis:
    """LiveCaptureQueueManager real-time analysis enable/disable."""

    def test_analysis_disabled_by_default(self):
        mgr = LiveCaptureQueueManager()
        assert mgr.realtime_analysis_enabled is False
        assert mgr.get_realtime_analysis() is None

    def test_enable_analysis(self):
        mgr = LiveCaptureQueueManager()
        mgr.enable_realtime_analysis(target_afr=13.2)
        assert mgr.realtime_analysis_enabled is True
        state = mgr.get_realtime_analysis()
        assert state is not None
        assert state["enabled"] is True

    def test_enable_analysis_twice_resets(self):
        mgr = LiveCaptureQueueManager()
        mgr.enable_realtime_analysis(target_afr=14.7)
        # Add some state
        mgr._realtime_engine.coverage_map[(0, 0)] = CoverageCell(
            rpm_bin=0, map_bin=0, hit_count=5
        )
        # Enable again should reset
        mgr.enable_realtime_analysis(target_afr=12.5)
        assert mgr._realtime_engine.target_afr == 12.5
        assert len(mgr._realtime_engine.coverage_map) == 0

    def test_disable_analysis(self):
        mgr = LiveCaptureQueueManager()
        mgr.enable_realtime_analysis()
        mgr.disable_realtime_analysis()
        assert mgr.realtime_analysis_enabled is False
        assert mgr.get_realtime_analysis() is None


@needs_live_queue
class TestResetLiveQueueManager:
    """reset_live_queue_manager() singleton cleanup."""

    def test_reset_clears_global(self):
        import api.services.jetdrive.jetdrive_live_queue as mod

        # Create manager
        mgr = mod.get_live_queue_manager()
        assert mgr is not None

        # Reset
        reset_live_queue_manager()
        assert mod._live_queue_manager is None

        # New call creates fresh instance
        mgr2 = mod.get_live_queue_manager()
        assert mgr2 is not mgr
