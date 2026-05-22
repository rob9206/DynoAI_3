"""
DynoAI iter_8 patch generator -- VE smoothing plus +2 deg WOT spark experiment.

Base:
    iter_6_patched.pvv, the validated tune that made 94.5 / 95.1 / 95.2 hp
    with zero knock after the rear brake drag issue was fixed.

Strategy:
    1. Smooth cruise + part-throttle VE only:
       - RPM 1500-5000
       - TPS 0-60
       - 3x3 neighbour mean, 1.5% deadband, half-step toward neighbours
       - per-cell VE change capped at +/-3%
       - TPS 80/100 WOT columns untouched
       - idle and rev-limit rows untouched

    2. Add +2 deg WOT spark only where peak power was measured:
       - MAP 100 kPa columns
       - RPM 4500, 5000, 5500
       - Front and rear cylinders
       - 5500/95 kPa knock notch preserved

This is an experimental customer-dyno tune, not a final safety claim. If it
does not beat iter_6 cleanly or shows knock, revert to iter_6.
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
DEFAULT_BASE = SESSION_DIR / "iterations" / "iter_6" / "patch" / "iter_6_patched.pvv"
DEFAULT_ITER8 = SESSION_DIR / "iterations" / "iter_8"

SPARK_SWEEP_RPM_K = (4.5, 5.0, 5.5)
SPARK_SWEEP_MAP_KPA = 100.0
SPARK_SWEEP_DELTA = 2.0

VE_RPM_LO = 1.5
VE_RPM_HI = 5.0
VE_TPS_LO = 0.0
VE_TPS_HI = 60.0
VE_DEADBAND_PCT = 0.015
VE_ALPHA = 0.5
VE_MAX_CHANGE_PCT = 0.03

DEG_HARD_CAP = 40.0
DEG_HARD_FLOOR = 20.0

EXPECTED_CHANGED_ITER8 = sorted(
    [g2.SPARK_FRONT_TABLE, g2.SPARK_REAR_TABLE, g2.VE_FRONT_TABLE, g2.VE_REAR_TABLE]
)

UNTOUCHABLE_ITER8 = sorted(
    [
        g2.DISPLACEMENT_TABLE,
        g2.DECEL_ENLEANMENT_TABLE,
        g2.KNOCK_RETARD_TABLE,
        g2.RPM_LIMIT_TABLE,
        g2.AFR_TARGET_TABLE,
        g2.AFR_STOICH_TABLE,
        g2.ACCEL_ENRICH_TABLE,
    ]
)


def _ve_in_scope(rpm_k: float, tps: float) -> bool:
    return VE_RPM_LO <= rpm_k <= VE_RPM_HI and VE_TPS_LO <= tps <= VE_TPS_HI


def _neighbour_mean_3x3(grid: list[list[float]], r: int, c: int) -> float:
    row_count = len(grid)
    col_count = len(grid[0])
    total = 0.0
    count = 0
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            rr = r + dr
            cc = c + dc
            if 0 <= rr < row_count and 0 <= cc < col_count:
                total += grid[rr][cc]
                count += 1
    return total / count if count else grid[r][c]


def _apply_ve_smoothing(
    item: ET.Element,
    cyl_label: str,
) -> tuple[list[float], list[float], list[list[float]], list[list[float]], list[dict]]:
    row_axis, col_axis, base_values = g2.read_table(item)
    base_grid = [list(row) for row in base_values]
    new_grid = [list(row) for row in base_values]
    delta_rows: list[dict] = []

    for r, rpm_k in enumerate(row_axis):
        for c, tps in enumerate(col_axis):
            if not _ve_in_scope(rpm_k, tps):
                continue

            base = base_grid[r][c]
            mean = _neighbour_mean_3x3(base_grid, r, c)
            if abs(mean) < 1e-9:
                continue

            residual = base - mean
            if abs(residual) < VE_DEADBAND_PCT * abs(mean):
                continue

            proposed = base - VE_ALPHA * residual
            cap = VE_MAX_CHANGE_PCT * abs(base)
            change = max(-cap, min(cap, proposed - base))
            new_value = base + change

            new_grid[r][c] = new_value
            delta_rows.append(
                {
                    "cylinder": cyl_label,
                    "row_idx": r,
                    "col_idx": c,
                    "rpm": int(rpm_k * 1000),
                    "tps_pct": tps,
                    "ve_base": base,
                    "ve_new": new_value,
                    "delta": new_value - base,
                }
            )

    g2.write_cells(item, new_grid)
    return row_axis, col_axis, base_grid, new_grid, delta_rows


def _apply_wot_spark_sweep(
    item: ET.Element,
    cyl_label: str,
) -> tuple[list[float], list[float], list[list[float]], list[list[float]], list[list[str]]]:
    row_axis, col_axis, base_values = g2.read_table(item)
    base_grid = [list(row) for row in base_values]
    new_grid = [list(row) for row in base_values]
    source_grid = [["" for _ in row] for row in base_grid]

    rpm_idxs = [i for i, rpm_k in enumerate(row_axis) if rpm_k in SPARK_SWEEP_RPM_K]
    if len(rpm_idxs) != len(SPARK_SWEEP_RPM_K):
        raise RuntimeError(
            f"{cyl_label} spark: missing one or more target RPM rows: {SPARK_SWEEP_RPM_K}"
        )

    map_cols = [
        i for i, map_kpa in enumerate(col_axis) if abs(map_kpa - SPARK_SWEEP_MAP_KPA) < 1e-9
    ]
    if not map_cols:
        raise RuntimeError(f"{cyl_label} spark: no MAP=100 kPa columns found")

    for r in rpm_idxs:
        for c in map_cols:
            base = base_grid[r][c]
            new_value = base + SPARK_SWEEP_DELTA
            if not (DEG_HARD_FLOOR <= new_value <= DEG_HARD_CAP):
                raise RuntimeError(
                    f"{cyl_label} spark sanity failed at rpm={row_axis[r]} map={col_axis[c]}: "
                    f"{base} -> {new_value}"
                )
            if abs(new_value - base) > g2.CLAMP_SPARK_DEG + 1e-3:
                raise RuntimeError(
                    f"{cyl_label} spark clamp failed at rpm={row_axis[r]} map={col_axis[c]}: "
                    f"{base} -> {new_value}"
                )
            new_grid[r][c] = new_value
            source_grid[r][c] = "iter8_wot_sweep_plus2"

    g2.write_cells(item, new_grid)
    return row_axis, col_axis, base_grid, new_grid, source_grid


def _write_ve_delta_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "cylinder",
                "row_idx",
                "col_idx",
                "rpm",
                "tps_pct",
                "ve_base",
                "ve_new",
                "delta",
                "delta_pct",
            ]
        )
        for row in rows:
            base = row["ve_base"]
            delta = row["delta"]
            pct = (delta / base * 100.0) if abs(base) > 1e-9 else 0.0
            writer.writerow(
                [
                    row["cylinder"],
                    row["row_idx"],
                    row["col_idx"],
                    row["rpm"],
                    f"{row['tps_pct']:g}",
                    f"{base:.2f}",
                    f"{row['ve_new']:.2f}",
                    f"{delta:+.3f}",
                    f"{pct:+.2f}",
                ]
            )


def _write_spark_delta_csv(
    path: Path,
    front_rows: list[tuple[str, float, float, str, float, float]],
    rear_rows: list[tuple[str, float, float, str, float, float]],
) -> None:
    g2.write_spark_delta_csv(path, [*front_rows, *rear_rows])


def _write_change_log(
    path: Path,
    base_sha: str,
    new_sha: str,
    ve_rows: list[dict],
    spark_rows: list[tuple[str, float, float, str, float, float]],
) -> None:
    top_ve = sorted(ve_rows, key=lambda row: -abs(row["delta"]))[:20]
    ve_front_count = sum(1 for row in ve_rows if row["cylinder"] == "front")
    ve_rear_count = sum(1 for row in ve_rows if row["cylinder"] == "rear")

    lines = [
        "# iter_8 Patch -- VE smoothing + aggressive WOT spark experiment",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "Vehicle: Ryan Titus 2006 Fat Boy CVO (103 ci)",
        "Session: 2026-05-10_4thgear_baseline",
        "",
        "Base: `iter_6_patched.pvv`, not iter_7. iter_7 (+1 deg WOT spark) was safe",
        "but did not beat iter_6. User requested the smoothed VE tune with +2 deg",
        "where it matters. This file is experimental and must be validated before final use.",
        "",
        f"- base SHA-256: `{base_sha}`",
        f"- iter_8_patched.pvv SHA-256: `{new_sha}`",
        "",
        "## Spark change",
        "",
        "- +2.0 deg at MAP=100 kPa columns only",
        "- RPM rows: 4500, 5000, 5500",
        "- Front and rear cylinders",
        "- 5500/95 kPa knock notch preserved",
        "- Spark clamp: +2.0 deg, inside the +/-3.0 deg safety clamp",
        "",
        "| cylinder | RPM | MAP | base | new | delta |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for cylinder, rpm_k, map_kpa, _, base, new in spark_rows:
        lines.append(
            f"| {cylinder} | {int(rpm_k * 1000)} | {map_kpa:g} | "
            f"{base:.1f} | {new:.1f} | {new - base:+.1f} |"
        )

    lines.extend(
        [
            "",
            "## VE smoothing change",
            "",
            f"- Front VE cells changed: {ve_front_count}",
            f"- Rear VE cells changed: {ve_rear_count}",
            "- Scope: RPM 1500-5000, TPS 0-60 only",
            "- WOT VE columns (TPS 80/100) untouched",
            "- Per-cell VE delta capped at +/-3%",
            "",
            "Top VE changes by absolute delta:",
            "",
            "| cylinder | RPM | TPS | base | new | delta | delta_pct |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in top_ve:
        base = row["ve_base"]
        delta = row["delta"]
        pct = (delta / base * 100.0) if abs(base) > 1e-9 else 0.0
        lines.append(
            f"| {row['cylinder']} | {row['rpm']} | {row['tps_pct']:g} | "
            f"{base:.2f} | {row['ve_new']:.2f} | {delta:+.2f} | {pct:+.2f}% |"
        )

    lines.extend(
        [
            "",
            "## Tables byte-identical to iter_6",
            "",
            "- Engine Displacement (103.0 CID)",
            "- Acceleration Enrichment (iter_6 AE fix preserved)",
            "- AFR / PE AFR",
            "- Deceleration Enleanment",
            "- Max Knock Retard (4 deg cap)",
            "- RPM Limit",
            "",
            "## Pull plan",
            "",
            "- First pull: 4th gear, watch knock retard live, abort if >4 deg",
            "- If clean: two more 4th-gear WOT pulls",
            "- Judge against iter_6, not iter_7: iter_6 brake-fixed avg = 94.9 hp",
            "",
            "## Abort / revert",
            "",
            "- Knock retard >4 deg: revert to iter_6",
            "- Audible detonation: revert immediately",
            "- Peak HP below iter_6 again: timing is past MBT, revert to iter_6",
            "- CHT >220 F: abort",
            "",
            f"Revert file: `iter_6_patched.pvv` (SHA-256 `{base_sha}`).",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_guardrails(path: Path) -> None:
    lines = [
        "# iter_8 Operational Guardrails",
        "",
        "Experimental combined tune: cruise/part-throttle VE smoothing plus +2 deg WOT spark.",
        "",
        "## Critical limits",
        "",
        "- Abort if knock retard >4 deg",
        "- Abort on any audible detonation",
        "- Abort if CHT >220 F",
        "- Revert if peak HP does not beat iter_6 cleanly",
        "",
        "## Pull plan",
        "",
        "- Pull 1: 4th gear, watch knock live; stop at ~5500 if anything looks wrong",
        "- Pull 2: full 4th gear to ~6000",
        "- Pull 3: confirmation pull",
        "",
        "## Expected behaviour",
        "",
        "- WOT AFR should match iter_6 because WOT VE is untouched",
        "- Part-throttle cruise should feel smoother because TPS 0-60 VE spikes are reduced",
        "- Spark is the risk: +2 deg may still be past MBT despite zero knock",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_iteration_json(path: Path, patch_filename: str) -> None:
    payload = {
        "id": "iter_8",
        "session_id": "2026-05-10_4thgear_baseline",
        "index": 8,
        "patch_filename": patch_filename,
        "patch_base": "iter_6_patched.pvv",
        "supersedes": "iter_7",
        "evidence_dir": "iterations/iter_6/pulls",
        "status": "ready_to_flash_experimental",
        "flashed_at": None,
        "notes": (
            "iter_8 = iter_6 base + cruise/part-throttle VE smoothing "
            "(RPM 1500-5000, TPS 0-60, WOT VE untouched) + aggressive +2 deg WOT "
            "spark at MAP=100 kPa for RPM 4500/5000/5500. iter_7 +1 deg was safe "
            "but did not gain HP, so this is experimental and must be judged against "
            "iter_6. Revert to iter_6 on knock, heat, or no power gain."
        ),
        "created_at": datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--iter8-dir", type=Path, default=DEFAULT_ITER8)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

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
    vf_item = g2.find_item_by_name(root, g2.VE_FRONT_TABLE)
    vr_item = g2.find_item_by_name(root, g2.VE_REAR_TABLE)
    if None in (sf_item, sr_item, vf_item, vr_item):
        print("ERROR: required spark/VE items missing in base", file=sys.stderr)
        return 5

    f_row, f_col, f_spark_base, f_spark_new, f_src = _apply_wot_spark_sweep(
        sf_item, "front"
    )
    r_row, r_col, r_spark_base, r_spark_new, r_src = _apply_wot_spark_sweep(
        sr_item, "rear"
    )
    _, _, f_ve_base, f_ve_new, f_ve_rows = _apply_ve_smoothing(vf_item, "front")
    _, _, r_ve_base, r_ve_new, r_ve_rows = _apply_ve_smoothing(vr_item, "rear")

    args.iter8_dir.mkdir(parents=True, exist_ok=True)
    patch_dir = args.iter8_dir / "patch"
    pulls_dir = args.iter8_dir / "pulls"
    patch_dir.mkdir(parents=True, exist_ok=True)
    pulls_dir.mkdir(parents=True, exist_ok=True)
    patched = patch_dir / "iter_8_patched.pvv"

    tree.write(str(patched), encoding="utf-8", xml_declaration=True)

    try:
        g2.verify_patch_gates(
            patched,
            args.base,
            EXPECTED_CHANGED_ITER8,
            UNTOUCHABLE_ITER8,
            (f_spark_base, f_spark_new),
            (r_spark_base, r_spark_new),
            ve_stage_front=f_ve_base,
            ve_patched_front=f_ve_new,
            ve_stage_rear=r_ve_base,
            ve_patched_rear=r_ve_new,
            ve_max_frac_change=VE_MAX_CHANGE_PCT,
        )
    except RuntimeError as exc:
        patched.unlink(missing_ok=True)
        print(f"ABORT: {exc}", file=sys.stderr)
        return 6

    front_spark_rows = g2.collect_spark_delta_rows(
        "front", f_row, f_col, f_spark_base, f_spark_new, f_src
    )
    rear_spark_rows = g2.collect_spark_delta_rows(
        "rear", r_row, r_col, r_spark_base, r_spark_new, r_src
    )
    spark_rows = [*front_spark_rows, *rear_spark_rows]
    ve_rows = [*f_ve_rows, *r_ve_rows]
    _write_spark_delta_csv(patch_dir / "spark_advance_delta.csv", front_spark_rows, rear_spark_rows)
    _write_ve_delta_csv(patch_dir / "ve_smoothing_delta.csv", ve_rows)

    new_sha = g2.sha256(patched)
    _write_change_log(patch_dir / "change_log.md", base_sha, new_sha, ve_rows, spark_rows)
    _write_guardrails(patch_dir / "guardrails.md")
    _write_iteration_json(args.iter8_dir / "iteration.json", patched.name)

    manifest = pulls_dir / "manifest.json"
    if not manifest.exists():
        manifest.write_text(
            json.dumps(
                {
                    "iteration_id": "iter_8",
                    "tune_state": patched.name,
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
    print(f"  iter_8_patched SHA-256: {new_sha}")
    print(f"  spark cells changed: {len(spark_rows)}")
    print(f"  VE cells changed:    {len(ve_rows)}")
    print(f"  artifacts: {patch_dir}")
    print(f"  flash this file: {patched}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
