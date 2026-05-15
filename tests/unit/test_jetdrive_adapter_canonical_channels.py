from api.services.ingestion.adapters import JetDriveAdapter


def test_jetdrive_adapter_maps_canonical_front_afr():
    adapter = JetDriveAdapter()

    point = adapter.convert(
        {"channel_name": "AFR Front", "value": 13.2, "timestamp_ms": 100}
    )

    assert point.afr_front == 13.2
    assert point.afr == 13.2


def test_jetdrive_adapter_maps_canonical_rear_afr():
    adapter = JetDriveAdapter()

    point = adapter.convert(
        {"channel_name": "AFR Rear", "value": 13.4, "timestamp_ms": 100}
    )

    assert point.afr_rear == 13.4
