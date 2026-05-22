"""Surgical patch: reduce VE in idle/low-load cells only. Leave WOT untouched.

Strategy:
- Idle zone (RPM <= 1.5k, TPS <= 10): scale VE by IDLE_SCALE (default 0.75).
- Transition zone (RPM <= 2.0k, TPS <= 20): linear blend between scaled and unchanged.
- All other cells: completely untouched.

Applied identically to both front and rear VE tables (preserves cylinder balance).

Verifies only the two VE table items changed; aborts otherwise.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

TARGETS = ("tbl_ve_tps_based_front_cyl", "tbl_ve_tps_based_rear_cyl")

IDLE_RPM_MAX = 1.5
IDLE_TPS_MAX = 10.0
TRANS_RPM_MAX = 2.0
TRANS_TPS_MAX = 20.0


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


def _find(root: ET.Element, iid: str) -> ET.Element:
    for it in root.findall("Item"):
        if it.get("id") == iid:
            return it
    raise ValueError(f"Item {iid!r} not found")


def cell_scale(rpm: float, tps: float, idle_scale: float) -> float:
    """Return scale factor for a cell at (rpm, tps).

    Returns 1.0 outside the transition zone (no change).
    Returns idle_scale inside the strict idle zone.
    Linear blend between strict idle and transition boundaries.
    """
    if rpm <= IDLE_RPM_MAX and tps <= IDLE_TPS_MAX:
        return idle_scale
    if rpm > TRANS_RPM_MAX or tps > TRANS_TPS_MAX:
        return 1.0
    rpm_frac = max(0.0, (rpm - IDLE_RPM_MAX) / (TRANS_RPM_MAX - IDLE_RPM_MAX))
    tps_frac = max(0.0, (tps - IDLE_TPS_MAX) / (TRANS_TPS_MAX - IDLE_TPS_MAX))
    blend = max(rpm_frac, tps_frac)
    blend = min(1.0, blend)
    return idle_scale + (1.0 - idle_scale) * blend


def run(args: argparse.Namespace) -> int:
    if not args.input_pvv.exists():
        raise FileNotFoundError(args.input_pvv)
    if not (0.50 <= args.idle_scale <= 0.95):
        raise ValueError(
            f"idle_scale {args.idle_scale} out of bounds [0.50, 0.95]. "
            "0.50 = 50% VE reduction (extreme). 0.95 = ~5% reduction (tiny)."
        )

    original_root = ET.parse(args.input_pvv).getroot()
    work_tree = ET.parse(args.input_pvv)
    work_root = work_tree.getroot()

    print(f"Input PVV:  {args.input_pvv}")
    print(f"Idle scale: {args.idle_scale} ({(1 - args.idle_scale) * 100:.0f}% VE reduction in idle zone)")
    print(f"Idle zone:  RPM <= {IDLE_RPM_MAX}k, TPS <= {IDLE_TPS_MAX}%")
    print(f"Trans zone: RPM <= {TRANS_RPM_MAX}k, TPS <= {TRANS_TPS_MAX}%")
    print(f"WOT zone:   untouched")

    n_modified_cells = 0
    for tid in TARGETS:
        item = _find(work_root, tid)
        cols = item.findall("./Columns/Col")
        col_tps = [float(c.get("label", "0")) for c in cols]
        rows = item.findall("./Rows/Row")

        print(f"\n--- {tid} ---")
        printed = 0
        for row in rows:
            try:
                rpm = float(row.get("label", "0"))
            except ValueError:
                continue
            cells = row.findall("Cell")
            for c_idx, cell in enumerate(cells):
                tps = col_tps[c_idx]
                scale = cell_scale(rpm, tps, args.idle_scale)
                if abs(scale - 1.0) < 1e-9:
                    continue
                try:
                    old_v = float(cell.get("value", "0"))
                except ValueError:
                    continue
                new_v = old_v * scale
                cell.set("value", _format_value(new_v))
                n_modified_cells += 1
                if printed < 8:
                    print(
                        f"   RPM={rpm:>5.2f}k TPS={tps:>5.1f}%  "
                        f"VE {old_v:6.2f} -> {new_v:6.2f}  (x{scale:.3f})"
                    )
                    printed += 1
        if printed < n_modified_cells:
            print(f"   ... {n_modified_cells - printed} more modified cells")

    print(f"\nTotal modified cells across both tables: {n_modified_cells}")

    if not args.write:
        print("\nDry-run only. Use --write to emit PVV.")
        return 0

    args.output_pvv.parent.mkdir(parents=True, exist_ok=True)
    work_tree.write(args.output_pvv, encoding="utf-8", xml_declaration=True)

    out_root = ET.parse(args.output_pvv).getroot()
    snap_in = _snapshot(original_root)
    snap_out = _snapshot(out_root)
    if set(snap_in) != set(snap_out):
        args.output_pvv.unlink(missing_ok=True)
        raise RuntimeError("Item id set changed -- output deleted.")
    changed = [k for k in snap_in if snap_in[k] != snap_out[k]]
    if sorted(changed) != sorted(TARGETS):
        args.output_pvv.unlink(missing_ok=True)
        raise RuntimeError(
            f"Unexpected items changed: {[c for c in changed if c not in TARGETS]} -- output deleted."
        )

    sha = _sha256(args.output_pvv)
    print(f"\nWrote: {args.output_pvv}")
    print(f"SHA256: {sha}")
    print("\nPost-flash expectation:")
    print(f"  - Idle smoke reduced (idle zone fueled ~{(1 - args.idle_scale) * 100:.0f}% leaner).")
    print("  - Idle stability should improve significantly.")
    print("  - WOT and cruise (TPS >= 25 OR RPM >= 2k): IDENTICAL to current bike.")
    print("  - Decel enleanment: unchanged (still soft).")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-pvv", type=Path, required=True)
    p.add_argument("--output-pvv", type=Path, required=True)
    p.add_argument(
        "--idle-scale",
        type=float,
        default=0.75,
        help="Multiplier for idle-zone VE cells. 0.75 = -25%%. Range [0.50, 0.95].",
    )
    p.add_argument("--write", action="store_true")
    return p.parse_args(argv)


if __name__ == "__main__":
    try:
        sys.exit(run(parse_args(sys.argv[1:])))
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: {e}")
        sys.exit(1)
