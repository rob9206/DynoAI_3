"""
DynoAI iter_9 patch generator -- decel rich-fix on top of iter_8.

Background:
    iter_8 cruise-data analysis (pulls _41..44, 3145 steady-state samples) shows
    real cruise (MAP 50-70 kPa) is essentially on target, but decel/closed-throttle
    cells (MAP 30-40 kPa) are 1.5-2.5 AFR rich (LC2 ~12.1-12.9 vs target ~14.5-14.7).
    Effective correction needed: ~0.85.

    Cause: iter_2 zeroed the Deceleration Enleanment table (all 1.0) and left
    the low-TPS / low-MAP VE corner fat. With no decel fuel cut, the ECU dumps
    fuel any time the rider closes the throttle.

iter_9 strategy:
    1. Deceleration Enleanment: 0.92 at operating-temp columns (CHT 90-320 F).
       Cold columns (3, 32, 61 F) stay at 1.0 to avoid cold-stall on first ride.
    2. VE Front/Rear at low-TPS decel columns: trim down toward measured AFR,
       capped at -7%. Scope: RPM 1500-5000 x TPS 0/2/5/7/10. WOT VE untouched.

Combined effect: 0.92 * 0.93 = 0.856 effective AFR correction, right in line
with the ~0.85 that the cruise data shows is needed.

Tables changed (3):
    - Deceleration Enleanment
    - VE (TPS based/Front Cyl)
    - VE (TPS based/Rear Cyl)

Tables byte-identical to iter_8:
    - Spark Advance Front/Rear (iter_8 +2 deg WOT preserved)
    - Engine Displacement, Acceleration Enrichment, AFR / PE AFR
    - Max Knock Retard, RPM Limit
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import generate_iter2_patch as g2

logger = logging.getLogger(__name__)

SESSION_DIR = g2.SESSION_DIR
DEFAULT_BASE = SESSION_DIR / "iterations" / "iter_8" / "patch" / "iter_8_patched.pvv"
DEFAULT_ITER9 = SESSION_DIR / "iterations" / "iter_9"

DECEL_HOT_VALUE = 0.92
DECEL_COLD_VALUE = 1.0
DECEL_COLD_TEMPS = {3, 32, 61}

VE_DECEL_TPS_COLS = {0.0, 2.0, 5.0, 7.0, 10.0}
VE_DECEL_RPM_LO = 1.5
VE_DECEL_RPM_HI = 5.0
VE_DECEL_TRIM_PCT = -0.07

EXPECTED_CHANGED_ITER9 = sorted(
    [g2.DECEL_ENLEANMENT_TABLE, g2.VE_FRONT_TABLE, g2.VE_REAR_TABLE]
)

UNTOUCHABLE_ITER9 = sorted(
    [
        g2.DISPLACEMENT_TABLE,
        g2.SPARK_FRONT_TABLE,
        g2.SPARK_REAR_TABLE,
        g2.KNOCK_RETARD_TABLE,
        g2.RPM_LIMIT_TABLE,
        g2.AFR_TARGET_TABLE,
        g2.AFR_STOICH_TABLE,
        g2.ACCEL_ENRICH_TABLE,
    ]
)


def _apply_decel_enleanment(item: ET.Element) -> tuple[list[float], list[float], list[float]]:
    rows = item.find("Rows")
    cols = item.find("Columns")
    if rows is None or cols is None:
        raise RuntimeError(f"{g2.DECEL_ENLEANMENT_TABLE} missing Rows/Columns")

    col_labels = [g2.parse_float(c.get("label", "0") or "0") for c in cols.findall("Col")]
    row_elems = rows.findall("Row")
    if len(row_elems) != 1:
        raise RuntimeError(
            f"{g2.DECEL_ENLEANMENT_TABLE} expected 1 row, found {len(row_elems)}"
        )
    cells = row_elems[0].findall("Cell")
    if len(cells) != len(col_labels):
        raise RuntimeError(
            f"{g2.DECEL_ENLEANMENT_TABLE} cells/labels mismatch: "
            f"{len(cells)} vs {len(col_labels)}"
        )

    base_values: list[float] = []
    new_values: list[float] = []
    for i, cell in enumerate(cells):
        base = g2.parse_float(cell.get("value", "0") or "0")
        base_values.append(base)
        temp = col_labels[i]
        new = DECEL_COLD_VALUE if int(temp) in DECEL_COLD_TEMPS else DECEL_HOT_VALUE
        if not (0.5 <= new <= 1.0):
            raise RuntimeError(
                f"decel sanity FAIL at temp={temp}: {new} outside [0.5, 1.0]"
            )
        cell.set("value", g2.fmt_cell(new))
        new_values.append(new)
    return col_labels, base_values, new_values


def _apply_ve_decel_trim(
    item: ET.Element,
    cyl_label: str,
) -> tuple[list[float], list[float], list[list[float]], list[list[float]], list[dict]]:
    row_axis, col_axis, base_values = g2.read_table(item)
    base_grid = [list(r) for r in base_values]
    new_grid = [list(r) for r in base_values]
    delta_rows: list[dict] = []

    for r, rpm_k in enumerate(row_axis):
        if not (VE_DECEL_RPM_LO <= rpm_k <= VE_DECEL_RPM_HI):
            continue
        for c, tps in enumerate(col_axis):
            if tps not in VE_DECEL_TPS_COLS:
                continue
            base = base_grid[r][c]
            new = base * (1.0 + VE_DECEL_TRIM_PCT)
            if abs(new - base) < 1e-9:
                continue
            new_grid[r][c] = new
            delta_rows.append(
                {
                    "cylinder": cyl_label,
                    "row_idx": r,
                    "col_idx": c,
                    "rpm": int(rpm_k * 1000),
                    "tps_pct": tps,
                    "ve_base": base,
                    "ve_new": new,
                    "delta": new - base,
                }
            )

    g2.write_cells(item, new_grid)
    return row_axis, col_axis, base_grid, new_grid, delta_rows


def _write_decel_delta_csv(
    path: Path,
    col_axis: list[float],
    base_values: list[float],
    new_values: list[float],
) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["temp_F", "decel_base", "decel_new", "delta", "delta_pct"])
        for label, b, n in zip(col_axis, base_values, new_values):
            d = n - b
            pct = (d / b * 100.0) if abs(b) > 1e-9 else 0.0
            w.writerow([f"{label:g}", f"{b:.3f}", f"{n:.3f}", f"{d:+.3f}", f"{pct:+.2f}"])


def _write_ve_delta_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            ["cylinder", "row_idx", "col_idx", "rpm", "tps_pct", "ve_base", "ve_new", "delta", "delta_pct"]
        )
        for row in rows:
            base = row["ve_base"]
            d = row["delta"]
            pct = (d / base * 100.0) if abs(base) > 1e-9 else 0.0
            w.writerow(
                [
                    row["cylinder"],
                    row["row_idx"],
                    row["col_idx"],
                    row["rpm"],
                    f"{row['tps_pct']:g}",
                    f"{base:.2f}",
                    f"{row['ve_new']:.2f}",
                    f"{d:+.3f}",
                    f"{pct:+.2f}",
                ]
            )


def _write_change_log(
    path: Path,
    base_sha: str,
    new_sha: str,
    decel_axis: list[float],
    decel_base: list[float],
    decel_new: list[float],
    ve_rows: list[dict],
) -> None:
    decel_lines = ["| temp F | base | new | delta |", "|---:|---:|---:|---:|"]
    for label, b, n in zip(decel_axis, decel_base, decel_new):
        decel_lines.append(f"| {int(label)} | {b:.2f} | {n:.2f} | {n - b:+.2f} |")

    ve_top = sorted(ve_rows, key=lambda x: -abs(x["delta"]))[:20]
    ve_front = sum(1 for r in ve_rows if r["cylinder"] == "front")
    ve_rear = sum(1 for r in ve_rows if r["cylinder"] == "rear")

    lines = [
        "# iter_9 Patch -- decel rich-fix on top of iter_8",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "Vehicle: Ryan Titus 2006 Fat Boy CVO (103 ci)",
        "Session: 2026-05-10_4thgear_baseline",
        "",
        "Cruise data from iter_8 pulls (`_41..44`, 3145 steady-state samples) showed:",
        "- Real cruise at MAP 50-70 kPa is on AFR target",
        "- Decel/closed-throttle cells at MAP 30-40 kPa run 1.5-2.5 AFR RICH",
        "  (LC2 ~12.1-12.9 vs target ~14.5-14.7)",
        "",
        "iter_9 fixes the decel rich condition with two coordinated changes:",
        "",
        f"- base file: `iter_8_patched.pvv`",
        f"- base SHA-256: `{base_sha}`",
        f"- iter_9_patched.pvv SHA-256: `{new_sha}`",
        "",
        "## Change 1: Deceleration Enleanment table",
        "",
        f"Set decel multiplier to {DECEL_HOT_VALUE} at operating-temp columns (CHT 90-320 F).",
        f"Cold columns (CHT 3, 32, 61 F) kept at {DECEL_COLD_VALUE} so cold engine does not stall.",
        "",
        *decel_lines,
        "",
        "## Change 2: VE (TPS based) low-TPS decel trim",
        "",
        f"Trim VE by {abs(VE_DECEL_TRIM_PCT) * 100:.0f}% at decel-zone cells:",
        f"- RPM rows: {int(VE_DECEL_RPM_LO * 1000)} - {int(VE_DECEL_RPM_HI * 1000)}",
        f"- TPS columns: {sorted(VE_DECEL_TPS_COLS)}",
        f"- Front cells changed: {ve_front}",
        f"- Rear cells changed: {ve_rear}",
        "",
        "Combined effect: 0.92 * 0.93 = 0.856 effective AFR multiplier on decel cells,",
        "matching the ~0.85 the data shows is needed.",
        "",
        "Top 20 VE changes by absolute delta:",
        "",
        "| cylinder | RPM | TPS | base | new | delta | delta_pct |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in ve_top:
        base = row["ve_base"]
        d = row["delta"]
        pct = (d / base * 100.0) if abs(base) > 1e-9 else 0.0
        lines.append(
            f"| {row['cylinder']} | {row['rpm']} | {row['tps_pct']:g} | "
            f"{base:.2f} | {row['ve_new']:.2f} | {d:+.2f} | {pct:+.2f}% |"
        )

    lines.extend(
        [
            "",
            "## Tables byte-identical to iter_8",
            "",
            "- Spark Advance Front/Rear (iter_8 +2 deg WOT preserved)",
            "- Engine Displacement (103.0 CID)",
            "- Acceleration Enrichment (iter_6 AE fix preserved)",
            "- AFR / PE AFR",
            "- Max Knock Retard (4 deg cap), RPM Limit",
            "",
            "## Expected outcome",
            "",
            "- Cruise at MAP 50-70 kPa: unchanged from iter_8 (already on target)",
            "- Decel / coast (MAP 30-40 kPa): LC2 should rise from ~12.5 toward ~13.5-14.0",
            "- Less decel pop on closed-throttle deceleration",
            "- WOT power: identical to iter_8 (94.2 hp avg)",
            "- Tip-in transient: unchanged (AE table preserved)",
            "",
            "## Pull plan",
            "",
            "- Coast down test: roll on, then snap closed throttle from 4000-5000 RPM",
            "  in 4th gear; LC2 should not drop below 13.0",
            "- Slow cruise at 2500-3500 RPM, light throttle: LC2 13.0-13.7",
            "- Full WOT pull: should match iter_8 (94+ hp, no knock)",
            "",
            "## Abort criteria",
            "",
            "- Engine stalls or stumbles when chopping throttle: revert iter_8 (cold cells too lean?)",
            "- Lurch on tip-out: revert iter_8 (decel too aggressive)",
            "- WOT power drops vs iter_8: should not happen (WOT VE/spark untouched), but revert if so",
            "",
            f"Revert file: `iter_8_patched.pvv` (SHA-256 `{base_sha}`).",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_guardrails(path: Path) -> None:
    lines = [
        "# iter_9 Operational Guardrails",
        "",
        "Decel-only cleanup on top of iter_8. WOT untouched.",
        "",
        "## Critical limits",
        "",
        "- Stall on tip-out: revert immediately to iter_8",
        "- Lurch on tip-out: revert to iter_8",
        "- WOT HP drop vs iter_8: revert (should never happen)",
        "",
        "## Pull plan",
        "",
        "- 1st: 4th-gear cruise at light throttle 2500-3500 RPM, log",
        "- 2nd: snap-closed throttle from 4000+ RPM (decel test)",
        "- 3rd: confirmation WOT pull (verify WOT HP matches iter_8)",
        "",
        "## Expected behaviour",
        "",
        "- Cruise AFR unchanged",
        "- Decel AFR: LC2 should rise from ~12.5 toward ~13.5-14.0 on overrun",
        "- Less decel pop",
        "- WOT identical to iter_8",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_iteration_json(path: Path, patch_filename: str) -> None:
    payload = {
        "id": "iter_9",
        "session_id": "2026-05-10_4thgear_baseline",
        "index": 9,
        "patch_filename": patch_filename,
        "patch_base": "iter_8_patched.pvv",
        "supersedes": None,
        "evidence_dir": "iterations/iter_8/pulls",
        "status": "ready_to_flash",
        "flashed_at": None,
        "notes": (
            "iter_9 = iter_8 base + decel rich-fix. Decel Enleanment 0.92 at "
            "operating-temp CHT (90-320 F), 1.0 cold (3-61 F). VE Front/Rear "
            "trimmed -7% at low-TPS decel cells (TPS 0/2/5/7/10, RPM 1500-5000). "
            "WOT VE/spark untouched. Targets cruise data finding that decel/MAP30-40 "
            "ran 1.5-2.5 AFR rich while real cruise (MAP 50-70) was on target."
        ),
        "created_at": datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", type=Path, default=DEFAULT_BASE)
    ap.add_argument("--iter9-dir", type=Path, default=DEFAULT_ITER9)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    if args.verbose:
        logging.basicConfig(level=logging.INFO, format="%(message)s")

    if not args.base.exists():
        print(f"ERROR: base not found {args.base}", file=sys.stderr)
        return 2

    base_sha = g2.sha256(args.base)
    tree = ET.parse(str(args.base))
    root = tree.getroot()

    decel_item = g2.find_item_by_name(root, g2.DECEL_ENLEANMENT_TABLE)
    vf_item = g2.find_item_by_name(root, g2.VE_FRONT_TABLE)
    vr_item = g2.find_item_by_name(root, g2.VE_REAR_TABLE)
    if None in (decel_item, vf_item, vr_item):
        print("ERROR: required items missing in base", file=sys.stderr)
        return 5

    decel_axis, decel_base, decel_new = _apply_decel_enleanment(decel_item)
    _, _, vf_base, vf_new, vf_rows = _apply_ve_decel_trim(vf_item, "front")
    _, _, vr_base, vr_new, vr_rows = _apply_ve_decel_trim(vr_item, "rear")

    sf_item = g2.find_item_by_name(root, g2.SPARK_FRONT_TABLE)
    sr_item = g2.find_item_by_name(root, g2.SPARK_REAR_TABLE)
    _, _, sf_grid = g2.read_table(sf_item)
    _, _, sr_grid = g2.read_table(sr_item)

    args.iter9_dir.mkdir(parents=True, exist_ok=True)
    patch_dir = args.iter9_dir / "patch"
    pulls_dir = args.iter9_dir / "pulls"
    patch_dir.mkdir(parents=True, exist_ok=True)
    pulls_dir.mkdir(parents=True, exist_ok=True)
    patched = patch_dir / "iter_9_patched.pvv"

    tree.write(str(patched), encoding="utf-8", xml_declaration=True)

    try:
        g2.verify_patch_gates(
            patched,
            args.base,
            EXPECTED_CHANGED_ITER9,
            UNTOUCHABLE_ITER9,
            (sf_grid, sf_grid),
            (sr_grid, sr_grid),
            ve_stage_front=vf_base,
            ve_patched_front=vf_new,
            ve_stage_rear=vr_base,
            ve_patched_rear=vr_new,
            ve_max_frac_change=abs(VE_DECEL_TRIM_PCT) + 1e-6,
        )
    except RuntimeError as exc:
        patched.unlink(missing_ok=True)
        print(f"ABORT: {exc}", file=sys.stderr)
        return 6

    _write_decel_delta_csv(patch_dir / "decel_enleanment_delta.csv", decel_axis, decel_base, decel_new)
    _write_ve_delta_csv(patch_dir / "ve_decel_trim_delta.csv", [*vf_rows, *vr_rows])

    new_sha = g2.sha256(patched)
    _write_change_log(
        patch_dir / "change_log.md",
        base_sha,
        new_sha,
        decel_axis,
        decel_base,
        decel_new,
        [*vf_rows, *vr_rows],
    )
    _write_guardrails(patch_dir / "guardrails.md")
    _write_iteration_json(args.iter9_dir / "iteration.json", patched.name)

    manifest = pulls_dir / "manifest.json"
    if not manifest.exists():
        manifest.write_text(
            json.dumps(
                {
                    "iteration_id": "iter_9",
                    "tune_state": patched.name,
                    "tune_sha256": new_sha,
                    "flashed_at": None,
                    "afr_source": "dyno_tailpipe_wideband_only",
                    "wideband_channel": "LC2 (Innovate venturi in collector)",
                    "lc1_status": "not_hooked_up_ignore",
                    "test_mode": "loaded_4th_gear_wot_plus_cruise",
                    "pulls": [],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    decel_changed = sum(1 for b, n in zip(decel_base, decel_new) if abs(n - b) > 1e-9)
    print("OK")
    print(f"  base           SHA-256: {base_sha}")
    print(f"  iter_9_patched SHA-256: {new_sha}")
    print(f"  decel cells changed: {decel_changed} / {len(decel_axis)}")
    print(f"  VE cells changed:    {len(vf_rows) + len(vr_rows)}")
    print(f"  artifacts: {patch_dir}")
    print(f"  flash this file: {patched}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
