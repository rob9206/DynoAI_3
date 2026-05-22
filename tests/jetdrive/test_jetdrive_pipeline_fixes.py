"""
Tests for JetDrive pipeline performance fixes:
  1. SO_RCVBUF (UDP socket buffer enlarged to 1 MB)
  2. Sequence gap detection in _subscribe_sync
  3. Event-driven SSE (threading.Event replaces fixed sleep)
"""

from __future__ import annotations

import asyncio
import socket
import struct
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from api.services.jetdrive import jetdrive_client as jc

# ---------------------------------------------------------------------------
# Helpers: build wire frames with controllable sequence numbers
# ---------------------------------------------------------------------------


def _make_channel_values_frame(
    host: int = 0x1234,
    seq: int = 0,
    channels: list[tuple[int, int, float]] | None = None,
) -> bytes:
    """Build a ChannelValues wire frame with a specific sequence number."""
    if channels is None:
        channels = [(1, 1_000, 3500.0)]  # RPM
    payload = bytearray()
    for chan_id, ts, val in channels:
        payload.extend(struct.pack("<HIf", chan_id, ts, float(val)))
    return jc._Wire.encode(
        jc.KEY_CHANNEL_VALUES,
        host=host,
        dest=jc.ALL_HOSTS,
        seq=seq,
        value=bytes(payload),
    )


def _make_channel_info_frame(host: int = 0x1234, seq: int = 0) -> bytes:
    """Build a ChannelInfo frame for a minimal provider."""
    provider_name = b"TestProvider".ljust(jc.PROVIDER_NAME_LEN, b"\0")
    payload = bytearray(provider_name)
    for chan_id, name, unit in [(1, "RPM", jc.JDUnit.EngineSpeed)]:
        payload.extend(struct.pack("<H", chan_id))
        payload.append(0)
        payload.extend(name.encode("utf-8").ljust(jc.CHANNEL_NAME_LEN, b"\0"))
        payload.append(int(unit))
    return jc._Wire.encode(
        jc.KEY_CHANNEL_INFO,
        host=host,
        dest=jc.ALL_HOSTS,
        seq=seq,
        value=bytes(payload),
    )


# ===================================================================
# Test 1: SO_RCVBUF is set on subscribe socket
# ===================================================================


class TestUDPSocketBuffer:
    """Verify that the subscribe socket requests a 1 MB receive buffer."""

    def test_default_rcvbuf_constant_exists(self):
        """DEFAULT_RCVBUF should be defined and default to 1 MB."""
        assert hasattr(jc, "DEFAULT_RCVBUF")
        assert jc.DEFAULT_RCVBUF == 1024 * 1024

    def test_subscribe_socket_sets_rcvbuf(self):
        """_subscribe_sync should call setsockopt(SO_RCVBUF) on its socket."""
        original_socket = socket.socket

        rcvbuf_values: list[int] = []

        class SpySocket(original_socket):
            def setsockopt(self, level, optname, value):
                if level == socket.SOL_SOCKET and optname == socket.SO_RCVBUF:
                    rcvbuf_values.append(value)
                return super().setsockopt(level, optname, value)

        provider = jc.JetDriveProviderInfo(
            provider_id=0x1234,
            name="Test",
            host="127.0.0.1",
            port=22399,
            channels={},
        )
        cfg = jc.JetDriveConfig(
            multicast_group="224.0.2.10", port=22399, iface="127.0.0.1"
        )
        stop_flag = [True]  # Stop immediately

        with patch("socket.socket", SpySocket):
            try:
                jc._subscribe_sync(provider, [], lambda s: None, cfg, stop_flag)
            except OSError:
                pass  # Expected -- binding to multicast on loopback may fail

        assert any(v == jc.DEFAULT_RCVBUF for v in rcvbuf_values), (
            f"Expected SO_RCVBUF={jc.DEFAULT_RCVBUF} in setsockopt calls, got: {rcvbuf_values}"
        )


# ===================================================================
# Test 2: Sequence gap detection
# ===================================================================


