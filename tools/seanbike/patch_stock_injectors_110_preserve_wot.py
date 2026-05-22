from __future__ import annotations

import argparse
import hashlib
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

TARGET_VE_IDS = ("tbl_ve_tps_based_front_cyl", "tbl_ve_tps_based_rear_cyl")
INJECTOR_ID = "tbl_injector_size"
DISPLACEMENT_ID = "tbl_engine_displacement"

G_PER_SEC_TO_LB_PER_HR = 3600.0 / 453.59237


def _find(root: ET.Element, item_id: str) -> ET.Element:
    for item in root.findall("Item"):
        if item.get("id") == item_id:
            return item
    raise ValueError(f"Item id={item_id!r} not found")


def _scalar(root: ET.Element, item_id: str) -> float:
    cell = _find(root, item_id).find("./Rows/Row/Cell")
    if cell is None:
        raise ValueError(f"Scalar item {item_id!r} missing Cell")
    return float(cell.get("value", "0"))


def _set_scalar(root: ET.Element, item_id: str, value: float) -> None:
    cell = _find(root, item_id).find("./Rows/Row/Cell")
    if cell is None:
        raise ValueError(f"Scalar item {item_id!r} missing Cell")
    cell.set("value", _fmt(value))


def _fmt(value: float) -> str:
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return text or "0"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _snapshot(root: ET.Element) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for item in root.findall("Item"):
        item_id = item.get("id", "")
        out[item_id] = [
            cell.get("value", "")
            for row in item.findall("./Rows/Row")
            for cell in row.findall("Cell")
        ]
    return out


def blend_factor(rpm_k: float, tps: float, preserve_factor: float) -> float:
    """Blend from no idle scaling to full fuel-preserving scaling.

    Idle/low-load stays unscaled to cure black smoke and rough rich idle.
    Main/load/high-end gets full scaling so effective WOT fuel remains the same
    after correcting injector and displacement scalars.
    """
    if rpm_k <= 1.5 and tps <= 10.0:
        return 1.0
    if rpm_k >= 2.0 or tps >= 25.0:
        return preserve_factor

    rpm_blend = max(0.0, min(1.0, (rpm_k - 1.5) / 0.5))
    tps_blend = max(0.0, min(1.0, (tps - 10.0) / 15.0))
    blend = max(rpm_blend, tps_blend)
    return 1.0 + (preserve_factor - 1.0) * blend


def run(args: argparse.Namespace) -> int:
    if not args.input_pvv.exists():
        raise FileNotFoundError(args.input_pvv)

    new_injector = args.injector_gps * G_PER_SEC_TO_LB_PER_HR
    if not (25.0 <= new_injector <= 36.0):
        raise ValueError(f"Converted injector scalar {new_injector:.3f} lb/hr is outside expected stock range")
    if not (95.0 <= args.displacement <= 120.0):
        raise ValueError(f"Displacement {args.displacement:.3f} CID outside expected 95-120 CID range")

    original_root = ET.parse(args.input_pvv).getroot()
    tree = ET.parse(args.input_pvv)
    root = tree.getroot()

    old_injector = _scalar(root, INJECTOR_ID)
    old_displacement = _scalar(root, DISPLACEMENT_ID)
    preserve_factor = (old_displacement / old_injector) * (new_injector / args.displacement)

    print(f"Input PVV: {args.input_pvv}")
    print(f"Injector: {old_injector:.4f} lb/hr -> {new_injector:.4f} lb/hr ({args.injector_gps:.3f} g/s)")
    print(f"Displacement: {old_displacement:.3f} CID -> {args.displacement:.3f} CID")
    print(f"Full-load VE preserve factor: x{preserve_factor:.4f}")
    print("Idle zone: unchanged VE so idle gets leaner with corrected scalar.")
    print("Load/WOT zone: VE scaled so effective WOT fueling stays the same.")

    _set_scalar(root, INJECTOR_ID, new_injector)
    _set_scalar(root, DISPLACEMENT_ID, args.displacement)

    max_new = 0.0
    modified = 0
    for item_id in TARGET_VE_IDS:
        item = _find(root, item_id)
        cols = [float(col.get("label", "0")) for col in item.findall("./Columns/Col")]
        shown = 0
        print(f"\n--- {item_id} ---")
        for row in item.findall("./Rows/Row"):
            rpm_k = float(row.get("label", "0"))
            for col_idx, cell in enumerate(row.findall("Cell")):
                tps = cols[col_idx]
                factor = blend_factor(rpm_k, tps, preserve_factor)
                old_val = float(cell.get("value", "0"))
                new_val = old_val * factor
                max_new = max(max_new, new_val)
                if abs(factor - 1.0) > 1e-9:
                    modified += 1
                    if shown < 10:
                        print(
                            f"RPM={rpm_k:>5.2f}k TPS={tps:>5.1f}% "
                            f"VE {old_val:>7.2f} -> {new_val:>7.2f} (x{factor:.3f})"
                        )
                        shown += 1
                cell.set("value", _fmt(new_val))

    print(f"\nModified VE cells: {modified}")
    print(f"Max output VE: {max_new:.2f}")
    if max_new > args.max_ve_warn:
        print(f"WARNING: max VE {max_new:.2f} exceeds warning threshold {args.max_ve_warn:.2f}.")
    if max_new > args.max_ve_block:
        raise RuntimeError(
            f"Refusing to write: max VE {max_new:.2f} exceeds hard block {args.max_ve_block:.2f}"
        )

    if not args.write:
        print("\nDry-run only. Use --write to emit PVV.")
        return 0

    args.output_pvv.parent.mkdir(parents=True, exist_ok=True)
    tree.write(args.output_pvv, encoding="utf-8", xml_declaration=True)

    output_root = ET.parse(args.output_pvv).getroot()
    before = _snapshot(original_root)
    after = _snapshot(output_root)
    changed = [item_id for item_id in before if before[item_id] != after[item_id]]
    allowed = set(TARGET_VE_IDS) | {INJECTOR_ID, DISPLACEMENT_ID}
    unexpected = [item_id for item_id in changed if item_id not in allowed]
    if unexpected or set(before) != set(after):
        args.output_pvv.unlink(missing_ok=True)
        raise RuntimeError(f"Unexpected output mutation; deleted output. unexpected={unexpected}")

    print(f"\nWrote: {args.output_pvv}")
    print(f"SHA256: {_sha256(args.output_pvv)}")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-pvv", type=Path, required=True)
    parser.add_argument("--output-pvv", type=Path, required=True)
    parser.add_argument("--injector-gps", type=float, default=3.91)
    parser.add_argument("--displacement", type=float, default=110.0)
    parser.add_argument("--max-ve-warn", type=float, default=155.0)
    parser.add_argument("--max-ve-block", type=float, default=170.0)
    parser.add_argument("--write", action="store_true")
    return parser.parse_args(argv)


if __name__ == "__main__":
    try:
        sys.exit(run(parse_args(sys.argv[1:])))
    except Exception as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)
