"""Tests for api.services.parsers.pvv_signature."""

from __future__ import annotations

from api.services.parsers.pvv_signature import compute_pvv_signature


def test_stable_across_whitespace_changes():
    a = (
        b'<?xml version="1.0"?>'
        b'<PVV><Item name="tbl_ve_tps_based_front_cyl">'
        b'<Cell value="1.0"/><Cell value="1.05"/></Item></PVV>'
    )
    b = (
        b'<?xml version="1.0"?>\n'
        b"<PVV>\n"
        b'    <Item name="tbl_ve_tps_based_front_cyl">\n'
        b'        <Cell value="1.0"/>\n'
        b'        <Cell value="1.05"/>\n'
        b"    </Item>\n"
        b"</PVV>\n"
    )
    assert compute_pvv_signature(a) == compute_pvv_signature(b)


def test_different_cell_values_produce_different_signatures():
    a = (
        b'<?xml version="1.0"?>'
        b'<PVV><Item name="tbl_ve_tps_based_front_cyl">'
        b'<Cell value="1.00"/></Item></PVV>'
    )
    b = (
        b'<?xml version="1.0"?>'
        b'<PVV><Item name="tbl_ve_tps_based_front_cyl">'
        b'<Cell value="1.05"/></Item></PVV>'
    )
    assert compute_pvv_signature(a) != compute_pvv_signature(b)


def test_non_pvv_returns_none():
    assert compute_pvv_signature(b"<html></html>") is None


def test_pvv_without_core_tables_falls_back_to_weak_signature():
    data = (
        b'<?xml version="1.0"?><PVV><Item name="random"><Cell value="0"/></Item></PVV>'
    )
    sig = compute_pvv_signature(data)
    assert sig is not None
    assert sig.startswith("weak:")
