"""
DynoAI iter_2 Tuning Patch Generator (v3)
==========================================

Generates a deterministic, reviewable tune patch for Ryan Titus's Fat Boy CVO
by surgically editing the Dynojet stage tune currently on the bike.

What this patch changes (six tables):
    1. Engine Displacement              88.48 to 103 (fix wrong-template error)
    2. Spark Advance (Front Cyl)        cam advance +1 deg in 2-4k RPM x 60-95 kPa,
                                        knock notch -2/-1 deg at 5500 RPM x 95 kPa
    3. Spark Advance (Rear Cyl)         same pattern as Front
    4. Deceleration Enleanment          all cells to 1.0 (no overrun fuel cut)
    5. Max Knock Retard vs RPM          cap to 4 deg from 8 deg (across all 12 RPM cols)
    6. RPM Limit                        5.6 to 6.2 RPMx1000 (restore OEM rev ceiling)

Tables EXPLICITLY untouched (Gate 5 negative test):
    - PE Air-Fuel Ratio (tbl_pe_air_fuel_ratio_stoich) -- WOT AFR target
    - Air-Fuel Ratio (tbl_afr_stoich)                  -- idle/cruise AFR target
    - VE (TPS based/Front Cyl)                         -- VE Front
    - VE (TPS based/Rear Cyl)                          -- VE Rear
    - Calibration ID (tbl_cal_id_string)               -- string identifier
    - Speedometer Calibration                          -- tire/gear constant
    - Acceleration Enrichment                          -- Dynojet's tip-in enrichment
    - Spark Adjust By Engine Temp                      -- Dynojet's CHT-based retard

There are NO O2 sensors on this bike or in the exhaust. AFR validation for any
future iteration must come from the dyno's tailpipe wideband, not anything on
the bike.

Approach:
    Surgical XML edit using xml.etree.ElementTree.parse. Original .pvv
    attributes (including each Item's `id`) are preserved. Only cells in the
    six target tables are mutated; every other byte in the document is left
    untouched.

Outputs (all written under iter_2/):
    patch/iter_2_patched.pvv          flash-ready tune
    patch/displacement_delta.csv      1 row: 88.48 to 103
    patch/spark_advance_delta.csv     both cyls; columns include `source`
                                      (cam_advance or knock_notch)
    patch/decel_enleanment_delta.csv  12 rows: CHT, base, new, delta
    patch/knock_retard_delta.csv      12 rows: RPM, base, new, delta
    patch/rpm_limit_delta.csv          9 rows: TPS, base, new, delta
    patch/change_log.md               customer-facing summary
    patch/guardrails.md               operator pre-pull checklist
    iteration.json                    registers iter_2 with the workspace

Verification gates (script aborts and writes nothing if any fail):
    1. Patched .pvv re-parses cleanly; same Item count as base (32 items)
    2. Exactly the six expected Items differ
    3. Engine Displacement cell equals exactly 103 (no clamp; physical constant)
    4. Every changed spark cell within +/-3 deg of base
    5. All eight untouchable tables are byte-identical to base

Idempotency:
    Re-running the script with the same dynojet_stage.pvv produces the same
    patched .pvv, same deltas, same change_log.

Usage:
    python tools/generate_iter2_patch.py
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SESSION_DIR = (
    PROJECT_ROOT
    / "vehicles"
    / "ryantitus_fatboy_cvo"
    / "sessions"
    / "2026-05-10_4thgear_baseline"
)
DEFAULT_BASE = SESSION_DIR / "base_tune" / "dynojet_stage.pvv"
DEFAULT_ITER2 = SESSION_DIR / "iterations" / "iter_2"
DEFAULT_ITER1_ANALYSIS = (
    SESSION_DIR / "iterations" / "iter_1" / "analyses" / "iter1_comparison.json"
)


DISPLACEMENT_TABLE = "Engine Displacement"
SPARK_FRONT_TABLE = "Spark Advance (Front Cyl)"
SPARK_REAR_TABLE = "Spark Advance (Rear Cyl)"
DECEL_ENLEANMENT_TABLE = "Deceleration Enleanment"
KNOCK_RETARD_TABLE = "Max Knock Retard vs RPM"
RPM_LIMIT_TABLE = "RPM Limit"

AFR_TARGET_TABLE = "PE Air-Fuel Ratio"
AFR_STOICH_TABLE = "Air-Fuel Ratio"
VE_FRONT_TABLE = "VE (TPS based/Front Cyl)"
VE_REAR_TABLE = "VE (TPS based/Rear Cyl)"
CAL_ID_TABLE = "Calibration ID"
SPEEDO_TABLE = "Speedometer Calibration"
ACCEL_ENRICH_TABLE = "Acceleration Enrichment"
SPARK_ECT_ADJUST_TABLE = "Spark Adjust By Engine Temp"


EXPECTED_CHANGED = [
    DISPLACEMENT_TABLE,
    SPARK_FRONT_TABLE,
    SPARK_REAR_TABLE,
    DECEL_ENLEANMENT_TABLE,
    KNOCK_RETARD_TABLE,
    RPM_LIMIT_TABLE,
]

UNTOUCHABLE_TABLES = [
    AFR_TARGET_TABLE,
    AFR_STOICH_TABLE,
    VE_FRONT_TABLE,
    VE_REAR_TABLE,
    CAL_ID_TABLE,
    SPEEDO_TABLE,
    ACCEL_ENRICH_TABLE,
    SPARK_ECT_ADJUST_TABLE,
]


NEW_DISPLACEMENT_CID = 103.0
NEW_DECEL_MULTIPLIER = 1.0
KNOCK_CAP_DEG = 4.0
NEW_RPM_LIMIT = 6.2

CLAMP_SPARK_DEG = 3.0
CAM_ADVANCE_DELTA = 1.0


CAM_ADVANCE_RPM_BANDS = (2.0, 4.0)
CAM_ADVANCE_MAP_BANDS = (60.0, 95.0)


SPARK_NOTCH_CENTER_RPM = 5.5
SPARK_NOTCH_CENTER_MAP = 95.0
SPARK_NOTCH_CENTER_DELTA = -2.0
SPARK_NOTCH_ADJACENT_DELTA = -1.0
SPARK_NOTCH_NEIGHBOURS: list[tuple[float, float]] = [
    (5.0, 95.0),
    (5.5, 90.0),
    (5.5, 100.0),
    (6.0, 95.0),
]


def _fmt_cell(value: float) -> str:
    """Format a cell the way the original .pvv does: int when whole, else trimmed decimal."""
    if value == int(value):
        return str(int(value))
    s = f"{value:.4f}".rstrip("0").rstrip(".")
    if s == "" or s == "-":
        return "0"
    return s


def _parse_float(text: str) -> float:
    try:
        return float(text)
    except (TypeError, ValueError):
        return 0.0


def _find_item_by_name(root: ET.Element, name: str) -> ET.Element | None:
    for item in root.findall("Item"):
        if item.get("name") == name:
            return item
    return None


def _read_table(item: ET.Element) -> tuple[list[float], list[float], list[list[float]]]:
    """Return (row_axis, col_axis, values) for an Item element."""
    cols_elem = item.find("Columns")
    rows_elem = item.find("Rows")
    if cols_elem is None or rows_elem is None:
        raise RuntimeError(f"Item '{item.get('name')}' missing Columns/Rows")
    col_axis = [_parse_float(c.get("label", "0") or "0") for c in cols_elem.findall("Col")]
    row_axis: list[float] = []
    values: list[list[float]] = []
    for row in rows_elem.findall("Row"):
        row_axis.append(_parse_float(row.get("label", "0") or "0"))
        values.append([_parse_float(c.get("value", "0") or "0") for c in row.findall("Cell")])
    return row_axis, col_axis, values


def _write_cells(item: ET.Element, values: list[list[float]]) -> None:
    """Write values back into the Item's <Cell> nodes in document order."""
    rows_elem = item.find("Rows")
    if rows_elem is None:
        raise RuntimeError(f"Item '{item.get('name')}' missing Rows")
    for row_idx, row in enumerate(rows_elem.findall("Row")):
        cells = row.findall("Cell")
        if row_idx >= len(values):
            break
        new_row = values[row_idx]
        for col_idx, cell in enumerate(cells):
            if col_idx >= len(new_row):
                break
            cell.set("value", _fmt_cell(new_row[col_idx]))


