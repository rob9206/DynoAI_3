from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import numpy as np

TARGET_VE_ITEM_IDS = (
    "tbl_ve_tps_based_front_cyl",
    "tbl_ve_tps_based_rear_cyl",
)
SCALAR_ITEM_IDS = {
    "injector_size": "tbl_injector_size",
    "engine_displacement": "tbl_engine_displacement",
}
ALLOWED_CHANGED_IDS = set(TARGET_VE_ITEM_IDS) | set(SCALAR_ITEM_IDS.values())

DEFAULT_STOCK_VE_PVV = Path(r"C:\Users\dawso\Downloads\stock ve.pvv")
DEFAULT_BASE_PVV = Path(r"C:\CommmandCenter\Customer_Files\seanbike\exportedreadfrompv4.pvv")
DEFAULT_TRIMS_CSV = Path(r"C:\Dev\DynoAI_3\tools\seanbike\pcv_advanced_trims.csv")
DEFAULT_OUTPUT_PVV = Path(
    r"C:\Dev\DynoAI_3\vehicles\seanbike\sessions\dai_2026_0518_pcv_bake_verify\iterations\iter_0\patches\v_pc_advanced_translation.pvv"
)


@dataclass
class TableData:
    item: ET.Element
    row_axis: np.ndarray
    col_axis: np.ndarray
    values: np.ndarray
    cell_elements: list[list[ET.Element]]


def _format_value(value: float) -> str:
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    if text in {"-0", "-0.0"}:
        return "0"
    return text


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _find_item_by_id(root: ET.Element, item_id: str) -> ET.Element:
    for item in root.findall("Item"):
        if item.get("id") == item_id:
            return item
    raise ValueError(f"Could not find Item id={item_id!r}")


def _parse_scalar(root: ET.Element, item_id: str) -> float:
    item = _find_item_by_id(root, item_id)
    cell = item.find("./Rows/Row/Cell")
    if cell is None:
        raise ValueError(f"Scalar item {item_id!r} missing Rows/Row/Cell")
    raw = cell.get("value")
    if raw is None:
        raise ValueError(f"Scalar item {item_id!r} missing value attribute")
    return float(raw)


def _set_scalar(root: ET.Element, item_id: str, value: float) -> None:
    item = _find_item_by_id(root, item_id)
    cell = item.find("./Rows/Row/Cell")
    if cell is None:
        raise ValueError(f"Scalar item {item_id!r} missing Rows/Row/Cell")
    cell.set("value", _format_value(value))


def _parse_table(root: ET.Element, item_id: str) -> TableData:
    item = _find_item_by_id(root, item_id)
    col_elements = item.findall("./Columns/Col")
    row_elements = item.findall("./Rows/Row")
    if not col_elements or not row_elements:
        raise ValueError(f"Table item {item_id!r} missing rows/columns")

    col_axis = np.array([float(col.get("label", "0")) for col in col_elements], dtype=float)
    row_axis: list[float] = []
    values: list[list[float]] = []
    cell_elements: list[list[ET.Element]] = []
    for row in row_elements:
        row_axis.append(float(row.get("label", "0")))
        cells = row.findall("Cell")
        if len(cells) != len(col_elements):
            raise ValueError(
                f"Table {item_id!r} row has {len(cells)} cells; expected {len(col_elements)}"
            )
        cell_elements.append(cells)
        values.append([float(cell.get("value", "0")) for cell in cells])
    return TableData(
        item=item,
        row_axis=np.array(row_axis, dtype=float),
        col_axis=col_axis,
        values=np.array(values, dtype=float),
        cell_elements=cell_elements,
    )


def _collect_item_cells(root: ET.Element) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for item in root.findall("Item"):
        item_id = item.get("id", "")
        out[item_id] = [
            cell.get("value", "")
            for row in item.findall("./Rows/Row")
            for cell in row.findall("Cell")
        ]
    return out


def _verify_output_integrity(
    input_root: ET.Element,
    output_root: ET.Element,
    allowed_changed_ids: set[str],
) -> tuple[list[str], list[str]]:
    in_items = input_root.findall("Item")
    out_items = output_root.findall("Item")
    if len(in_items) != len(out_items):
        raise RuntimeError(f"Output Item count changed ({len(in_items)} -> {len(out_items)})")
    in_ids = {item.get("id", "") for item in in_items}
    out_ids = {item.get("id", "") for item in out_items}
    if in_ids != out_ids:
        raise RuntimeError("Output Item id set does not match input")

    in_cells = _collect_item_cells(input_root)
    out_cells = _collect_item_cells(output_root)
    changed_ids = sorted(item_id for item_id in in_cells if in_cells[item_id] != out_cells[item_id])
    unexpected = sorted(item_id for item_id in changed_ids if item_id not in allowed_changed_ids)
    if unexpected:
        raise RuntimeError(f"Unexpected non-approved item ids changed: {', '.join(unexpected)}")
    return changed_ids, unexpected