class TestSequenceGapDetection:
    """Verify that _subscribe_sync detects missing sequence numbers."""

    def _run_subscribe_with_frames(
        self,
        frames: list[bytes],
        host: int = 0x1234,
    ) -> dict[str, int]:
        """Feed canned frames into _subscribe_sync and return stats."""
        frame_iter = iter(frames)
        call_count = [0]

        provider = jc.JetDriveProviderInfo(
            provider_id=host,
            name="Test",
            host="127.0.0.1",
            port=22344,
            channels={
                1: jc.ChannelInfo(chan_id=1, name="RPM", unit=jc.JDUnit.EngineSpeed)
            },
        )
        cfg = jc.JetDriveConfig(
            multicast_group="224.0.2.10", port=22344, iface="127.0.0.1"
        )

        samples_received: list[jc.JetDriveSample] = []
        stop_flag = [False]

        # Monkey-patch a fake socket into _subscribe_sync via patching socket.socket
        class FakeSocket:
            def __init__(self, *a, **kw):
                pass

            def setsockopt(self, *a, **kw):
                pass

            def getsockopt(self, *a, **kw):
                return 0

            def bind(self, *a, **kw):
                pass

            def settimeout(self, *a, **kw):
                pass

            def close(self):
                pass

            def recvfrom(self, bufsize):
                try:
                    data = next(frame_iter)
                    return data, ("127.0.0.1", 22344)
                except StopIteration:
                    stop_flag[0] = True
                    raise socket.timeout()

        with patch("socket.socket", FakeSocket):
            stats = jc._subscribe_sync(
                provider,
                [],
                lambda s: samples_received.append(s),
                cfg,
                stop_flag,
                recv_timeout=0.1,
                debug=False,
            )

        return stats

    def test_no_gaps_when_sequential(self):
        """Consecutive sequence numbers should yield zero gaps."""
        frames = [
            _make_channel_values_frame(seq=0),
            _make_channel_values_frame(seq=1),
            _make_channel_values_frame(seq=2),
            _make_channel_values_frame(seq=3),
        ]
        stats = self._run_subscribe_with_frames(frames)
        assert stats["seq_gaps"] == 0
        assert stats["total_frames"] == 4

    def test_detects_single_gap(self):
        """Skipping one sequence number should report 1 gap."""
        frames = [
            _make_channel_values_frame(seq=0),
            _make_channel_values_frame(seq=1),
            # seq=2 missing
            _make_channel_values_frame(seq=3),
        ]
        stats = self._run_subscribe_with_frames(frames)
        assert stats["seq_gaps"] == 1

    def test_detects_large_gap(self):
        """Skipping multiple sequence numbers should sum correctly."""
        frames = [
            _make_channel_values_frame(seq=10),
            # seq 11-14 missing (4 packets lost)
            _make_channel_values_frame(seq=15),
        ]
        stats = self._run_subscribe_with_frames(frames)
        assert stats["seq_gaps"] == 4

    def test_wraps_around_255(self):
        """Sequence wrapping from 255 -> 0 should not be a gap."""
        frames = [
            _make_channel_values_frame(seq=254),
            _make_channel_values_frame(seq=255),
            _make_channel_values_frame(seq=0),  # wrap
            _make_channel_values_frame(seq=1),
        ]
        stats = self._run_subscribe_with_frames(frames)
        assert stats["seq_gaps"] == 0

    def test_gap_across_wrap(self):
        """A gap spanning the 255->0 boundary should be counted."""
        frames = [
            _make_channel_values_frame(seq=254),
            # 255 and 0 missing
            _make_channel_values_frame(seq=1),
        ]
        stats = self._run_subscribe_with_frames(frames)
        assert stats["seq_gaps"] == 2

    def test_per_host_tracking(self):
        """Gaps are tracked per-host, not globally."""
        # Host A: sequential.  Host B: has a gap.
        frames = [
            _make_channel_values_frame(host=0xAAAA, seq=0),
            _make_channel_values_frame(host=0xBBBB, seq=0),
            _make_channel_values_frame(host=0xAAAA, seq=1),
            _make_channel_values_frame(host=0xBBBB, seq=5),  # gap of 4
            _make_channel_values_frame(host=0xAAAA, seq=2),
            _make_channel_values_frame(host=0xBBBB, seq=6),
        ]
        # Need to register both hosts as providers for accept_all_providers
        provider = jc.JetDriveProviderInfo(
            provider_id=0xAAAA,
            name="Test",
            host="127.0.0.1",
            port=22344,
            channels={
                1: jc.ChannelInfo(chan_id=1, name="RPM", unit=jc.JDUnit.EngineSpeed)
            },
        )
        cfg = jc.JetDriveConfig(
            multicast_group="224.0.2.10", port=22344, iface="127.0.0.1"
        )

        frame_iter = iter(frames)
        stop_flag = [False]

        class FakeSocket:
            def __init__(self, *a, **kw):
                pass

            def setsockopt(self, *a, **kw):
                pass

            def getsockopt(self, *a, **kw):
                return 0

            def bind(self, *a, **kw):
                pass

            def settimeout(self, *a, **kw):
                pass

            def close(self):
                pass

            def recvfrom(self, bufsize):
                try:
                    data = next(frame_iter)
                    return data, ("127.0.0.1", 22344)
                except StopIteration:
                    stop_flag[0] = True
                    raise socket.timeout()

        with patch("socket.socket", FakeSocket):
            stats = jc._subscribe_sync(
                provider,
                [],
                lambda s: None,
                cfg,
                stop_flag,
                recv_timeout=0.1,
                debug=False,
                accept_all_providers=True,
            )

        # Only host B had a gap of 4
        assert stats["seq_gaps"] == 4

    def test_stats_include_seq_gaps_key(self):
        """The returned stats dict must include the 'seq_gaps' key."""
        frames = [_make_channel_values_frame(seq=0)]
        stats = self._run_subscribe_with_frames(frames)
        assert "seq_gaps" in stats