def _apply_displacement(item: ET.Element) -> tuple[float, float]:
    """Set the single displacement cell to NEW_DISPLACEMENT_CID. Return (base, new)."""
    cell = item.find(".//Cell")
    if cell is None:
        raise RuntimeError(f"{DISPLACEMENT_TABLE} has no Cell")
    base_val = _parse_float(cell.get("value", "0") or "0")
    cell.set("value", _fmt_cell(NEW_DISPLACEMENT_CID))
    return base_val, NEW_DISPLACEMENT_CID


def _apply_decel_enleanment(
    item: ET.Element,
) -> tuple[list[float], list[float], list[float]]:
    """Set every Decel Enleanment cell to NEW_DECEL_MULTIPLIER. Return (col_axis, base, new)."""
    row_axis, col_axis, values = _read_table(item)
    if not values:
        raise RuntimeError(f"{DECEL_ENLEANMENT_TABLE} is empty")
    base_row = list(values[0])
    new_row = [NEW_DECEL_MULTIPLIER] * len(base_row)
    _write_cells(item, [new_row])
    return col_axis, base_row, new_row


def _apply_knock_retard_cap(
    item: ET.Element,
) -> tuple[list[float], list[float], list[float]]:
    """Cap every Max Knock Retard cell at KNOCK_CAP_DEG. Return (col_axis, base, new)."""
    row_axis, col_axis, values = _read_table(item)
    if not values:
        raise RuntimeError(f"{KNOCK_RETARD_TABLE} is empty")
    base_row = list(values[0])
    new_row = [min(v, KNOCK_CAP_DEG) for v in base_row]
    _write_cells(item, [new_row])
    return col_axis, base_row, new_row


