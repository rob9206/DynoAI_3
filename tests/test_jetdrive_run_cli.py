from __future__ import annotations

from pathlib import Path

from synthetic import jetdrive_client as jc
from synthetic import winpep8_cli as cli


def _provider(with_afr: bool = True) -> jc.JetDriveProviderInfo:
    channels = {
        1: jc.ChannelInfo(chan_id=1, name="RPM", unit=int(jc.JDUnit.EngineSpeed)),
        2: jc.ChannelInfo(chan_id=2, name="Torque", unit=int(jc.JDUnit.Torque)),
    }
    if with_afr:
        channels[3] = jc.ChannelInfo(chan_id=3, name="AFR", unit=int(jc.JDUnit.AFR))
    return jc.JetDriveProviderInfo(
        provider_id=0x1234,
        name="TestProvider",
        host="127.0.0.1",
        port=jc.DEFAULT_PORT,
        channels=channels,
    )


def _sample(chan: str, chan_id: int, ts: int, value: float) -> jc.JetDriveSample:
    return jc.JetDriveSample(
        provider_id=0x1234,
        channel_id=chan_id,
        channel_name=chan,
        timestamp_ms=ts,
        value=value,
    )


def _make_run_samples():
    samples = []
    ts = 0
    step = 500
    # Ramp above start threshold (five consecutive RPM samples >= 1500)
    for rpm in (1600, 1700, 1800, 1900, 2000):
        samples.append(_sample("RPM", 1, ts, float(rpm)))
        samples.append(_sample("Torque", 2, ts, 120.0))
        samples.append(_sample("AFR", 3, ts, 13.8))
        ts += step
    # Mid-pull samples
    for rpm in (2500, 3000, 3200, 3400):
        samples.append(_sample("RPM", 1, ts, float(rpm)))
        samples.append(_sample("Torque", 2, ts, 150.0))
        samples.append(_sample("AFR", 3, ts, 12.8))
        ts += step
    # Drop back below end threshold (five consecutive RPM samples <= 1200)
    for rpm in (1100, 1100, 1100, 1000, 950):
        samples.append(_sample("RPM", 1, ts, float(rpm)))
        samples.append(_sample("Torque", 2, ts, 80.0))
        samples.append(_sample("AFR", 3, ts, 13.5))
        ts += step
    return samples


def test_jetdrive_run_auto_trigger_writes_csv(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    async def fake_discover_providers(*_, **__):
        return [_provider()]

    async def fake_subscribe(provider, channel_names, on_sample, **kwargs):
        stop_event = kwargs.get("stop_event")
        for sample in _make_run_samples():
            on_sample(sample)
        if stop_event:
            stop_event.set()

    monkeypatch.setattr(cli, "discover_providers", fake_discover_providers)
    monkeypatch.setattr(cli, "subscribe", fake_subscribe)

    argv = [
        "jetdrive-run",
        "--provider",
        "TestProvider",
        "--run-id",
        "test_run_auto",
        "--family",
        "M8",
        "--displacement-ci",
        "128",
    ]

    rc = cli.main(argv)
    assert rc == 0

    csv_path = Path("runs") / "test_run_auto" / "run.csv"
    assert csv_path.exists()
    content = csv_path.read_text().splitlines()
    assert len(content) > 1
    header = content[0]
    assert "Horsepower" in header and "Torque" in header


def test_jetdrive_run_missing_channel_exits(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    async def fake_discover_providers(*_, **__):
        return [_provider(with_afr=False)]

    monkeypatch.setattr(cli, "discover_providers", fake_discover_providers)

    argv = [
        "jetdrive-run",
        "--provider",
        "TestProvider",
        "--run-id",
        "missing",
        "--family",
        "M8",
        "--displacement-ci",
        "128",
        "--channels",
        "RPM,Torque,AFR",
    ]

    rc = cli.main(argv)
    assert rc == 1
    assert not (Path("runs") / "missing" / "run.csv").exists()


def test_jetdrive_run_timeout_without_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    async def fake_discover_providers(*_, **__):
        return [_provider()]

    async def fake_subscribe(provider, channel_names, on_sample, **kwargs):
        # No samples delivered; behaves as a timeout/no-run scenario
        stop_event = kwargs.get("stop_event")
        if stop_event:
            stop_event.set()

    monkeypatch.setattr(cli, "discover_providers", fake_discover_providers)
    monkeypatch.setattr(cli, "subscribe", fake_subscribe)

    argv = [
        "jetdrive-run",
        "--provider",
        "TestProvider",
        "--run-id",
        "timeout",
        "--family",
        "M8",
        "--displacement-ci",
        "128",
        "--timeout",
        "1.0",
    ]

    rc = cli.main(argv)
    assert rc == 1
    assert not (Path("runs") / "timeout" / "run.csv").exists()