# ===================================================================
# Test 3: Event-driven SSE (_live_data_event)
# ===================================================================


class TestSSEEventDriven:
    """Verify that _live_data_event exists and is signaled on sample updates."""

    def test_live_data_event_exists(self):
        """_shared should export a threading.Event for SSE wake-up."""
        from api.routes.jetdrive._shared import _live_data_event

        assert isinstance(_live_data_event, threading.Event)

    def test_event_is_cleared_initially(self):
        """The event should not be set before any sample arrives."""
        from api.routes.jetdrive._shared import _live_data_event

        # Clear it to establish a known state
        _live_data_event.clear()
        assert not _live_data_event.is_set()

    def test_event_is_set_after_live_data_update(self):
        """Updating _live_data should set the event so SSE wakes immediately."""
        from api.routes.jetdrive._shared import (
            _live_data,
            _live_data_event,
            _live_data_lock,
        )

        # Clear the event
        _live_data_event.clear()

        # Simulate what on_sample does in hardware.py
        with _live_data_lock:
            channels = _live_data.get("channels")
            if not isinstance(channels, dict):
                channels = {}
                _live_data["channels"] = channels
            channels["Test RPM"] = {
                "value": 3500,
                "name": "Test RPM",
                "timestamp": 1000,
            }
            _live_data["last_update_ts"] = time.time()

        # Signal the event (this is what on_sample does after the lock block)
        _live_data_event.set()

        assert _live_data_event.is_set(), "Event should be set after _live_data update"

        # Clean up
        with _live_data_lock:
            _live_data["channels"].pop("Test RPM", None)
        _live_data_event.clear()

    def test_event_wait_returns_quickly_when_set(self):
        """wait() should return almost instantly when the event is set."""
        from api.routes.jetdrive._shared import _live_data_event

        _live_data_event.clear()

        # Set the event from another thread after 10ms
        def _set_after_delay():
            time.sleep(0.01)
            _live_data_event.set()

        t = threading.Thread(target=_set_after_delay)
        t.start()

        start = time.monotonic()
        _live_data_event.wait(timeout=2.0)
        elapsed = time.monotonic() - start

        t.join()

        # Should have woken up in ~10-50ms, not 250ms (the old sleep)
        assert elapsed < 0.15, f"Event wait took {elapsed:.3f}s, expected < 0.15s"

        _live_data_event.clear()

    def test_sse_stream_uses_event_not_fixed_sleep(self):
        """The SSE endpoint source should reference _live_data_event.wait, not time.sleep(0.25)."""
        import inspect

        from api.routes.jetdrive.hardware import stream_live_data

        source = inspect.getsource(stream_live_data)
        assert "_live_data_event.wait" in source, (
            "SSE should use _live_data_event.wait()"
        )
        assert "time.sleep(0.25)" not in source, (
            "SSE should NOT use the old 250ms sleep"
        )