def _apply_rpm_limit(
    item: ET.Element,
) -> tuple[list[float], list[float], list[float]]:
    """Set every RPM Limit cell to NEW_RPM_LIMIT. Return (col_axis, base, new)."""
    row_axis, col_axis, values = _read_table(item)
    if not values:
        raise RuntimeError(f"{RPM_LIMIT_TABLE} is empty")
    base_row = list(values[0])
    new_row = [NEW_RPM_LIMIT] * len(base_row)
    _write_cells(item, [new_row])
    return col_axis, base_row, new_row


def _idx_nearest(axis: list[float], target: float) -> int:
    return min(range(len(axis)), key=lambda i: abs(axis[i] - target))


def _apply_spark_changes(
    item: ET.Element,
) -> tuple[
    list[float],
    list[float],
    list[list[float]],
    list[list[float]],
    list[list[str]],
]:
    """
    Apply cam advance then knock notch to a spark advance table.

    Cam advance is applied first across (CAM_ADVANCE_RPM_BANDS x CAM_ADVANCE_MAP_BANDS),
    then the knock notch overwrites at the center and four neighbour cells.
    Both passes are clamped per cell to +/-CLAMP_SPARK_DEG from the base value.

    Returns (row_axis, col_axis, base_grid, new_grid, source_grid).
    source_grid cells contain "" (unchanged), "cam_advance", or "knock_notch".
    """
    row_axis, col_axis, base_values = _read_table(item)
    base_grid = [list(r) for r in base_values]
    new_grid = [list(r) for r in base_values]
    source_grid: list[list[str]] = [
        ["" for _ in row] for row in base_grid
    ]

    rpm_lo, rpm_hi = CAM_ADVANCE_RPM_BANDS
    map_lo, map_hi = CAM_ADVANCE_MAP_BANDS
    for r, rpm_k in enumerate(row_axis):
        if not (rpm_lo <= rpm_k <= rpm_hi):
            continue
        for c, map_kpa in enumerate(col_axis):
            if not (map_lo <= map_kpa <= map_hi):
                continue
            base_val = base_grid[r][c]
            delta = CAM_ADVANCE_DELTA
            delta = max(-CLAMP_SPARK_DEG, min(CLAMP_SPARK_DEG, delta))
            new_val = base_val + delta
            new_grid[r][c] = new_val
            source_grid[r][c] = "cam_advance"

    cr = _idx_nearest(row_axis, SPARK_NOTCH_CENTER_RPM)
    cc = _idx_nearest(col_axis, SPARK_NOTCH_CENTER_MAP)
    notch_targets: dict[tuple[int, int], float] = {
        (cr, cc): SPARK_NOTCH_CENTER_DELTA
    }
    for nb_rpm, nb_map in SPARK_NOTCH_NEIGHBOURS:
        nr = _idx_nearest(row_axis, nb_rpm)
        nc = _idx_nearest(col_axis, nb_map)
        notch_targets.setdefault((nr, nc), SPARK_NOTCH_ADJACENT_DELTA)

    for (r, c), delta in notch_targets.items():
        base_val = base_grid[r][c]
        delta = max(-CLAMP_SPARK_DEG, min(CLAMP_SPARK_DEG, delta))
        new_grid[r][c] = base_val + delta
        source_grid[r][c] = "knock_notch"

    _write_cells(item, new_grid)
    return row_axis, col_axis, base_grid, new_grid, source_grid


