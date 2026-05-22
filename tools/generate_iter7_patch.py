"""
DynoAI iter_7 patch generator -- targeted +1 deg WOT spark sweep on top of iter_6.

Background:
    iter_6 was flashed and validated on 2026-05-12 with brake-fixed pulls 31..33:
    94.5 / 95.1 / 95.2 hp, 0 deg knock retard at peak, LC2 12.0-12.8 in 3000-5500 RPM,
    rear injector duty 86-93%. Tune is healthy; bike has unused knock margin and is
    approaching injector saturation at the very top of the band.

    The remaining lever for HP without a hardware change is spark advance. The
    iter_3/iter_6 spark table at the WOT columns (MAP = 100 kPa) is byte-identical
    to the original Dynojet stage map. Cam advance from iter_2 only added +1 deg in
    the MAP 60-95 cruise zone, not at WOT.

iter_7 strategy:
    Add +1 deg ONLY at the WOT MAP columns (MAP = 100 kPa, columns 10..16) and
    ONLY at peak-power RPMs 4500, 5000, 5500. Both cylinders. 42 cells total.

    Cells excluded from the sweep:
      - Below RPM 4.5: peak power not happening here, cam advance already applied.
      - Above RPM 5.5: rear injector duty saturating; no more fuel available so
        more spark would just increase EGT for no HP gain. Also the 6.0 row at MAP
        95 already has the iter_2 knock notch that we MUST NOT overwrite.
      - MAP < 100 kPa: untouched. The iter_2 5500/95 knock notch is preserved.
      - Knock-retard cap (4 deg) and AE/VE/displacement/decel/RPM limit: unchanged.

Tables changed (2):
    - Spark Advance (Front Cyl)
    - Spark Advance (Rear Cyl)

Tables byte-identical to iter_6:
    - VE (TPS based/Front Cyl), VE (TPS based/Rear Cyl)
    - Engine Displacement (103.0 CID)
    - Acceleration Enrichment
    - AFR / PE AFR, Deceleration Enleanment, Max Knock Retard, RPM Limit

Usage:
    python tools/generate_iter7_patch.py
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

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SESSION_DIR = g2.SESSION_DIR
DEFAULT_BASE = SESSION_DIR / "iterations" / "iter_6" / "patch" / "iter_6_patched.pvv"
DEFAULT_ITER7 = SESSION_DIR / "iterations" / "iter_7"

SPARK_SWEEP_RPM_K = (4.5, 5.0, 5.5)
SPARK_SWEEP_MAP_KPA = 100.0
SPARK_SWEEP_DELTA = 1.0

DEG_HARD_CAP = 40.0
DEG_HARD_FLOOR = 20.0

EXPECTED_CHANGED_ITER7 = sorted([g2.SPARK_FRONT_TABLE, g2.SPARK_REAR_TABLE])

UNTOUCHABLE_ITER7 = sorted([
    g2.DISPLACEMENT_TABLE,
    g2.DECEL_ENLEANMENT_TABLE,
    g2.KNOCK_RETARD_TABLE,
    g2.RPM_LIMIT_TABLE,
    g2.AFR_TARGET_TABLE,
    g2.AFR_STOICH_TABLE,
    g2.VE_FRONT_TABLE,
    g2.VE_REAR_TABLE,
    g2.ACCEL_ENRICH_TABLE,
])


def _apply_wot_spark_sweep(
    item: ET.Element,
    cyl_label: str,
) -> tuple[
    list[float], list[float], list[list[float]], list[list[float]], list[list[str]]
]:
    """Apply +1 deg sweep at MAP=100 kPa cols for RPM 4.5/5.0/5.5.

    Returns (row_axis, col_axis, base_grid, new_grid, source_grid).
    """
    row_axis, col_axis, base_values = g2.read_table(item)
    base_grid = [list(r) for r in base_values]
    new_grid = [list(r) for r in base_values]
    source_grid: list[list[str]] = [["" for _ in row] for row in base_grid]

    rpm_idxs = [i for i, rpm_k in enumerate(row_axis) if rpm_k in SPARK_SWEEP_RPM_K]
    if len(rpm_idxs) != len(SPARK_SWEEP_RPM_K):
        raise RuntimeError(
            f"{cyl_label} spark: could not find all sweep RPM rows. "
            f"axis={row_axis} wanted={SPARK_SWEEP_RPM_K}"
        )
    map_cols = [
        i for i, kpa in enumerate(col_axis) if abs(kpa - SPARK_SWEEP_MAP_KPA) < 1e-9
    ]
    if not map_cols:
        raise RuntimeError(
            f"{cyl_label} spark: no MAP=100 columns found. col_axis={col_axis}"
        )

    for r in rpm_idxs:
        for c in map_cols:
            base_val = base_grid[r][c]
            new_val = base_val + SPARK_SWEEP_DELTA
            if not (DEG_HARD_FLOOR <= new_val <= DEG_HARD_CAP):
                raise RuntimeError(
                    f"{cyl_label} spark sanity FAIL: cell rpm={row_axis[r]} kpa={col_axis[c]} "
                    f"base={base_val} new={new_val} outside [{DEG_HARD_FLOOR},{DEG_HARD_CAP}]"
                )
            if abs(new_val - base_val) > g2.CLAMP_SPARK_DEG + 1e-3:
                raise RuntimeError(
                    f"{cyl_label} spark clamp FAIL: cell rpm={row_axis[r]} kpa={col_axis[c]} "
                    f"|{new_val}-{base_val}| > clamp {g2.CLAMP_SPARK_DEG}"
                )
            new_grid[r][c] = new_val
            source_grid[r][c] = "iter7_wot_sweep"

    g2.write_cells(item, new_grid)
    return row_axis, col_axis, base_grid, new_grid, source_grid


def _write_spark_delta_csv(
    path: Path,
    front_rows: list[tuple[str, float, float, str, float, float]],
    rear_rows: list[tuple[str, float, float, str, float, float]],
) -> None:
    g2.write_spark_delta_csv(path, [*front_rows, *rear_rows])


def _spark_change_table_md(
    cyl_label: str,
    row_axis: list[float],
    col_axis: list[float],
    base_grid: list[list[float]],
    new_grid: list[list[float]],
) -> list[str]:
    lines = [f"### {cyl_label}", ""]
    lines.append("| RPM | MAP | base | new | delta |")
    lines.append("|---|---|---|---|---|")
    for r, rpm_k in enumerate(row_axis):
        for c, kpa in enumerate(col_axis):
            d = new_grid[r][c] - base_grid[r][c]
            if abs(d) < 1e-9:
                continue
            lines.append(
                f"| {int(rpm_k * 1000)} | {kpa:g} | {base_grid[r][c]:.1f} | "
                f"{new_grid[r][c]:.1f} | {d:+.1f} |"
            )
    return lines


def _write_iter7_change_log(
    path: Path,
    base_sha: str,
    new_sha: str,
    f_axis: tuple[list[float], list[float], list[list[float]], list[list[float]]],
    r_axis: tuple[list[float], list[float], list[list[float]], list[list[float]]],
) -> None:
    f_lines = _spark_change_table_md("Front Cyl", *f_axis)
    r_lines = _spark_change_table_md("Rear Cyl", *r_axis)
    lines = [
        "# iter_7 Patch -- targeted +1 deg WOT spark sweep on top of iter_6",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "Vehicle: Ryan Titus 2006 Fat Boy CVO (103 ci)",
        "Session: 2026-05-10_4thgear_baseline",
        "",
        "iter_6 was flashed and validated on 2026-05-12. Brake-fixed pulls _31..33 made",
        "94.5 / 95.1 / 95.2 hp peak with **0 deg knock retard** in the entire pull and",
        "rear injector duty 86-93%. The bike has unused knock margin and is at the",
        "injector ceiling -- spark advance is the only remaining HP lever without a",
        "hardware change.",
        "",
        "iter_7 adds +1 deg ONLY at the WOT MAP columns (MAP = 100 kPa) at peak-power",
        "RPMs (4500, 5000, 5500). Both cylinders. The iter_2 knock notch at",
        "5500 / 95 kPa is left untouched (we are sweeping a column to the right of it).",
        "",
        f"- base file: `iter_6_patched.pvv`",
        f"- base SHA-256: `{base_sha}`",
        f"- iter_7_patched.pvv SHA-256: `{new_sha}`",
        "",
        "## Spark cells changed (Front + Rear)",
        "",
        *f_lines,
        "",
        *r_lines,
        "",
        "## Tables byte-identical to iter_6",
        "",
        "- VE (TPS based/Front Cyl), VE (TPS based/Rear Cyl)",
        "- Engine Displacement (103.0 CID)",
        "- Acceleration Enrichment (iter_6 AE fix preserved)",
        "- AFR / PE AFR, Deceleration Enleanment, Max Knock Retard (4 deg cap), RPM Limit",
        "",
        "## Expected outcome (4th-gear pulls)",
        "",
        "- Peak HP: 96-98 (+1-3 hp over iter_6's 94.9 hp average)",
        "- WOT LC2 in 3000-5500 RPM: ~12.3-12.8 (unchanged from iter_6; pure spark change)",
        "- Knock retard: 0-2 deg target; abort if knock > 4 deg or any cell hits the cap",
        "- Rear injector duty: ~86-93% (unchanged; this is hardware-limited)",
        "",
        "## Abort criteria post-flash",
        "",
        "- Knock retard > 4 deg sustained at any RPM -- back off, revert to iter_6",
        "- Peak HP drops vs iter_6 -- spark is past MBT, revert",
        "- Detonation audible -- revert immediately",
        "- CHT > 220 F at WOT",
        "",
        "## Pull plan",
        "",
        "- Pull 1: gentle WOT in 4th, watch knock retard live",
        "- Pull 2: full WOT in 4th, log to redline",
        "- Pull 3: confirm pull 2 (repeatability)",
        "",
        "## Revert",
        "",
        f"Re-flash `iter_6_patched.pvv` (SHA-256 `{base_sha}`).",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_iter7_guardrails(path: Path) -> None:
    lines = [
        "# iter_7 Operational Guardrails",
        "",
        "Spark-only revision on top of iter_6. Single dimension change: WOT timing.",
        "",
        "## Pull plan",
        "",
        "- [ ] Pull 1: gentle 4th-gear WOT to 5500 RPM, watch knock retard channel live",
        "- [ ] Pull 2: full 4th-gear WOT to ~6000 RPM, log",
        "- [ ] Pull 3: confirmation pull (must repeat pull 2 within 1 hp)",
        "",
        "## Win conditions",
        "",
        "- WOT peak HP: 96+ (target +1-3 hp vs iter_6's 94.9 hp avg)",
        "- WOT LC2 3000-5500: 12.3-12.8 (unchanged vs iter_6)",
        "- Knock retard: 0-2 deg observed; cap is 4 deg",
        "- CHT: <220 F",
        "",
        "## Abort criteria (revert to iter_6)",
        "",
        "- Knock retard > 4 deg at any RPM",
        "- Peak HP drops below iter_6 baseline",
        "- Audible detonation",
        "- CHT > 220 F",
        "",
        "## Known constraints",
        "",
        "- Rear injector duty 86-93% in iter_6 -- this iteration does not change fuel,",
        "  duty stays the same. Hardware ceiling unchanged.",
        "",
        "See `vehicles/ryantitus_fatboy_cvo/profile.json` tuning_guardrails.",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_iter7_iteration_json(path: Path, patch_filename: str) -> None:
    payload = {
        "id": "iter_7",
        "session_id": "2026-05-10_4thgear_baseline",
        "index": 7,
        "patch_filename": patch_filename,
        "patch_base": "iter_6_patched.pvv",
        "supersedes": None,
        "evidence_dir": "iterations/iter_6/pulls",
        "status": "ready_to_flash",
        "flashed_at": None,
        "notes": (
            "iter_7 = +1 deg WOT spark sweep at MAP=100 kPa, RPM 4.5/5.0/5.5, both "
            "cylinders. iter_6 brake-fixed pulls _31..33 showed 0 deg knock retard at "
            "94.5-95.2 hp peak, leaving headroom. Knock cap unchanged at 4 deg. "
            "Knock notch at 5500/95 kPa preserved. All tables byte-identical to iter_6 "
            "except Spark Advance (Front Cyl) and Spark Advance (Rear Cyl)."
        ),
        "created_at": datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", type=Path, default=DEFAULT_BASE)
    ap.add_argument("--iter7-dir", type=Path, default=DEFAULT_ITER7)
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

    sf_item = g2.find_item_by_name(root, g2.SPARK_FRONT_TABLE)
    sr_item = g2.find_item_by_name(root, g2.SPARK_REAR_TABLE)
    if sf_item is None or sr_item is None:
        print("ERROR: spark items missing in base", file=sys.stderr)
        return 5

    f_row, f_col, f_base, f_new, f_src = _apply_wot_spark_sweep(sf_item, "Front")
    r_row, r_col, r_base, r_new, r_src = _apply_wot_spark_sweep(sr_item, "Rear")

    args.iter7_dir.mkdir(parents=True, exist_ok=True)
    patch_dir = args.iter7_dir / "patch"
    pulls_dir = args.iter7_dir / "pulls"
    patch_dir.mkdir(parents=True, exist_ok=True)
    pulls_dir.mkdir(parents=True, exist_ok=True)
    patched = patch_dir / "iter_7_patched.pvv"

    tree.write(str(patched), encoding="utf-8", xml_declaration=True)

    vf_item = g2.find_item_by_name(root, g2.VE_FRONT_TABLE)
    vr_item = g2.find_item_by_name(root, g2.VE_REAR_TABLE)
    _, _, vf_grid = g2.read_table(vf_item)
    _, _, vr_grid = g2.read_table(vr_item)

    try:
        g2.verify_patch_gates(
            patched,
            args.base,
            EXPECTED_CHANGED_ITER7,
            UNTOUCHABLE_ITER7,
            (f_base, f_new),
            (r_base, r_new),
            ve_stage_front=vf_grid,
            ve_patched_front=vf_grid,
            ve_stage_rear=vr_grid,
            ve_patched_rear=vr_grid,
            ve_max_frac_change=0.0,
        )
    except RuntimeError as exc:
        patched.unlink(missing_ok=True)
        print(f"ABORT: {exc}", file=sys.stderr)
        return 6

    front_rows = g2.collect_spark_delta_rows("front", f_row, f_col, f_base, f_new, f_src)
    rear_rows = g2.collect_spark_delta_rows("rear", r_row, r_col, r_base, r_new, r_src)
    _write_spark_delta_csv(patch_dir / "spark_advance_delta.csv", front_rows, rear_rows)

    new_sha = g2.sha256(patched)
    cells_changed = len(front_rows) + len(rear_rows)

    _write_iter7_change_log(
        patch_dir / "change_log.md",
        base_sha,
        new_sha,
        (f_row, f_col, f_base, f_new),
        (r_row, r_col, r_base, r_new),
    )
    _write_iter7_guardrails(patch_dir / "guardrails.md")
    _write_iter7_iteration_json(args.iter7_dir / "iteration.json", patched.name)

    pulls_manifest = pulls_dir / "manifest.json"
    if not pulls_manifest.exists():
        pulls_manifest.write_text(
            json.dumps(
                {
                    "iteration_id": "iter_7",
                    "tune_state": "iter_7_patched.pvv",
                    "tune_sha256": new_sha,
                    "flashed_at": None,
                    "afr_source": "dyno_tailpipe_wideband_only",
                    "wideband_channel": "LC2 (Innovate venturi in collector)",
                    "lc1_status": "not_hooked_up_ignore",
                    "test_mode": "loaded_4th_gear_wot",
                    "pulls": [],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    print("OK")
    print(f"  base           SHA-256: {base_sha}")
    print(f"  iter_7_patched SHA-256: {new_sha}")
    print(f"  spark cells changed:           {cells_changed}")
    print(f"  artifacts: {patch_dir}")
    print(f"  flash this file: {patched}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
