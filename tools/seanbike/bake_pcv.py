from __future__ import annotations

import argparse
import csv
import hashlib
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

DEFAULT_INPUT_PVV = Path(
    r"C:\CommmandCenter\Customer_Files\seanbike\exportedreadfrompv4.pvv"
)
DEFAULT_PCV_CSV = Path(r"C:\CommmandCenter\Customer_Files\seanbike\pcv_trims_clean.csv")
DEFAULT_OUTPUT_PVV = Path(r"C:\CommmandCenter\Customer_Files\seanbike\iter_1_baked.pvv")


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


def _find_item_by_id(root: ET.Element, item_id: str) -> ET.Element:
    for item in root.findall("Item"):
        if item.get("id") == item_id:
            return item
    raise ValueError(f"Could not find Item id={item_id!r}")


def _parse_scalar(root: ET.Element, item_id: str) -> float:
    item = _find_item_by_id(root, item_id)
    cell = item.find("./Rows/Row/Cell")
    if cell is None:
        raise ValueError(f"Scalar item {item_id!r} has no Rows/Row/Cell")
    raw = cell.get("value")
    if raw is None:
        raise ValueError(f"Scalar item {item_id!r} has no Cell value attribute")
    return float(raw)


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
    collected: dict[str, list[str]] = {}
    for item in root.findall("Item"):
        item_id = item.get("id", "")
        cells = [
            cell.get("value", "")
            for row in item.findall("./Rows/Row")
            for cell in row.findall("Cell")
        ]
        collected[item_id] = cells
    return collected