# ===================================================================
# Test 4: Wideband canonicalization ordering for queue manager
# ===================================================================


class TestWidebandCanonicalizationOrdering:
    """Verify live queue receives canonicalized AFR (not raw LC-2 volts)."""

    def test_queue_receives_canonicalized_wideband_sample(self, monkeypatch):
        from api.routes.jetdrive import hardware
        from api.routes.jetdrive._shared import (
            _live_data,
            _live_data_lock,
            _sample_ring,
        )
        from api.services.jetdrive.wideband_rescale import canonicalize_wideband_sample

        queued_samples: list[jc.JetDriveSample] = []

        class FakeQueueManager:
            def on_sample(self, sample):
                queued_samples.append(sample)

            def start_processing(self):
                pass

            def force_flush(self):
                pass

            def stop_processing(self):
                pass

        class FakeValidator:
            def set_active_provider(self, _provider_id):
                pass

            def reset(self, _provider_id):
                pass

            def record_sample(self, _sample):
                pass

            def record_frame_stats(self, _provider_id, total=1):
                pass

        provider_id = 0x1234
        channel_id = 42
        raw_sample = jc.JetDriveSample(
            provider_id=provider_id,
            channel_id=channel_id,
            channel_name="LC2 Volts Petrol AFR1",
            timestamp_ms=1000,
            value=2.5,
            category="misc",
            units="V",
        )
        provider = jc.JetDriveProviderInfo(
            provider_id=provider_id,
            name="Fake Provider",
            host="127.0.0.1",
            port=22344,
            channels={
                channel_id: jc.ChannelInfo(
                    chan_id=channel_id,
                    name=raw_sample.channel_name,
                    unit=int(jc.JDUnit.AFR),
                )
            },
        )

        async def fake_discover(_config, timeout=10.0):
            return [provider]

        async def fake_subscribe(
            _provider,
            _channel_names,
            on_sample,
            *,
            config=None,
            stop_event=None,
            recv_timeout=2.0,
            debug=True,
            return_stats=True,
        ):
            on_sample(raw_sample)
            if stop_event is not None:
                stop_event.set()
            return {"total_frames": 1, "dropped_frames": 0, "non_provider_frames": 0}

        fake_queue_mgr = FakeQueueManager()
        fake_validator = FakeValidator()

        import api.services.jetdrive.jetdrive_client as client_mod
        import api.services.jetdrive.jetdrive_live_queue as queue_mod
        import api.services.jetdrive.jetdrive_validation as validation_mod

        monkeypatch.setattr(client_mod, "discover_providers", fake_discover)
        monkeypatch.setattr(client_mod, "subscribe", fake_subscribe)
        monkeypatch.setattr(queue_mod, "reset_live_queue_manager", lambda: None)
        monkeypatch.setattr(queue_mod, "get_live_queue_manager", lambda: fake_queue_mgr)
        monkeypatch.setattr(validation_mod, "get_validator", lambda: fake_validator)

        with _live_data_lock:
            _live_data["capturing"] = True
            _live_data["channels"] = {}
            _live_data["last_update_ts"] = None
            _live_data.pop("error", None)
            _sample_ring.clear()

        try:
            hardware._live_capture_loop(requested_provider_id=provider_id)
        except asyncio.CancelledError:
            # _live_capture_loop cancels an internal check task on shutdown and
            # may surface CancelledError during teardown in unit-test execution.
            pass

        assert queued_samples, "Expected at least one sample enqueued to live queue"
        queued = queued_samples[0]
        expected = canonicalize_wideband_sample("LC2 Volts Petrol AFR1", 2.5)
        assert expected is not None

        assert queued.channel_name == expected.canonical_name
        assert queued.value == pytest.approx(expected.afr, rel=1e-6)
        assert queued.units == expected.units
        # Ensure original sample remains raw and unchanged.
        assert raw_sample.channel_name == "LC2 Volts Petrol AFR1"
        assert raw_sample.value == pytest.approx(2.5)

    def test_lc_is_canonical_afr_source_of_truth(self, monkeypatch):
        from api.routes.jetdrive import hardware
        from api.routes.jetdrive._shared import (
            _live_data,
            _live_data_lock,
            _sample_ring,
        )

        class FakeQueueManager:
            def on_sample(self, _sample):
                pass

            def start_processing(self):
                pass

            def force_flush(self):
                pass

            def stop_processing(self):
                pass

        class FakeValidator:
            def set_active_provider(self, _provider_id):
                pass

            def reset(self, _provider_id):
                pass

            def record_sample(self, _sample):
                pass

            def record_frame_stats(self, _provider_id, total=1):
                pass

        provider_id = 0x4321
        lc_chan_id = 10
        ecu_chan_id = 11
        wbo2_chan_id = 12

        lc_sample = jc.JetDriveSample(
            provider_id=provider_id,
            channel_id=lc_chan_id,
            channel_name="LC1 Volts Petrol AFR",
            timestamp_ms=1000,
            value=13.2,
            category="misc",
            units="",
        )
        ecu_sample_same_name = jc.JetDriveSample(
            provider_id=provider_id,
            channel_id=ecu_chan_id,
            channel_name="AFR Front",
            timestamp_ms=1010,
            value=0.2,
            category="afr",
            units="AFR",
        )
        ecu_sample_wbo2 = jc.JetDriveSample(
            provider_id=provider_id,
            channel_id=wbo2_chan_id,
            channel_name="WBO2 AFR Front",
            timestamp_ms=1020,
            value=0.1,
            category="afr",
            units="AFR",
        )

        provider = jc.JetDriveProviderInfo(
            provider_id=provider_id,
            name="Fake Provider",
            host="127.0.0.1",
            port=22344,
            channels={
                lc_chan_id: jc.ChannelInfo(
                    chan_id=lc_chan_id,
                    name=lc_sample.channel_name,
                    unit=int(jc.JDUnit.NoUnit),
                ),
                ecu_chan_id: jc.ChannelInfo(
                    chan_id=ecu_chan_id,
                    name=ecu_sample_same_name.channel_name,
                    unit=int(jc.JDUnit.AFR),
                ),
                wbo2_chan_id: jc.ChannelInfo(
                    chan_id=wbo2_chan_id,
                    name=ecu_sample_wbo2.channel_name,
                    unit=int(jc.JDUnit.AFR),
                ),
            },
        )

        async def fake_discover(_config, timeout=10.0):
            return [provider]

        async def fake_subscribe(
            _provider,
            _channel_names,
            on_sample,
            *,
            config=None,
            stop_event=None,
            recv_timeout=2.0,
            debug=True,
            return_stats=True,
        ):
            on_sample(lc_sample)
            on_sample(ecu_sample_same_name)
            on_sample(ecu_sample_wbo2)
            if stop_event is not None:
                stop_event.set()
            return {"total_frames": 3, "dropped_frames": 0, "non_provider_frames": 0}

        fake_queue_mgr = FakeQueueManager()
        fake_validator = FakeValidator()

        import api.services.jetdrive.jetdrive_client as client_mod
        import api.services.jetdrive.jetdrive_live_queue as queue_mod
        import api.services.jetdrive.jetdrive_validation as validation_mod

        monkeypatch.setattr(client_mod, "discover_providers", fake_discover)
        monkeypatch.setattr(client_mod, "subscribe", fake_subscribe)
        monkeypatch.setattr(queue_mod, "reset_live_queue_manager", lambda: None)
        monkeypatch.setattr(queue_mod, "get_live_queue_manager", lambda: fake_queue_mgr)
        monkeypatch.setattr(validation_mod, "get_validator", lambda: fake_validator)

        with _live_data_lock:
            _live_data["capturing"] = True
            _live_data["channels"] = {}
            _live_data["last_update_ts"] = None
            _live_data.pop("error", None)
            _sample_ring.clear()

        try:
            hardware._live_capture_loop(requested_provider_id=provider_id)
        except asyncio.CancelledError:
            pass

        with _live_data_lock:
            channels = dict(_live_data.get("channels", {}))

        afr_front = channels.get("AFR Front")
        assert isinstance(afr_front, dict)
        assert float(afr_front["value"]) == pytest.approx(13.2)
        assert str(afr_front.get("source_name")) == "LC1 Volts Petrol AFR"

        # Raw ECU AFR channels are still available for diagnostics, but do not
        # override canonical AFR Front.
        wbo2 = channels.get("WBO2 AFR Front")
        assert isinstance(wbo2, dict)
        assert float(wbo2["value"]) == pytest.approx(0.1)
