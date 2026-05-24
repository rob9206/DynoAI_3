from __future__ import annotations

from pathlib import Path

from api.services.workspace_analyzer import _select_primary_pull


def test_select_primary_pull_accepts_csv_shaped_txt(tmp_path: Path) -> None:
    pull = tmp_path / "dynoware_pull.txt"
    pull.write_text(
        "\n".join(
            [
                "Time,(DWRT CPU) Engine RPM,(DWRT CPU) LC2 Volts Petrol AFR2",
                "0.00,2100,14.2",
                "0.05,2500,13.9",
            ]
        ),
        encoding="utf-8",
    )

    chosen, df, source, peak = _select_primary_pull([pull])

    assert chosen == pull
    assert df is not None
    assert not df.empty
    assert source == "txt_csv"
    assert peak is None
