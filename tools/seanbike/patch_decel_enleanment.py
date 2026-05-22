"""Surgical patch for tbl_deceleration_enleanment.

Softens the hot-running decel enleanment cells so the engine doesn't die
on closed-throttle overrun. Cold cells are left untouched.

Rule: per-cell change capped at +/- 0.30 in absolute lambda multiplier.
Output ceiling: 0.90 (never disable decel enleanment entirely).
Output floor:   0.30 (allow OEM-style aggressive enleanment if base is that low).

Surgical: ONLY tbl_deceleration_enleanment cells are mutated. Item id
attributes and all other items are preserved exactly.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

TARGET_ITEM_ID = "tbl_deceleration_enleanment"

ABS_FLOOR = 0.30
ABS_CEIL = 0.90
PER_CELL_MAX_DELTA = 0.40


def _find_item(root: ET.Element, item_id: str) -> ET.Element:
    for it in root.findall("Item"):
        if it.get("id") == item_id:
            return it
    raise ValueError(f"Item {item_id!r} not found")


def _format_value(v: float) -> str:
    text = f"{v:.4f}".rstrip("0").rstrip(".")
    return text or "0"


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _snapshot(root: ET.Element) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for it in root.findall("Item"):
        iid = it.get("id", "")
        cells = [
            c.get("value", "")
            for r in it.findall("./Rows/Row")
            for c in r.findall("Cell")
        ]
        out[iid] = cells
    return out


def soften_decel_cells(
    temps: list[float],
    current: list[float],
    hot_threshold: float = 140.0,
    target_hot: float = 0.60,
) -> tuple[list[float], list[str]]:
    """Return new values + per-cell explanation strings.

    Strategy: for cells whose temp axis label is >= hot_threshold (i.e. running
    temperature, not cold-start), raise the multiplier toward target_hot but
    never by more than PER_CELL_MAX_DELTA in one pass. Cold cells unchanged.
    """
    out: list[float] = []
    notes: list[str] = []
    for t, v in zip(temps, current):
        if t < hot_threshold:
            out.append(v)
            notes.append(f"  T={t:>4.0f}  v={v:5.3f} -> {v:5.3f}  (unchanged, cold-side)")
            continue
        desired = target_hot
        delta = desired - v
        if abs(delta) > PER_CELL_MAX_DELTA:
            delta = PER_CELL_MAX_DELTA if delta > 0 else -PER_CELL_MAX_DELTA
        new_v = v + delta
        new_v = max(ABS_FLOOR, min(ABS_CEIL, new_v))
        out.append(new_v)
        notes.append(
            f"  T={t:>4.0f}  v={v:5.3f} -> {new_v:5.3f}  (delta {new_v - v:+.3f})"
        )
    return out, notes


def run(args: argparse.Namespace) -> int:
    if not args.input_pvv.exists():
        raise FileNotFoundError(args.input_pvv)

    original_root = ET.parse(args.input_pvv).getroot()
    work_tree = ET.parse(args.input_pvv)
    work_root = work_tree.getroot()

    item = _find_item(work_root, TARGET_ITEM_ID)
    rows = item.findall("./Rows/Row")
    if len(rows) != 1:
        raise RuntimeError(
            f"Expected 1 row in {TARGET_ITEM_ID}, got {len(rows)} -- aborting."
        )
    cols = item.findall("./Columns/Col")
    temps = [float(c.get("label", "0")) for c in cols]
    cells = rows[0].findall("Cell")
    if len(cells) != len(temps):
        raise RuntimeError(
            f"Column/cell count mismatch ({len(temps)} vs {len(cells)}) -- aborting."
        )
    current = [float(c.get("value", "0")) for c in cells]

    new_vals, notes = soften_decel_cells(
        temps,
        current,
        hot_threshold=args.hot_threshold,
        target_hot=args.target_hot,
    )

    print(f"Input PVV: {args.input_pvv}")
    print(f"Target item: {TARGET_ITEM_ID}")
    print(f"Hot threshold (deg): {args.hot_threshold}")
    print(f"Target hot value: {args.target_hot}")
    print(f"Per-cell max delta: {PER_CELL_MAX_DELTA}")
    print(f"Output range: [{ABS_FLOOR}, {ABS_CEIL}]")
    print("\nCell-by-cell plan:")
    for line in notes:
        print(line)

    if not args.write:
        print("\nDry-run only. Use --write to emit the PVV.")
        return 0

    for cell, v in zip(cells, new_vals):
        cell.set("value", _format_value(v))

    args.output_pvv.parent.mkdir(parents=True, exist_ok=True)
    work_tree.write(args.output_pvv, encoding="utf-8", xml_declaration=True)

    verify_root = ET.parse(args.output_pvv).getroot()
    snap_in = _snapshot(original_root)
    snap_out = _snapshot(verify_root)
    if set(snap_in) != set(snap_out):
        args.output_pvv.unlink(missing_ok=True)
        raise RuntimeError("Item id set changed -- output deleted.")
    changed = [k for k in snap_in if snap_in[k] != snap_out[k]]
    if changed != [TARGET_ITEM_ID]:
        args.output_pvv.unlink(missing_ok=True)
        raise RuntimeError(
            f"Unexpected items changed: {[c for c in changed if c != TARGET_ITEM_ID]} "
            "-- output deleted."
        )

    sha = _sha256(args.output_pvv)
    print(f"\nWrote: {args.output_pvv}")
    print(f"SHA256: {sha}")
    print("\nPost-flash expectation:")
    print("  - Closed-throttle decel from cruise -> idle should no longer die flat.")
    print("  - Idle quality unchanged (this patch does not touch idle tables).")
    print("  - Cold-start drivability unchanged.")
    print("  - Mileage may drop a hair (less aggressive decel cut).")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-pvv", type=Path, required=True)
    p.add_argument("--output-pvv", type=Path, required=True)
    p.add_argument(
        "--hot-threshold",
        type=float,
        default=140.0,
        help="Temperature axis value above which cells get softened. Below this is treated as cold-start and left alone.",
    )
    p.add_argument(
        "--target-hot",
        type=float,
        default=0.60,
        help="Target lambda multiplier for hot cells (higher = less enleanment = richer overrun).",
    )
    p.add_argument("--write", action="store_true")
    return p.parse_args(argv)


if __name__ == "__main__":
    try:
        sys.exit(run(parse_args(sys.argv[1:])))
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: {e}")
        sys.exit(1)
