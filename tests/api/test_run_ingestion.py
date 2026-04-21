"""Tests for run ingestion auto-promotion."""

from __future__ import annotations

import json
from pathlib import Path

from api.services.parsers.file_index import FileType
from api.services.run_ingestion.promoter import (
    classify_csv,
    maybe_promote,
    promote_path,
)


def _write_dynoai_csv(path: Path) -> None:
    path.write_text(
        "Engine RPM,Horsepower,Torque\n"
        "2000,40,100\n"
        "3000,60,105\n",
        encoding="utf-8",
    )


def _write_powervision_csv(path: Path) -> None:
    path.write_text(
        '"Dynojet Power Vision Log File"\n'
        "\n"
        '"Format:","Pro-XY CSV 1.0.0"\n'
        "\n"
        '1,"drv","id","RPM","rpm","",""\n'
        '2,"drv","id","MAP","kPa","",""\n'
        '3,"drv","id","TP","%","",""\n'
        "\n"
        '"Time(ms)","Signal","Value"\n'
        "0,1,1100\n"
        "0,2,48\n"
        "0,3,7\n"
        "100,1,2100\n"
        "100,2,56\n"
        "100,3,12\n",
        encoding="utf-8",
    )


def test_classify_csv_detects_powervision_and_dynoai(tmp_path):
    pv = tmp_path / "pv.csv"
    dyno = tmp_path / "dyno.csv"
    _write_powervision_csv(pv)
    _write_dynoai_csv(dyno)

    assert classify_csv(pv) == "powervision"
    assert classify_csv(dyno) == "dynoai"


def test_promote_dynoai_csv_copies_and_writes_manifest(tmp_path):
    source = tmp_path / "dyno.csv"
    runs = tmp_path / "runs"
    _write_dynoai_csv(source)

    result = promote_path(source, runs_dir=runs)

    target = runs / result.run_id / "run.csv"
    manifest = runs / result.run_id / "manifest.json"
    assert result.created is True
    assert target.exists()
    assert target.read_bytes() == source.read_bytes()
    assert manifest.exists()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["source_path"] == str(source.resolve())
    assert data["origin"] == "watch_auto"
    assert data["format"] == "dynoai"


def test_promote_powervision_csv_normalizes_columns(tmp_path):
    source = tmp_path / "pv.csv"
    runs = tmp_path / "runs"
    _write_powervision_csv(source)

    result = promote_path(source, runs_dir=runs)
    promoted = (runs / result.run_id / "run.csv").read_text(encoding="utf-8")
    assert "Engine RPM" in promoted
    assert "MAP kPa" in promoted


def test_promote_wp8_copies_source_only(tmp_path):
    source = tmp_path / "run.wp8"
    runs = tmp_path / "runs"
    source.write_bytes(b"WP8\x00test")

    result = promote_path(source, runs_dir=runs)
    run_dir = runs / result.run_id
    assert result.created is True
    assert (run_dir / "source.wp8").exists()
    assert not (run_dir / "run.csv").exists()


def test_promote_is_idempotent_on_same_source(tmp_path):
    source = tmp_path / "repeat.csv"
    runs = tmp_path / "runs"
    _write_dynoai_csv(source)

    first = promote_path(source, runs_dir=runs)
    second = promote_path(source, runs_dir=runs)

    assert first.created is True
    assert second.created is False
    assert second.reason == "already_promoted"


def test_promote_skips_pvv_and_pvm(tmp_path):
    source = tmp_path / "map.pvv"
    source.write_text("not used", encoding="utf-8")
    event = {
        "file_type": FileType.TUNE.value,
        "parse_ok": True,
        "path": str(source.resolve()),
    }
    assert maybe_promote(event, runs_dir=tmp_path / "runs") is None


def test_promote_skips_parse_failed_csv(tmp_path):
    source = tmp_path / "bad.csv"
    _write_dynoai_csv(source)
    event = {
        "file_type": FileType.LOG.value,
        "parse_ok": False,
        "path": str(source.resolve()),
    }
    assert maybe_promote(event, runs_dir=tmp_path / "runs") is None
