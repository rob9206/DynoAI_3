"""
Build iter_2 DWRT wideband findings for iter_3 VE correction.

Reads DynoWare RT .txt logs under iter_2/pulls/, bins LC2 AFR error into VE
table cells (same TPS x RPM axes as dynojet_stage.pvv), writes
iter_2/analyses/iter2_dwrt_findings.json.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

import pandas as pd

TOOLS_ITER3 = Path(__file__).resolve().parent
if str(TOOLS_ITER3) not in sys.path:
    sys.path.insert(0, str(TOOLS_ITER3))

from parse_dwrt_log import parse_dwrt_log  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SESSION_DIR = PROJECT_ROOT / "vehicles" / "ryantitus_fatboy_cvo" / "sessions" / "2026-05-10_4thgear_baseline"
DEFAULT_BASE_PVV = SESSION_DIR / "base_tune" / "dynojet_stage.pvv"
DEFAULT_PULLS_DIR = SESSION_DIR / "iterations" / "iter_2" / "pulls"
DEFAULT_OUT = SESSION_DIR / "iterations" / "iter_2" / "analyses" / "iter2_dwrt_findings.json"

PE_TABLE = "PE Air-Fuel Ratio"
AFR_TABLE = "Air-Fuel Ratio"
VE_FRONT_TABLE = "VE (TPS based/Front Cyl)"

MIN_RPM_FOR_ANALYSIS = 1.5
MIN_TPS_PCT = 5.0
MAX_RPM_DOT = 800.0
WOT_MAP_KPA = 85.0
WOT_TPS_PCT = 80.0
MIN_SAMPLES_PER_CELL = 5
MAX_VE_DELTA_PCT = 10.0


def _parse_float(text: str) -> float:
    try:
        return float(text)
    except (TypeError, ValueError):
        return 0.0


def _find_item(root: ET.Element, name: str) -> ET.Element:
    for item in root.findall("Item"):
        if item.get("name") == name:
            return item
    raise KeyError(name)


def _read_table(item: ET.Element) -> tuple[list[float], list[float], list[list[float]]]:
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


def _idx_nearest(axis: list[float], target: float) -> int:
    return min(range(len(axis)), key=lambda i: abs(axis[i] - target))


def _load_tune_targets(pvv: Path) -> tuple[
    list[float],
    list[float],
    list[list[float]],
    list[float],
    list[float],
    list[list[float]],
    list[float],
    list[float],
]:
    root = ET.parse(str(pvv)).getroot()
    pe_item = _find_item(root, PE_TABLE)
    afr_item = _find_item(root, AFR_TABLE)
    ve_item = _find_item(root, VE_FRONT_TABLE)
    pe_rows, pe_cols, pe_vals = _read_table(pe_item)
    afr_rows, afr_cols, afr_vals = _read_table(afr_item)
    ve_rows, ve_cols, _ve_vals = _read_table(ve_item)
    return pe_rows, pe_cols, pe_vals, afr_rows, afr_cols, afr_vals, ve_rows, ve_cols


def _lookup_target_afr(
    map_kpa: float,
    tps_pct: float,
    rpm_k: float,
    pe_cols: list[float],
    pe_vals: list[list[float]],
    afr_row_axis: list[float],
    afr_col_axis: list[float],
    afr_vals: list[list[float]],
) -> float:
    if map_kpa >= WOT_MAP_KPA or tps_pct >= WOT_TPS_PCT:
        ci = _idx_nearest(pe_cols, rpm_k)
        return pe_vals[0][ci]
    ri = _idx_nearest(afr_row_axis, rpm_k)
    ci = _idx_nearest(afr_col_axis, tps_pct)
    return afr_vals[ri][ci]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-pvv", type=Path, default=DEFAULT_BASE_PVV)
    ap.add_argument("--pulls-dir", type=Path, default=DEFAULT_PULLS_DIR)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    txt_files = sorted(args.pulls_dir.glob("*.txt"))
    if not txt_files:
        print(f"ERROR: no .txt in {args.pulls_dir}", file=sys.stderr)
        return 2

    pe_rows, pe_cols, pe_vals, afr_rows, afr_cols, afr_vals, ve_rows, ve_cols = (
        _load_tune_targets(args.base_pvv)
    )

    frames: list[pd.DataFrame] = []
    sources: list[dict] = []
    total_pegged = 0
    total_valid = 0

    for p in txt_files:
        df, rep = parse_dwrt_log(p)
        df["source_file"] = p.name
        frames.append(df)
        h = __import__("hashlib").sha256(p.read_bytes()).hexdigest()
        sources.append(
            {
                "name": p.name,
                "sha256": h,
                "samples": rep.row_count,
                "lc2_first_peg_t_s": rep.lc2_first_peg_t_s,
                "peak_hp": rep.peak_hp,
            }
        )
        total_pegged += rep.lc2_pegged_count

    all_df = pd.concat(frames, ignore_index=True)

    errs: dict[tuple[int, int], list[float]] = defaultdict(list)

    for _, row in all_df.iterrows():
        if row.get("lc2_pegged", False):
            continue
        rpm_k = float(row["rpm_k"])
        if rpm_k < MIN_RPM_FOR_ANALYSIS or pd.isna(rpm_k):
            continue
        tps = float(row["tps_pct"])
        if tps < MIN_TPS_PCT or pd.isna(tps):
            continue
        map_k = float(row["map_kpa"])
        if pd.isna(map_k):
            continue
        lc2 = float(row["lc2_afr"])
        if pd.isna(lc2) or lc2 <= 5.0 or lc2 >= 30.0:
            continue
        rd = float(row["rpm_dot_rpm_per_s"])
        if pd.isna(rd) or abs(rd) > MAX_RPM_DOT:
            continue

        tgt = _lookup_target_afr(map_k, tps, rpm_k, pe_cols, pe_vals, afr_rows, afr_cols, afr_vals)
        if tgt <= 0.5:
            continue
        err_pct = (lc2 - tgt) / tgt * 100.0

        ri = _idx_nearest(ve_rows, rpm_k)
        ci = _idx_nearest(ve_cols, tps)
        errs[(ri, ci)].append(err_pct)
        total_valid += 1

    grid: list[dict] = []
    for (ri, ci), vals in sorted(errs.items()):
        if len(vals) < MIN_SAMPLES_PER_CELL:
            continue
        med = float(statistics.median(vals))
        ve_delta = max(-MAX_VE_DELTA_PCT, min(MAX_VE_DELTA_PCT, med))
        grid.append(
            {
                "row_idx": ri,
                "col_idx": ci,
                "rpm_k": ve_rows[ri],
                "tps_pct": ve_cols[ci],
                "n": len(vals),
                "median_err_pct": round(med, 3),
                "ve_delta_pct": round(ve_delta, 3),
            }
        )

    warnings: list[str] = []
    warnings.append(
        f"LC2 pegged (>=22.38) in {total_pegged} samples across all files; "
        "those rows are excluded from VE binning (annotate-only policy)."
    )
    if not grid:
        warnings.append(
            "No VE cells met min sample count; widen filters or add pulls "
            f"(min_samples={MIN_SAMPLES_PER_CELL})."
        )

    try:
        base_rel = str(args.base_pvv.relative_to(PROJECT_ROOT))
    except ValueError:
        base_rel = str(args.base_pvv)
    payload = {
        "base_pvv": base_rel,
        "afr_target_table_in_use": f"{PE_TABLE} (WOT MAP>={WOT_MAP_KPA} or TPS>={WOT_TPS_PCT}) "
        f"else {AFR_TABLE}",
        "sources": sources,
        "total_valid_rows_used": total_valid,
        "ve_correction_grid": grid,
        "warnings": warnings,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {args.out} ({len(grid)} VE cells)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