def _load_trim_csv(csv_path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if not csv_path.exists():
        raise FileNotFoundError(f"Trim CSV not found: {csv_path}")
    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError("Trim CSV missing header")
        tps_fields = [name for name in reader.fieldnames if name.startswith("tps_")]
        if not tps_fields:
            raise ValueError("Trim CSV missing tps_* columns")
        tps_axis = np.array([float(field.replace("tps_", "")) for field in tps_fields], dtype=float)

        by_cyl: dict[str, list[tuple[float, list[float]]]] = {"front": [], "rear": []}
        for row in reader:
            cyl = (row.get("cylinder") or "").strip().lower()
            if cyl not in by_cyl:
                continue
            rpm = float(row["rpm"])
            values = [float(row[field]) for field in tps_fields]
            by_cyl[cyl].append((rpm, values))

    if not by_cyl["front"] or not by_cyl["rear"]:
        raise ValueError("Trim CSV must include both front and rear cylinders")
    for cyl in ("front", "rear"):
        by_cyl[cyl].sort(key=lambda pair: pair[0])
    front_rpm = np.array([rpm for rpm, _ in by_cyl["front"]], dtype=float)
    rear_rpm = np.array([rpm for rpm, _ in by_cyl["rear"]], dtype=float)
    if not np.array_equal(front_rpm, rear_rpm):
        raise ValueError("Front/rear trim RPM axes differ")
    front_grid = np.array([vals for _, vals in by_cyl["front"]], dtype=float)
    rear_grid = np.array([vals for _, vals in by_cyl["rear"]], dtype=float)
    return front_rpm, tps_axis, front_grid, rear_grid


def _resample_trim(
    src_rpm: np.ndarray,
    src_tps: np.ndarray,
    src_grid: np.ndarray,
    dst_rpm: np.ndarray,
    dst_tps: np.ndarray,
) -> np.ndarray:
    interp_tps = np.vstack(
        [np.interp(dst_tps, src_tps, src_grid[row_idx], left=np.nan, right=np.nan) for row_idx in range(src_grid.shape[0])]
    )
    out = np.vstack(
        [np.interp(dst_rpm, src_rpm, interp_tps[:, col_idx], left=np.nan, right=np.nan) for col_idx in range(interp_tps.shape[1])]
    ).T
    rpm_ok = (dst_rpm[:, None] >= src_rpm[0]) & (dst_rpm[:, None] <= src_rpm[-1])
    tps_ok = (dst_tps[None, :] >= src_tps[0]) & (dst_tps[None, :] <= src_tps[-1])
    mask = rpm_ok & tps_ok
    out = np.where(mask, out, 0.0)
    return np.nan_to_num(out, nan=0.0)


def _mutate_table_cells(table: TableData, new_values: np.ndarray) -> None:
    if table.values.shape != new_values.shape:
        raise ValueError("New value shape mismatch")
    rows, cols = new_values.shape
    for r in range(rows):
        for c in range(cols):
            table.cell_elements[r][c].set("value", _format_value(float(new_values[r, c])))


def _max_front_rear_delta(front: np.ndarray, rear: np.ndarray) -> tuple[float, tuple[int, int]]:
    abs_diff = np.abs(front - rear)
    idx = np.unravel_index(int(np.argmax(abs_diff)), abs_diff.shape)
    return float(abs_diff[idx]), (int(idx[0]), int(idx[1]))


def run(args: argparse.Namespace) -> int:
    for path in (args.stock_ve_pvv, args.base_pvv, args.trim_csv):
        if not path.exists():
            raise FileNotFoundError(path)

    if not (args.injector_min <= args.target_injector <= args.injector_max):
        raise RuntimeError(
            f"Injector target sanity gate failed: {args.target_injector:.3f} not in "
            f"[{args.injector_min:.3f}, {args.injector_max:.3f}]"
        )
    if not (args.displacement_min <= args.target_displacement <= args.displacement_max):
        raise RuntimeError(
            f"Displacement target sanity gate failed: {args.target_displacement:.3f} not in "
            f"[{args.displacement_min:.3f}, {args.displacement_max:.3f}]"
        )

    comp_factor = args.source_displacement / args.target_displacement
    expected = 95.5 / 103.0
    if abs(comp_factor - expected) > 1e-6:
        raise RuntimeError(
            f"Compensation factor mismatch: got {comp_factor:.9f}, expected {expected:.9f}. "
            "Update source/target displacement intentionally if you need a different factor."
        )

    original_root = ET.parse(args.base_pvv).getroot()
    base_tree = ET.parse(args.base_pvv)
    base_root = base_tree.getroot()
    stock_root = ET.parse(args.stock_ve_pvv).getroot()

    old_injector = _parse_scalar(base_root, SCALAR_ITEM_IDS["injector_size"])
    old_disp = _parse_scalar(base_root, SCALAR_ITEM_IDS["engine_displacement"])
    print(f"Base PVV: {args.base_pvv}")
    print(f"Stock VE PVV: {args.stock_ve_pvv}")
    print(f"Trim CSV: {args.trim_csv}")
    print(f"Base scalars: injector={old_injector:.3f} displacement={old_disp:.3f}")
    print(
        f"Target scalars: injector={args.target_injector:.3f} displacement={args.target_displacement:.3f}"
    )
    print(f"VE compensation factor K={comp_factor:.9f}")

    base_front = _parse_table(base_root, TARGET_VE_ITEM_IDS[0])
    base_rear = _parse_table(base_root, TARGET_VE_ITEM_IDS[1])
    stock_front = _parse_table(stock_root, TARGET_VE_ITEM_IDS[0])
    stock_rear = _parse_table(stock_root, TARGET_VE_ITEM_IDS[1])

    if base_front.values.shape != base_rear.values.shape:
        raise RuntimeError("Base front/rear VE shape mismatch")
    if stock_front.values.shape != stock_rear.values.shape:
        raise RuntimeError("Stock front/rear VE shape mismatch")
    if base_front.values.shape != stock_front.values.shape:
        raise RuntimeError(
            f"Stock/base VE shape mismatch: stock={stock_front.values.shape}, base={base_front.values.shape}"
        )
    if not np.array_equal(base_front.row_axis, base_rear.row_axis) or not np.array_equal(
        base_front.col_axis, base_rear.col_axis
    ):
        raise RuntimeError("Base front/rear VE axes mismatch")
    if not np.array_equal(stock_front.row_axis, base_front.row_axis) or not np.array_equal(
        stock_front.col_axis, base_front.col_axis
    ):
        raise RuntimeError("Stock/base VE axes mismatch")

    src_rpm, src_tps, trim_front, trim_rear = _load_trim_csv(args.trim_csv)
    trim_front_on_ve = _resample_trim(
        src_rpm, src_tps, trim_front, base_front.row_axis * 1000.0, base_front.col_axis
    )
    trim_rear_on_ve = _resample_trim(
        src_rpm, src_tps, trim_rear, base_rear.row_axis * 1000.0, base_rear.col_axis
    )

    if args.cylinder_mode == "average":
        trim_avg = (trim_front_on_ve + trim_rear_on_ve) / 2.0
        trim_front_on_ve = trim_avg
        trim_rear_on_ve = trim_avg
        print("Cylinder mode: average (same trim map applied to front and rear)")
    else:
        print("Cylinder mode: split (cyl1->rear, cyl2->front)")

    if abs(args.trim_scale - 1.0) > 1e-9:
        trim_front_on_ve = trim_front_on_ve * args.trim_scale
        trim_rear_on_ve = trim_rear_on_ve * args.trim_scale
        print(f"Trim scale applied: x{args.trim_scale:.4f}")

    new_front = stock_front.values * (1.0 + trim_front_on_ve / 100.0) * comp_factor
    new_rear = stock_rear.values * (1.0 + trim_rear_on_ve / 100.0) * comp_factor

    min_ve = float(min(np.min(new_front), np.min(new_rear)))
    max_ve = float(max(np.max(new_front), np.max(new_rear)))
    max_delta, max_delta_idx = _max_front_rear_delta(new_front, new_rear)
    max_delta_rpm = int(round(base_front.row_axis[max_delta_idx[0]] * 1000))
    max_delta_tps = base_front.col_axis[max_delta_idx[1]]

    print("\nDry-run summary")
    print(f"  Front VE min/max: {np.min(new_front):.2f} / {np.max(new_front):.2f}")
    print(f"  Rear VE min/max:  {np.min(new_rear):.2f} / {np.max(new_rear):.2f}")
    print(f"  Global VE min/max: {min_ve:.2f} / {max_ve:.2f}")
    print(
        f"  Max |front-rear| delta: {max_delta:.2f} at rpm={max_delta_rpm}, tps={max_delta_tps:g}"
    )

    if min_ve < args.ve_floor:
        raise RuntimeError(f"VE floor gate failed: min {min_ve:.2f} < floor {args.ve_floor:.2f}")
    if max_ve > args.ve_ceiling:
        raise RuntimeError(
            f"VE ceiling gate failed: max {max_ve:.2f} > ceiling {args.ve_ceiling:.2f}"
        )
    if max_delta > args.warn_front_rear_delta:
        print(
            f"WARNING: front/rear delta {max_delta:.2f} exceeds warning threshold "
            f"{args.warn_front_rear_delta:.2f} at rpm={max_delta_rpm}, tps={max_delta_tps:g}"
        )

    if not args.write:
        print("\nDry-run only: no file written.")
        return 0

    _mutate_table_cells(base_front, new_front)
    _mutate_table_cells(base_rear, new_rear)
    _set_scalar(base_root, SCALAR_ITEM_IDS["injector_size"], args.target_injector)
    _set_scalar(base_root, SCALAR_ITEM_IDS["engine_displacement"], args.target_displacement)

    args.output_pvv.parent.mkdir(parents=True, exist_ok=True)
    base_tree.write(args.output_pvv, encoding="utf-8", xml_declaration=True)

    output_root = ET.parse(args.output_pvv).getroot()
    changed_ids, _ = _verify_output_integrity(original_root, output_root, ALLOWED_CHANGED_IDS)
    output_sha = _sha256(args.output_pvv)

    manifest_path = args.manifest_path or args.output_pvv.with_suffix(".manifest.json")
    manifest = {
        "kind": "pc_advanced_translation",
        "strategy": "fix_scalars_compensate_ve",
        "cylinder_mode": args.cylinder_mode,
        "trim_scale": args.trim_scale,
        "inputs": {
            "stock_ve_pvv": str(args.stock_ve_pvv),
            "base_pvv": str(args.base_pvv),
            "trim_csv": str(args.trim_csv),
            "sha256": {
                "stock_ve_pvv": _sha256(args.stock_ve_pvv),
                "base_pvv": _sha256(args.base_pvv),
                "trim_csv": _sha256(args.trim_csv),
            },
        },
        "mapping": {
            "cyl1_table1": "rear",
            "cyl2_table2": "front",
        },
        "scalars": {
            "injector_size_old": old_injector,
            "injector_size_new": args.target_injector,
            "displacement_old": old_disp,
            "displacement_new": args.target_displacement,
            "source_displacement_for_compensation": args.source_displacement,
        },
        "compensation_factor": comp_factor,
        "ve_summary": {
            "front_min": float(np.min(new_front)),
            "front_max": float(np.max(new_front)),
            "rear_min": float(np.min(new_rear)),
            "rear_max": float(np.max(new_rear)),
            "global_min": min_ve,
            "global_max": max_ve,
            "max_front_rear_delta": max_delta,
            "max_front_rear_delta_rpm": max_delta_rpm,
            "max_front_rear_delta_tps": float(max_delta_tps),
        },
        "output": {
            "pvv": str(args.output_pvv),
            "sha256": output_sha,
            "changed_ids": changed_ids,
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"\nWrote: {args.output_pvv}")
    print(f"SHA256: {output_sha}")
    print(f"Manifest: {manifest_path}")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Translate PC Advanced Map fuel trims to PVV using fixed scalars + VE compensation."
    )
    parser.add_argument("--stock-ve-pvv", type=Path, default=DEFAULT_STOCK_VE_PVV)
    parser.add_argument("--base-pvv", type=Path, default=DEFAULT_BASE_PVV)
    parser.add_argument("--trim-csv", type=Path, default=DEFAULT_TRIMS_CSV)
    parser.add_argument("--output-pvv", type=Path, default=DEFAULT_OUTPUT_PVV)
    parser.add_argument("--manifest-path", type=Path, default=None)

    parser.add_argument("--target-injector", type=float, default=31.07)
    parser.add_argument("--target-displacement", type=float, default=103.0)
    parser.add_argument("--source-displacement", type=float, default=95.5)
    parser.add_argument("--injector-min", type=float, default=28.0)
    parser.add_argument("--injector-max", type=float, default=34.0)
    parser.add_argument("--displacement-min", type=float, default=101.0)
    parser.add_argument("--displacement-max", type=float, default=105.0)
    parser.add_argument("--ve-floor", type=float, default=25.0)
    parser.add_argument("--ve-ceiling", type=float, default=155.0)
    parser.add_argument("--warn-front-rear-delta", type=float, default=12.0)
    parser.add_argument(
        "--cylinder-mode",
        choices=("split", "average"),
        default="split",
        help="split=respect cyl1/cyl2 maps; average=apply averaged trim to both cylinders.",
    )
    parser.add_argument(
        "--trim-scale",
        type=float,
        default=1.0,
        help="Optional multiplier on trim percent (e.g. 0.90 reduces all trims by 10%).",
    )
    parser.add_argument("--write", action="store_true")
    return parser.parse_args(argv)


if __name__ == "__main__":
    try:
        sys.exit(run(parse_args(sys.argv[1:])))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}")
        sys.exit(1)
