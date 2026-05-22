from __future__ import annotations

import argparse
import csv
import json
import statistics
import xml.etree.ElementTree as ET
from pathlib import Path


VE_TABLE_IDS = ("tbl_ve_tps_based_front_cyl", "tbl_ve_tps_based_rear_cyl")

DEFAULT_BASE = Path(r"C:\CommmandCenter\Customer_Files\seanbike\newnenww_baked.pvv")
DEFAULT_RUN = Path(r"C:\CommmandCenter\Customer_Files\seanbike\runnning_9.txt")
DEFAULT_OUT = Path(
    r"C:\CommmandCenter\Customer_Files\seanbike\newnenww_emergency_rich_v1.pvv"
)
DEFAULT_REPORT = Path(
    r"C:\CommmandCenter\Customer_Files\seanbike\newnenww_emergency_rich_v1_report.json"
)


def _find_item(root: ET.Element, item_id: str) -> ET.Element:
    for item in root.findall("Item"):
        if item.get("id") == item_id:
            return item
    raise RuntimeError(f"Missing VE table id={item_id}")


def _read_run_medians(run_path: Path) -> dict[str, float]:
    """
    Compute AFR medians by TPS bands from latest run.
    Uses LC2 collector channel as AFR source.
    """
    bands = {
        "20_40": [],
        "40_60": [],
        "60_80": [],
        "80_100": [],
    }

    with run_path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.reader(fh)
        header = [h.strip() for h in next(reader)]
        idx = {name: i for i, name in enumerate(header)}

        rpm_col = "(PV) Engine Speed"
        tps_col = "(PV) Throttle Position"
        afr_col = "(DWRT CPU) LC2 Volts Petrol AFR2"
        for c in (rpm_col, tps_col, afr_col):
            if c not in idx:
                raise RuntimeError(f"Run file missing required column: {c}")

        for row in reader:
            if len(row) < len(header):
                row = row + [""] * (len(header) - len(row))
            try:
                rpm = float(row[idx[rpm_col]].strip() or "nan")
                tps = float(row[idx[tps_col]].strip() or "nan")
                afr = float(row[idx[afr_col]].strip() or "nan")
            except ValueError:
                continue
            if not (rpm == rpm and tps == tps and afr == afr):
                continue
            # Focus on meaningful load region.
            if rpm < 3.0 or tps < 20:
                continue
            if 20 <= tps < 40:
                bands["20_40"].append(afr)
            elif 40 <= tps < 60:
                bands["40_60"].append(afr)
            elif 60 <= tps < 80:
                bands["60_80"].append(afr)
            elif tps >= 80:
                bands["80_100"].append(afr)

    medians = {}
    for k, vals in bands.items():
        if not vals:
            raise RuntimeError(f"No AFR samples in band {k}; cannot build emergency patch")
        medians[k] = statistics.median(vals)
    return medians


def _build_band_corrections(medians: dict[str, float]) -> dict[str, float]:
    # Conservative rich targets for emergency baseline.
    targets = {
        "20_40": 13.2,
        "40_60": 13.0,
        "60_80": 12.8,
        "80_100": 12.8,
    }

    corrections = {}
    for band, measured in medians.items():
        base_pct = ((measured / targets[band]) - 1.0) * 100.0
        # Add a small safety margin; still cap to avoid absurd jumps.
        pct = max(10.0, min(55.0, base_pct + 3.0))
        corrections[band] = pct
    return corrections


def _band_for_tps(tps: float) -> str | None:
    if tps < 20:
        return None
    if tps < 40:
        return "20_40"
    if tps < 60:
        return "40_60"
    if tps < 80:
        return "60_80"
    return "80_100"


def _format_value(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _apply_patch_to_table(
    table_item: ET.Element, corrections: dict[str, float]
) -> dict[str, float | int]:
    rows = table_item.findall("./Rows/Row")
    changed = 0
    max_pct = 0.0
    avg_pct_accum = 0.0

    for row in rows:
        rpm_k = float(row.get("label", "0") or "0")
        rpm = rpm_k * 1000.0
        cells = row.findall("Cell")

        col_labels = []
        for col in table_item.findall("./Columns/Col"):
            col_labels.append(float(col.get("label", "0") or "0"))

        if len(col_labels) != len(cells):
            raise RuntimeError("VE table column/cell length mismatch")

        for i, cell in enumerate(cells):
            tps = col_labels[i]
            band = _band_for_tps(tps)
            if band is None:
                continue

            # Keep low-rpm stable; act strongly only where pull went lean.
            if rpm < 2500:
                continue

            pct = corrections[band]
            if rpm >= 4200 and tps >= 40:
                pct += 4.0
            if rpm >= 5200 and tps >= 80:
                pct += 2.0
            pct = min(55.0, pct)

            old_v = float(cell.get("value", "0") or "0")
            new_v = old_v * (1.0 + pct / 100.0)
            cell.set("value", _format_value(new_v))

            changed += 1
            avg_pct_accum += pct
            max_pct = max(max_pct, pct)

    avg_pct = (avg_pct_accum / changed) if changed else 0.0
    return {
        "changed_cells": changed,
        "avg_pct": round(avg_pct, 3),
        "max_pct": round(max_pct, 3),
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Generate emergency rich baseline patch from latest lean pull."
    )
    ap.add_argument("--base", type=Path, default=DEFAULT_BASE)
    ap.add_argument("--run", type=Path, default=DEFAULT_RUN)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = ap.parse_args()

    if not args.base.exists():
        raise SystemExit(f"Base tune not found: {args.base}")
    if not args.run.exists():
        raise SystemExit(f"Run file not found: {args.run}")

    medians = _read_run_medians(args.run)
    corrections = _build_band_corrections(medians)

    tree = ET.parse(args.base)
    root = tree.getroot()

    per_table = {}
    for table_id in VE_TABLE_IDS:
        item = _find_item(root, table_id)
        per_table[table_id] = _apply_patch_to_table(item, corrections)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    tree.write(args.out, encoding="utf-8", xml_declaration=True)

    report = {
        "base_tune": str(args.base),
        "run_file": str(args.run),
        "output_tune": str(args.out),
        "afr_medians_by_tps_band": medians,
        "corrections_pct_by_tps_band": corrections,
        "table_stats": per_table,
        "note": "Single collector AFR source; identical enrichment strategy applied to front and rear VE tables.",
    }
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("Emergency patch created.")
    print("Output:", args.out)
    print("Report:", args.report)
    print("AFR medians:", medians)
    print("Corrections %:", corrections)
    print("Table stats:", per_table)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