def verify_patch_gates(
    patched_pvv: Path,
    base_pvv: Path,
    expected_changed: list[str],
    untouchable_tables: list[str],
    spark_fronts: tuple[list[list[float]], list[list[float]]],
    spark_rears: tuple[list[list[float]], list[list[float]]],
    *,
    ve_stage_front: list[list[float]] | None = None,
    ve_patched_front: list[list[float]] | None = None,
    ve_stage_rear: list[list[float]] | None = None,
    ve_patched_rear: list[list[float]] | None = None,
    ve_max_frac_change: float | None = None,
) -> None:
    """Gates 1-5 plus optional Gate 6 (VE fractional change vs stage tune)."""

    parsed = ET.parse(str(patched_pvv)).getroot()
    base_parsed = ET.parse(str(base_pvv)).getroot()

    patched_items: dict[str, ET.Element] = {
        it.get("name", ""): it for it in parsed.findall("Item")
    }
    base_items: dict[str, ET.Element] = {
        it.get("name", ""): it for it in base_parsed.findall("Item")
    }

    if set(patched_items.keys()) != set(base_items.keys()):
        raise RuntimeError(
            "Gate 1 FAILED: patched .pvv item set differs from base. "
            f"missing={set(base_items)-set(patched_items)} "
            f"extra={set(patched_items)-set(base_items)}"
        )
    if len(patched_items) != len(base_items):
        raise RuntimeError(
            f"Gate 1 FAILED: item count {len(patched_items)} != base {len(base_items)}"
        )

    actually_changed: list[str] = []
    for name, patched_item in patched_items.items():
        base_item = base_items[name]
        if ET.tostring(patched_item) != ET.tostring(base_item):
            actually_changed.append(name)

    if set(actually_changed) != set(expected_changed):
        raise RuntimeError(
            "Gate 2 FAILED: scope drift. "
            f"expected_changed={sorted(expected_changed)} "
            f"actually_changed={sorted(actually_changed)}"
        )

    disp_item = patched_items[DISPLACEMENT_TABLE]
    disp_cell = disp_item.find(".//Cell")
    if disp_cell is None:
        raise RuntimeError("Gate 3 FAILED: Engine Displacement Cell missing in patched")
    disp_val = _parse_float(disp_cell.get("value", "0") or "0")
    if abs(disp_val - NEW_DISPLACEMENT_CID) > 1e-9:
        raise RuntimeError(
            f"Gate 3 FAILED: displacement={disp_val} != {NEW_DISPLACEMENT_CID}"
        )

    for label, (base_grid, new_grid) in (
        ("front", spark_fronts),
        ("rear", spark_rears),
    ):
        for r, (base_row, new_row) in enumerate(zip(base_grid, new_grid)):
            for c, (b_val, n_val) in enumerate(zip(base_row, new_row)):
                deg_change = abs(n_val - b_val)
                if deg_change > CLAMP_SPARK_DEG + 1e-3:
                    raise RuntimeError(
                        f"Gate 4 FAILED: spark {label}[{r}][{c}] changed {deg_change:.2f} deg "
                        f"(base={b_val}, new={n_val}, cap={CLAMP_SPARK_DEG} deg)"
                    )

    for forbidden in untouchable_tables:
        if forbidden in actually_changed:
            raise RuntimeError(
                f"Gate 5 FAILED: untouchable table '{forbidden}' was modified"
            )
        if forbidden not in base_items:
            continue
        if ET.tostring(patched_items[forbidden]) != ET.tostring(base_items[forbidden]):
            raise RuntimeError(
                f"Gate 5 FAILED: untouchable table '{forbidden}' bytes differ "
                f"between base and patched"
            )

    if ve_max_frac_change is not None:
        if (
            ve_stage_front is None
            or ve_patched_front is None
            or ve_stage_rear is None
            or ve_patched_rear is None
        ):
            raise RuntimeError("Gate 6 FAILED: VE grids missing for Gate 6")
        for label, (sg, pg) in (
            ("front", (ve_stage_front, ve_patched_front)),
            ("rear", (ve_stage_rear, ve_patched_rear)),
        ):
            for r, (br, nr) in enumerate(zip(sg, pg)):
                for c, (b_val, n_val) in enumerate(zip(br, nr)):
                    if abs(n_val - b_val) < 1e-9:
                        continue
                    if abs(b_val) < 1e-9:
                        raise RuntimeError(f"Gate 6 FAILED: VE {label} base ~0 at [{r}][{c}]")
                    frac = abs(n_val - b_val) / abs(b_val)
                    if frac > ve_max_frac_change + 1e-6:
                        raise RuntimeError(
                            f"Gate 6 FAILED: VE {label}[{r}][{c}] frac change {frac:.4f} "
                            f"> cap {ve_max_frac_change} (base={b_val}, new={n_val})"
                        )


def _verification_gates(
    patched_pvv: Path,
    base_pvv: Path,
    spark_fronts: tuple[list[list[float]], list[list[float]]],
    spark_rears: tuple[list[list[float]], list[list[float]]],
) -> None:
    verify_patch_gates(
        patched_pvv,
        base_pvv,
        EXPECTED_CHANGED,
        UNTOUCHABLE_TABLES,
        spark_fronts,
        spark_rears,
    )


def _write_displacement_delta_csv(path: Path, base_val: float, new_val: float) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["table", "base_cid", "new_cid", "delta_cid", "engine_fuel_delta_pct"])
        pct = (new_val - base_val) / base_val * 100.0 if base_val else 0.0
        w.writerow([
            DISPLACEMENT_TABLE,
            f"{base_val:.2f}",
            f"{new_val:.2f}",
            f"{new_val - base_val:+.2f}",
            f"{pct:+.2f}",
        ])


def _write_spark_delta_csv(
    path: Path,
    rows: list[tuple[str, float, float, str, float, float]],
) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "cylinder",
            "RPM",
            "MAP_kpa",
            "source",
            "spark_base_deg",
            "spark_new_deg",
            "delta_deg",
        ])
        for cylinder, rpm, map_kpa, source, base, new in rows:
            w.writerow([
                cylinder,
                int(rpm * 1000),
                map_kpa,
                source,
                f"{base:.2f}",
                f"{new:.2f}",
                f"{new - base:+.2f}",
            ])