def _load_pcv_trims(csv_path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if not csv_path.exists():
        raise FileNotFoundError(f"PCV CSV not found: {csv_path}")

    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError("PCV CSV is missing header row")
        tps_fields = [name for name in reader.fieldnames if name.startswith("tps_")]
        if not tps_fields:
            raise ValueError("PCV CSV has no tps_* columns")
        tps_axis = np.array([float(name.replace("tps_", "")) for name in tps_fields], dtype=float)

        by_cyl: dict[str, list[tuple[float, list[float]]]] = {"front": [], "rear": []}
        for row in reader:
            cyl = (row.get("cyl") or "").strip().lower()
            if cyl not in by_cyl:
                continue
            rpm = float(row["rpm"])
            values = [float(row[field]) for field in tps_fields]
            by_cyl[cyl].append((rpm, values))

    if not by_cyl["front"] or not by_cyl["rear"]:
        raise ValueError("PCV CSV must include both front and rear rows")

    for cyl in ("front", "rear"):
        by_cyl[cyl].sort(key=lambda pair: pair[0])

    front_rpm = np.array([rpm for rpm, _ in by_cyl["front"]], dtype=float)
    rear_rpm = np.array([rpm for rpm, _ in by_cyl["rear"]], dtype=float)
    if not np.array_equal(front_rpm, rear_rpm):
        raise ValueError("Front/rear PCV RPM axes differ")

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
    # Interpolate across TPS for each source RPM row.
    interp_tps = np.vstack(
        [np.interp(dst_tps, src_tps, src_grid[row_idx], left=np.nan, right=np.nan) for row_idx in range(src_grid.shape[0])]
    )

    # Interpolate across RPM for each destination TPS column.
    out = np.vstack(
        [np.interp(dst_rpm, src_rpm, interp_tps[:, col_idx], left=np.nan, right=np.nan) for col_idx in range(interp_tps.shape[1])]
    ).T

    # No extrapolation outside PCV axis coverage.
    rpm_ok = (dst_rpm[:, None] >= src_rpm[0]) & (dst_rpm[:, None] <= src_rpm[-1])
    tps_ok = (dst_tps[None, :] >= src_tps[0]) & (dst_tps[None, :] <= src_tps[-1])
    mask = rpm_ok & tps_ok
    out = np.where(mask, out, 0.0)
    out = np.nan_to_num(out, nan=0.0)
    return out


def _apply_trim_with_clamp(
    base_ve: np.ndarray, trim_pct: np.ndarray, clamp_ratio: float = 0.10
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    proposed = base_ve * (1.0 + trim_pct / 100.0)
    lower = base_ve * (1.0 - clamp_ratio)
    upper = base_ve * (1.0 + clamp_ratio)
    clamped = np.clip(proposed, lower, upper)
    clamped_mask = np.abs(clamped - proposed) > 1e-9
    delta = clamped - base_ve
    return clamped, clamped_mask, delta


def _print_column_diff(
    label: str,
    row_axis: np.ndarray,
    col_axis: np.ndarray,
    base: np.ndarray,
    new: np.ndarray,
    target_tps: float,
) -> None:
    idx = int(np.argmin(np.abs(col_axis - target_tps)))
    tps_label = col_axis[idx]
    print(f"\n{label} @ TPS~{target_tps}% (actual axis {tps_label}%)")
    print(f"{'RPM':>7}  {'base':>8}  {'new':>8}  {'delta':>8}")
    for r in range(base.shape[0]):
        rpm = int(round(row_axis[r] * 1000))
        b = base[r, idx]
        n = new[r, idx]
        d = n - b
        print(f"{rpm:7d}  {b:8.2f}  {n:8.2f}  {d:8.2f}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_output_integrity(
    input_root: ET.Element,
    output_root: ET.Element,
    allowed_changed_ids: set[str],
) -> None:
    in_items = input_root.findall("Item")
    out_items = output_root.findall("Item")
    if len(in_items) != len(out_items):
        raise RuntimeError(
            f"Output Item count changed ({len(in_items)} -> {len(out_items)})"
        )

    in_ids = {item.get("id", "") for item in in_items}
    out_ids = {item.get("id", "") for item in out_items}
    if in_ids != out_ids:
        raise RuntimeError("Output Item id set does not match input")

    in_cells = _collect_item_cells(input_root)
    out_cells = _collect_item_cells(output_root)
    changed_ids = {item_id for item_id in in_cells if in_cells[item_id] != out_cells[item_id]}
    if not changed_ids.issubset(allowed_changed_ids):
        raise RuntimeError(
            "Unexpected non-VE items changed: "
            + ", ".join(sorted(changed_ids - allowed_changed_ids))
        )


def _mutate_table_cells(table: TableData, new_values: np.ndarray) -> None:
    rows, cols = new_values.shape
    if rows != len(table.cell_elements) or cols != len(table.cell_elements[0]):
        raise ValueError("New value shape does not match existing table shape")

    for r in range(rows):
        for c in range(cols):
            table.cell_elements[r][c].set("value", _format_value(float(new_values[r, c])))


def run(args: argparse.Namespace) -> int:
    if not args.input_pvv.exists():
        raise FileNotFoundError(f"Input PVV not found: {args.input_pvv}")
    if not args.pcv_csv.exists():
        raise FileNotFoundError(f"PCV CSV not found: {args.pcv_csv}")

    original_root = ET.parse(args.input_pvv).getroot()
    input_tree = ET.parse(args.input_pvv)
    input_root = input_tree.getroot()

    injector_size = _parse_scalar(input_root, SCALAR_ITEM_IDS["injector_size"])
    displacement = _parse_scalar(input_root, SCALAR_ITEM_IDS["engine_displacement"])

    print(f"Input tune: {args.input_pvv}")
    print(f"Injector size (lb/hr): {injector_size:.3f}")
    print(f"Engine displacement (CID): {displacement:.3f}")

    gate_errors: list[str] = []
    if not (args.injector_min <= injector_size <= args.injector_max):
        gate_errors.append(
            "Injector size sanity gate failed: "
            f"{injector_size:.3f} not in [{args.injector_min:.3f}, {args.injector_max:.3f}]"
        )
    if abs(displacement - args.expected_displacement) > 0.01:
        gate_errors.append(
            "Displacement sanity gate failed: "
            f"{displacement:.3f} is not {args.expected_displacement:.3f} CID"
        )
    if gate_errors and not args.ignore_sanity_gates:
        raise RuntimeError(" | ".join(gate_errors))
    if gate_errors and args.ignore_sanity_gates:
        print("\nSANITY GATE OVERRIDE ENABLED:")
        for err in gate_errors:
            print(f"  - {err}")
        print("Proceeding because --ignore-sanity-gates was provided.\n")

    ve_front = _parse_table(input_root, TARGET_VE_ITEM_IDS[0])
    ve_rear = _parse_table(input_root, TARGET_VE_ITEM_IDS[1])

    if ve_front.values.shape != ve_rear.values.shape:
        raise RuntimeError(
            f"Front/rear VE shape mismatch: {ve_front.values.shape} vs {ve_rear.values.shape}"
        )
    if not np.array_equal(ve_front.row_axis, ve_rear.row_axis) or not np.array_equal(
        ve_front.col_axis, ve_rear.col_axis
    ):
        raise RuntimeError("Front/rear VE axes mismatch")

    src_rpm, src_tps, front_trim, rear_trim = _load_pcv_trims(args.pcv_csv)

    trim_front_on_ve = _resample_trim(
        src_rpm, src_tps, front_trim, ve_front.row_axis * 1000.0, ve_front.col_axis
    )
    trim_rear_on_ve = _resample_trim(
        src_rpm, src_tps, rear_trim, ve_rear.row_axis * 1000.0, ve_rear.col_axis
    )

    front_new, front_clamped_mask, front_delta = _apply_trim_with_clamp(
        ve_front.values, trim_front_on_ve, clamp_ratio=0.10
    )
    rear_new, rear_clamped_mask, rear_delta = _apply_trim_with_clamp(
        ve_rear.values, trim_rear_on_ve, clamp_ratio=0.10
    )

    front_clamped_count = int(np.count_nonzero(front_clamped_mask))
    rear_clamped_count = int(np.count_nonzero(rear_clamped_mask))
    total_clamped = front_clamped_count + rear_clamped_count

    biggest_front_idx = np.unravel_index(
        int(np.argmax(np.abs(front_delta))), front_delta.shape
    )
    biggest_rear_idx = np.unravel_index(int(np.argmax(np.abs(rear_delta))), rear_delta.shape)
    biggest_front = float(front_delta[biggest_front_idx])
    biggest_rear = float(rear_delta[biggest_rear_idx])

    print("\nDry-run diff summary")
    print(f"Front clamped cells: {front_clamped_count}")
    print(f"Rear clamped cells:  {rear_clamped_count}")
    print(f"Total clamped cells: {total_clamped}")

    print(
        f"Largest front delta: {biggest_front:+.2f} at "
        f"rpm={int(round(ve_front.row_axis[biggest_front_idx[0]] * 1000))}, "
        f"tps={ve_front.col_axis[biggest_front_idx[1]]}"
    )
    print(
        f"Largest rear delta:  {biggest_rear:+.2f} at "
        f"rpm={int(round(ve_rear.row_axis[biggest_rear_idx[0]] * 1000))}, "
        f"tps={ve_rear.col_axis[biggest_rear_idx[1]]}"
    )

    _print_column_diff(
        "Front WOT column", ve_front.row_axis, ve_front.col_axis, ve_front.values, front_new, 100.0
    )
    _print_column_diff(
        "Rear WOT column", ve_rear.row_axis, ve_rear.col_axis, ve_rear.values, rear_new, 100.0
    )
    _print_column_diff(
        "Front cruise column", ve_front.row_axis, ve_front.col_axis, ve_front.values, front_new, 20.0
    )
    _print_column_diff(
        "Rear cruise column", ve_rear.row_axis, ve_rear.col_axis, ve_rear.values, rear_new, 20.0
    )

    if not args.write:
        print("\nDry-run only: no file written.")
        return 0

    _mutate_table_cells(ve_front, front_new)
    _mutate_table_cells(ve_rear, rear_new)

    args.output_pvv.parent.mkdir(parents=True, exist_ok=True)
    input_tree.write(args.output_pvv, encoding="utf-8", xml_declaration=True)

    output_tree = ET.parse(args.output_pvv)
    output_root = output_tree.getroot()
    _verify_output_integrity(
        original_root,
        output_root,
        allowed_changed_ids=set(TARGET_VE_ITEM_IDS),
    )

    output_sha = _sha256(args.output_pvv)
    print(f"\nWrote: {args.output_pvv}")
    print(f"SHA256: {output_sha}")
    print("\nPRE-FLASH REMINDER: Remove PCV from harness before flashing this file.")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bake PCV trims into a TPS-based Power Vision PVV VE table."
    )
    parser.add_argument("--input-pvv", type=Path, default=DEFAULT_INPUT_PVV)
    parser.add_argument("--pcv-csv", type=Path, default=DEFAULT_PCV_CSV)
    parser.add_argument("--output-pvv", type=Path, default=DEFAULT_OUTPUT_PVV)
    parser.add_argument(
        "--injector-min",
        type=float,
        default=3.5,
        help="Minimum accepted injector_size scalar in the sanity gate.",
    )
    parser.add_argument(
        "--injector-max",
        type=float,
        default=5.5,
        help="Maximum accepted injector_size scalar in the sanity gate.",
    )
    parser.add_argument(
        "--expected-displacement",
        type=float,
        default=100.0,
        help="Expected engine displacement scalar (CID) sanity gate value.",
    )
    parser.add_argument(
        "--ignore-sanity-gates",
        action="store_true",
        help="Continue even if injector/displacement sanity gates fail.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write output PVV. Without this flag, command runs dry-run only.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    try:
        sys.exit(run(parse_args(sys.argv[1:])))
    except Exception as exc:  # noqa: BLE001 - CLI should print a single readable error.
        print(f"ERROR: {exc}")
        sys.exit(1)