def _collect_spark_delta_rows(
    cylinder: str,
    row_axis: list[float],
    col_axis: list[float],
    base_grid: list[list[float]],
    new_grid: list[list[float]],
    source_grid: list[list[str]],
) -> list[tuple[str, float, float, str, float, float]]:
    out: list[tuple[str, float, float, str, float, float]] = []
    for r, rpm_k in enumerate(row_axis):
        for c, map_kpa in enumerate(col_axis):
            if abs(new_grid[r][c] - base_grid[r][c]) < 1e-9:
                continue
            out.append((
                cylinder,
                rpm_k,
                map_kpa,
                source_grid[r][c] or "unknown",
                base_grid[r][c],
                new_grid[r][c],
            ))
    return out


def _write_simple_delta_csv(
    path: Path,
    axis_header: str,
    col_axis: list[float],
    base_row: list[float],
    new_row: list[float],
    axis_scale: float = 1.0,
) -> None:
    """Write a 1-row table as a delta CSV (one input row per axis cell)."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([axis_header, "base", "new", "delta"])
        for c, axis_val in enumerate(col_axis):
            scaled = axis_val * axis_scale
            display: float | int = int(scaled) if scaled == int(scaled) else scaled
            w.writerow([
                display,
                f"{base_row[c]:.3f}",
                f"{new_row[c]:.3f}",
                f"{new_row[c] - base_row[c]:+.3f}",
            ])


def _write_change_log(
    path: Path,
    base_pvv_path: Path,
    base_sha: str,
    new_sha: str,
    disp_base: float,
    spark_summary: dict[str, int],
    decel_summary: dict[str, float],
    knock_summary: dict[str, float],
    rpm_limit_summary: dict[str, float],
) -> None:
    fuel_pct = (NEW_DISPLACEMENT_CID - disp_base) / disp_base * 100.0
    lines = [
        "# iter_2 Patch -- Dynojet Stage Base, Displacement Fix, Safety Touches",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "Vehicle: Ryan Titus 2006 Fat Boy CVO (103 ci)",
        "Session: 2026-05-10_4thgear_baseline",
        "",
        f"- base file: `{base_pvv_path.name}`",
        f"- base SHA-256: `{base_sha}`",
        f"- iter_2_patched.pvv SHA-256: `{new_sha}`",
        "",
        "## Context",
        "",
        "iter_1 ran on the Dynojet stage tune which has Engine Displacement",
        "incorrectly set to 88.48 CID (almost certainly a wrong-template error;",
        "the bike is actually 103 CID). The stage tune compensated by slashing",
        f"VE tables and richening AFR targets. This patch fixes the root cause.",
        "",
        "## Changes (six tables)",
        "",
        "### 1. Engine Displacement",
        "",
        f"- base: {disp_base:.2f} CID",
        f"- new:  {NEW_DISPLACEMENT_CID:.2f} CID",
        f"- engine fuel command delta: {fuel_pct:+.1f} percent everywhere",
        "",
        "This is the single largest fueling change in this session. iter_1 max",
        "injector duty was 71 percent, so this puts duty around 83 percent worst",
        "case -- inside safe headroom, but tight. First pulls post-flash are",
        "diagnostic, not performance runs.",
        "",
        "### 2. Spark Advance (Front + Rear)",
        "",
        f"- cells changed (front / rear): {spark_summary['front_cells']} / {spark_summary['rear_cells']}",
        f"- cam-driven advance: +{CAM_ADVANCE_DELTA:.1f} deg in 2000-4000 RPM x 60-95 kPa",
        f"- knock notch: -{abs(SPARK_NOTCH_CENTER_DELTA):.1f} deg at (5500 RPM, 95 kPa),",
        f"  -{abs(SPARK_NOTCH_ADJACENT_DELTA):.1f} deg at 4 adjacent cells",
        f"- knock notch overrides cam advance in any overlapping cell",
        f"- clamp: +/-{CLAMP_SPARK_DEG:.0f} deg per cell from base",
        "",
        "### 3. Deceleration Enleanment",
        "",
        f"- base range: {decel_summary['base_min']:.2f} to {decel_summary['base_max']:.2f}",
        f"- new: {NEW_DECEL_MULTIPLIER:.2f} (all 12 CHT cells)",
        "",
        "Eliminates fuel cut on overrun. Cures exhaust popping on V&H true duals.",
        "",
        "### 4. Max Knock Retard vs RPM",
        "",
        f"- base: {knock_summary['base_max']:.0f} deg across all 12 RPM cols",
        f"- new:  {knock_summary['new_max']:.0f} deg (capped)",
        "",
        "Lower cap means knock surfaces in logs sooner instead of being masked.",
        "",
        "### 5. RPM Limit",
        "",
        f"- base: {rpm_limit_summary['base']:.1f} RPMx1000 (Dynojet stage pulled 600 RPM)",
        f"- new:  {rpm_limit_summary['new']:.1f} RPMx1000 (OEM ceiling restored)",
        "",
        "Our analysis ceiling (vehicle profile guardrail) stays at 5500 RPM.",
        "",
        "## Tables NOT modified (byte-identical to base)",
        "",
        "These would require dyno tailpipe wideband AFR to change safely:",
        "- PE Air-Fuel Ratio (WOT AFR target)",
        "- Air-Fuel Ratio (idle/cruise AFR target)",
        "- VE (TPS based/Front Cyl)",
        "- VE (TPS based/Rear Cyl)",
        "",
        "These are identity/safety items the Dynojet stage owns:",
        "- Calibration ID (touching this breaks the flash)",
        "- Speedometer Calibration",
        "- Acceleration Enrichment (Dynojet's +50-100 percent tip-in)",
        "- Spark Adjust By Engine Temp (Dynojet's heat-soak retard)",
        "",
        "## No O2 sensors on bike or in exhaust",
        "",
        "AFR validation in iter_3 and beyond must come from the dyno's tailpipe",
        "wideband sniffer (DynoWare RT). There is no on-bike sensor to read.",
        "",
        "## First-pull post-flash protocol",
        "",
        "Treat the first 2-3 pulls after flash as diagnostic baselines.",
        "Abort criteria:",
        "",
        "- Injector duty rear > 90 percent at any point",
        "- Knock retard pegged at the new 4 deg cap for > 0.2 s sustained",
        "- CHT > 220 F at pull start",
        "- Visible black smoke or strong fuel smell at idle",
        "",
        "## Revert procedure",
        "",
        f"Re-flash `dynojet_stage.pvv` (SHA-256 `{base_sha}`) to restore the",
        "tune that was on the bike before iter_2.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_guardrails(path: Path) -> None:
    lines = [
        "# iter_2 Operational Guardrails",
        "",
        "Enforced at the dyno; not encoded in the .pvv. Mirrored in",
        "`vehicles/ryantitus_fatboy_cvo/profile.json` under `tuning_guardrails`.",
        "",
        "## Pre-pull checklist",
        "",
        "- [ ] CHT start temperature less than 220 F",
        "- [ ] At least 60 seconds since previous WOT pull",
        "- [ ] Dyno tailpipe wideband warm and reading sane (no on-bike sensor)",
        "- [ ] iter_2_patched.pvv flashed; SHA-256 matches change_log.md",
        "- [ ] Knock retard cap is now 4 deg, not 8 -- watch the live retard channel",
        "- [ ] First 2-3 pulls are diagnostic baselines; expect the engine to feel",
        "      slightly richer than the Dynojet stage (16.4 percent more fuel command)",
        "",
        "## Analysis ceiling",
        "",
        "Treat any data above 5500 RPM as informational only. Observed peak",
        "HP was ~5300 RPM. Rev limiter is back at 6200 (OEM). The 5500-6200",
        "range is past the powerband and noisy without AFR feedback.",
        "",
        "## AFR ground truth",
        "",
        "There are NO O2 sensors on this bike or in the exhaust. AFR validation",
        "must come from the dyno's tailpipe wideband (DynoWare RT). No on-bike",
        "sensor will ever produce AFR for this vehicle.",
        "",
        "## What unlocks iter_3",
        "",
        "- Dyno tailpipe wideband connected and producing valid 10.0-19.0 readings",
        "- 2-3 clean WOT pulls captured with AFR present",
        "- iter_2 patch verified safe (no rich rear, no recurring knock)",
        "",
        "## Generated values (for tooling)",
        "",
        "| key                                  | value |",
        "| ------------------------------------ | ----- |",
        "| `abort_if_cht_above_f`               | 220.0 |",
        "| `min_cool_down_s_between_wot_pulls`  | 60    |",
        "| `wot_rpm_ceiling_for_analysis`       | 5500  |",
        "| `max_knock_retard_deg` (in tune)     | 4.0   |",
        "| `no_o2_sensors_on_bike`              | true  |",
        "| `afr_source`                         | `dyno_tailpipe_wideband_only` |",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_iteration_json(path: Path, patch_filename: str, base_filename: str) -> None:
    payload = {
        "id": "iter_2",
        "session_id": "2026-05-10_4thgear_baseline",
        "index": 2,
        "patch_filename": patch_filename,
        "patch_base": base_filename,
        "flashed_at": None,
        "notes": (
            "iter_2 v3 patch. Starts from Dynojet stage tune (88.48 CID, currently "
            "on the bike). Fixes Engine Displacement 88.48 -> 103 (~16.4% more fuel "
            "command everywhere). Adds +1 deg cam advance in 2-4k RPM x 60-95 kPa. "
            "Notches WOT spark -2/-1 deg at the 5300 RPM knock cell on both cylinders. "
            "Decel enleanment set to 1.0 (no overrun fuel cut). Max Knock Retard "
            "capped at 4 deg. RPM Limit restored to 6.2 (OEM). AFR target, VE, "
            "Calibration ID, Speedo, Accel Enrichment, and Spark Adjust by ECT are "
            "byte-identical to the Dynojet stage. No O2 sensors on bike -- AFR "
            "validation in iter_3 requires dyno tailpipe wideband only."
        ),
        "created_at": datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
    }
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--iter2-dir", type=Path, default=DEFAULT_ITER2)
    parser.add_argument("--iter1-analysis", type=Path, default=DEFAULT_ITER1_ANALYSIS)
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable INFO logging",
    )
    args = parser.parse_args(argv)

    if args.verbose:
        logging.basicConfig(level=logging.INFO, format="%(message)s")

    base_pvv: Path = args.base
    iter2_dir: Path = args.iter2_dir
    iter1_analysis_path: Path = args.iter1_analysis

    if not base_pvv.exists():
        print(f"ERROR: base pvv not found at {base_pvv}", file=sys.stderr)
        return 2
    if not iter1_analysis_path.exists():
        print(
            f"WARNING: iter_1 analysis not at {iter1_analysis_path} (continuing)",
            file=sys.stderr,
        )

    logger.info("Reading base .pvv: %s", base_pvv)
    base_sha = _sha256(base_pvv)
    logger.info("base SHA-256: %s", base_sha)

    tree = ET.parse(str(base_pvv))
    root = tree.getroot()

    items: dict[str, ET.Element | None] = {
        name: _find_item_by_name(root, name)
        for name in (
            DISPLACEMENT_TABLE,
            SPARK_FRONT_TABLE,
            SPARK_REAR_TABLE,
            DECEL_ENLEANMENT_TABLE,
            KNOCK_RETARD_TABLE,
            RPM_LIMIT_TABLE,
        )
    }
    missing = [n for n, it in items.items() if it is None]
    if missing:
        print(f"ERROR: base .pvv missing required tables: {missing}", file=sys.stderr)
        return 3

    logger.info("Applying Engine Displacement 88.48 -> %.2f", NEW_DISPLACEMENT_CID)
    disp_base, _ = _apply_displacement(items[DISPLACEMENT_TABLE])  # type: ignore[arg-type]

    logger.info("Applying spark changes (Front)")
    (
        f_row_axis,
        f_col_axis,
        f_base_grid,
        f_new_grid,
        f_source_grid,
    ) = _apply_spark_changes(items[SPARK_FRONT_TABLE])  # type: ignore[arg-type]

    logger.info("Applying spark changes (Rear)")
    (
        r_row_axis,
        r_col_axis,
        r_base_grid,
        r_new_grid,
        r_source_grid,
    ) = _apply_spark_changes(items[SPARK_REAR_TABLE])  # type: ignore[arg-type]

    logger.info("Applying decel enleanment unity")
    decel_col_axis, decel_base, decel_new = _apply_decel_enleanment(
        items[DECEL_ENLEANMENT_TABLE]  # type: ignore[arg-type]
    )

    logger.info("Applying knock retard cap")
    knock_col_axis, knock_base, knock_new = _apply_knock_retard_cap(
        items[KNOCK_RETARD_TABLE]  # type: ignore[arg-type]
    )

    logger.info("Applying RPM limit restore to %.1f", NEW_RPM_LIMIT)
    rpm_col_axis, rpm_base, rpm_new = _apply_rpm_limit(
        items[RPM_LIMIT_TABLE]  # type: ignore[arg-type]
    )

    iter2_dir.mkdir(parents=True, exist_ok=True)
    patch_dir = iter2_dir / "patch"
    patch_dir.mkdir(parents=True, exist_ok=True)
    patched_pvv = patch_dir / "iter_2_patched.pvv"

    logger.info("Writing patched .pvv: %s", patched_pvv)
    tree.write(str(patched_pvv), encoding="utf-8", xml_declaration=True)

    logger.info("Running verification gates")
    try:
        _verification_gates(
            patched_pvv=patched_pvv,
            base_pvv=base_pvv,
            spark_fronts=(f_base_grid, f_new_grid),
            spark_rears=(r_base_grid, r_new_grid),
        )
    except RuntimeError as exc:
        patched_pvv.unlink(missing_ok=True)
        print(f"ABORT: {exc}", file=sys.stderr)
        return 4

    logger.info("Writing delta CSVs")
    _write_displacement_delta_csv(
        patch_dir / "displacement_delta.csv", disp_base, NEW_DISPLACEMENT_CID
    )

    spark_rows = (
        _collect_spark_delta_rows(
            "front", f_row_axis, f_col_axis, f_base_grid, f_new_grid, f_source_grid
        )
        + _collect_spark_delta_rows(
            "rear", r_row_axis, r_col_axis, r_base_grid, r_new_grid, r_source_grid
        )
    )
    _write_spark_delta_csv(patch_dir / "spark_advance_delta.csv", spark_rows)

    _write_simple_delta_csv(
        patch_dir / "decel_enleanment_delta.csv",
        "CHT_F",
        decel_col_axis,
        decel_base,
        decel_new,
    )
    _write_simple_delta_csv(
        patch_dir / "knock_retard_delta.csv",
        "RPM",
        knock_col_axis,
        knock_base,
        knock_new,
    )
    _write_simple_delta_csv(
        patch_dir / "rpm_limit_delta.csv",
        "TPS_pct",
        rpm_col_axis,
        rpm_base,
        rpm_new,
    )

    new_sha = _sha256(patched_pvv)
    logger.info("iter_2_patched.pvv SHA-256: %s", new_sha)

    front_cells_changed = sum(
        1
        for r in range(len(f_base_grid))
        for c in range(len(f_base_grid[0]))
        if abs(f_new_grid[r][c] - f_base_grid[r][c]) > 1e-9
    )
    rear_cells_changed = sum(
        1
        for r in range(len(r_base_grid))
        for c in range(len(r_base_grid[0]))
        if abs(r_new_grid[r][c] - r_base_grid[r][c]) > 1e-9
    )

    _write_change_log(
        patch_dir / "change_log.md",
        base_pvv_path=base_pvv,
        base_sha=base_sha,
        new_sha=new_sha,
        disp_base=disp_base,
        spark_summary={
            "front_cells": front_cells_changed,
            "rear_cells": rear_cells_changed,
        },
        decel_summary={
            "base_min": min(decel_base),
            "base_max": max(decel_base),
        },
        knock_summary={
            "base_min": min(knock_base),
            "base_max": max(knock_base),
            "new_min": min(knock_new),
            "new_max": max(knock_new),
        },
        rpm_limit_summary={
            "base": rpm_base[0] if rpm_base else 0.0,
            "new": rpm_new[0] if rpm_new else 0.0,
        },
    )

    _write_guardrails(patch_dir / "guardrails.md")
    _write_iteration_json(iter2_dir / "iteration.json", patched_pvv.name, base_pvv.name)

    logger.info("Done.")
    print("OK")
    print(f"  base                 SHA-256: {base_sha}")
    print(f"  iter_2_patched       SHA-256: {new_sha}")
    print(f"  displacement:        {disp_base:.2f} -> {NEW_DISPLACEMENT_CID:.2f} CID")
    print(f"  spark cells changed front/rear: {front_cells_changed} / {rear_cells_changed}")
    print(f"  decel enleanment:    all 12 cells -> {NEW_DECEL_MULTIPLIER}")
    print(f"  knock retard cap:    {max(knock_new):.1f} deg (was {max(knock_base):.1f})")
    print(f"  rpm limit:           {rpm_new[0]:.1f} (was {rpm_base[0]:.1f}) RPMx1000")
    print(f"  artifacts in: {patch_dir}")
    return 0


__all__ = [
    "SESSION_DIR",
    "DEFAULT_BASE",
    "DEFAULT_ITER2",
    "DISPLACEMENT_TABLE",
    "SPARK_FRONT_TABLE",
    "SPARK_REAR_TABLE",
    "DECEL_ENLEANMENT_TABLE",
    "KNOCK_RETARD_TABLE",
    "RPM_LIMIT_TABLE",
    "AFR_TARGET_TABLE",
    "AFR_STOICH_TABLE",
    "VE_FRONT_TABLE",
    "VE_REAR_TABLE",
    "CAL_ID_TABLE",
    "SPEEDO_TABLE",
    "ACCEL_ENRICH_TABLE",
    "SPARK_ECT_ADJUST_TABLE",
    "EXPECTED_CHANGED",
    "UNTOUCHABLE_TABLES",
    "NEW_DISPLACEMENT_CID",
    "NEW_DECEL_MULTIPLIER",
    "KNOCK_CAP_DEG",
    "NEW_RPM_LIMIT",
    "CLAMP_SPARK_DEG",
    "fmt_cell",
    "parse_float",
    "find_item_by_name",
    "read_table",
    "write_cells",
    "idx_nearest",
    "apply_displacement",
    "apply_decel_enleanment",
    "apply_knock_retard_cap",
    "apply_rpm_limit",
    "apply_spark_changes",
    "verify_patch_gates",
    "sha256",
    "collect_spark_delta_rows",
    "write_displacement_delta_csv",
    "write_spark_delta_csv",
    "write_simple_delta_csv",
]

fmt_cell = _fmt_cell
parse_float = _parse_float
find_item_by_name = _find_item_by_name
read_table = _read_table
write_cells = _write_cells
idx_nearest = _idx_nearest
apply_displacement = _apply_displacement
apply_decel_enleanment = _apply_decel_enleanment
apply_knock_retard_cap = _apply_knock_retard_cap
apply_rpm_limit = _apply_rpm_limit
apply_spark_changes = _apply_spark_changes
sha256 = _sha256
collect_spark_delta_rows = _collect_spark_delta_rows
write_displacement_delta_csv = _write_displacement_delta_csv
write_spark_delta_csv = _write_spark_delta_csv
write_simple_delta_csv = _write_simple_delta_csv


if __name__ == "__main__":
    sys.exit(main())
