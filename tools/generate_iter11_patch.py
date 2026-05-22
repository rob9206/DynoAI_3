"""
DynoAI iter_11 patch generator -- directed cruise VE trim from measured AFR.

Background:
    iter_9 cruise pulls (_46/47/48, 1099 steady-state samples) showed the loaded
    dyno is hitting the cruise/part-throttle VE cells at TPS 5-25%, RPM 1.75-4.5,
    with persistent richness (correction 0.81-0.95 = need to trim VE 5-19%).
    iter_9 only trimmed TPS columns 0/2/5/7/10 by a fixed -7%, so cells at TPS
    15/20/25 were untouched.

Strategy:
    Read iter_11/analysis/cell_corrections.csv and apply directed per-cell VE
    trim where evidence is strong. Mirror the same trim to Front and Rear.

Apply rules (all must pass to trim a cell):
    - n >= MIN_HITS samples in cell
    - measured correction < ENRICH_THRESH (only lean, never enrich)
    - RPM row in [RPM_LO, RPM_HI]
    - TPS column in TPS_SCOPE
    - delta capped at MAX_TRIM_PCT

Tables changed:
    - VE (TPS based/Front Cyl)
    - VE (TPS based/Rear Cyl)

Tables byte-identical to iter_9:
    - Spark Advance Front/Rear, Engine Displacement
    - Acceleration Enrichment, AFR / PE AFR
    - Max Knock Retard, RPM Limit, Deceleration Enleanment (iter_9 0.92 preserved)
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

sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate_iter2_patch as g2  # noqa: E402

logger = logging.getLogger(__name__)

SESSION_DIR = g2.SESSION_DIR
DEFAULT_BASE = SESSION_DIR / "iterations" / "iter_9" / "patch" / "iter_9_patched.pvv"
DEFAULT_ITER11 = SESSION_DIR / "iterations" / "iter_11"
DEFAULT_CORRECTIONS = (
    SESSION_DIR / "iterations" / "iter_11" / "analysis" / "cell_corrections.csv"
)

MIN_HITS = 5
ENRICH_THRESH = 0.97
MAX_TRIM_PCT = -0.10
RPM_LO = 1.5
RPM_HI = 5.5
TPS_SCOPE = {5.0, 7.3, 10.0, 15.0, 20.0, 25.0, 30.0}

EXPECTED_CHANGED = sorted([g2.VE_FRONT_TABLE, g2.VE_REAR_TABLE])
UNTOUCHABLE = sorted(
    [
        g2.DISPLACEMENT_TABLE,
        g2.SPARK_FRONT_TABLE,
        g2.SPARK_REAR_TABLE,
        g2.KNOCK_RETARD_TABLE,
        g2.RPM_LIMIT_TABLE,
        g2.AFR_TARGET_TABLE,
        g2.AFR_STOICH_TABLE,
        g2.ACCEL_ENRICH_TABLE,
        g2.DECEL_ENLEANMENT_TABLE,
    ]
)


def _load_corrections(path: Path) -> list[dict]:
    rows: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(
                {
                    "rpm_idx": int(r["rpm_idx"]),
                    "tps_idx": int(r["tps_idx"]),
                    "rpm_k": float(r["rpm_k"]),
                    "tps_pct": float(r["tps_pct"]),
                    "n": int(r["n"]),
                    "lc2_avg": float(r["lc2_avg"]),
                    "target_avg": float(r["target_avg"]),
                    "corr_avg": float(r["corr_avg"]),
                    "map_avg": float(r["map_avg"]),
                }
            )
    return rows


def _apply_trims(
    item: ET.Element,
    cyl_label: str,
    corrections: list[dict],
) -> tuple[list[float], list[float], list[list[float]], list[list[float]], list[dict]]:
    rpm_axis, tps_axis, base_grid_t = g2.read_table(item)
    base_grid = [list(r) for r in base_grid_t]
    new_grid = [list(r) for r in base_grid_t]
    delta_rows: list[dict] = []
    skipped: list[dict] = []

    for c in corrections:
        ri, ti = c["rpm_idx"], c["tps_idx"]
        rpm_k = rpm_axis[ri]
        tps_pct = tps_axis[ti]
        reason = None
        if c["n"] < MIN_HITS:
            reason = f"n={c['n']}<{MIN_HITS}"
        elif c["corr_avg"] >= ENRICH_THRESH:
            reason = f"corr={c['corr_avg']:.3f}>={ENRICH_THRESH}"
        elif not (RPM_LO <= rpm_k <= RPM_HI):
            reason = f"rpm_k={rpm_k:g} outside [{RPM_LO},{RPM_HI}]"
        elif tps_pct not in TPS_SCOPE:
            reason = f"tps_pct={tps_pct:g} not in scope"
        if reason is not None:
            skipped.append({**c, "reason": reason})
            continue

        capped = max(c["corr_avg"], 1.0 + MAX_TRIM_PCT)
        base = base_grid[ri][ti]
        new = base * capped
        if new == base:
            continue
        new_grid[ri][ti] = new
        delta_rows.append(
            {
                "cylinder": cyl_label,
                "rpm_idx": ri,
                "tps_idx": ti,
                "rpm_k": rpm_k,
                "tps_pct": tps_pct,
                "n": c["n"],
                "lc2_avg": c["lc2_avg"],
                "target_avg": c["target_avg"],
                "corr_meas": c["corr_avg"],
                "corr_applied": capped,
                "ve_base": base,
                "ve_new": new,
                "delta": new - base,
                "delta_pct": (new - base) / base * 100.0 if abs(base) > 1e-9 else 0.0,
            }
        )

    g2.write_cells(item, new_grid)
    return rpm_axis, tps_axis, base_grid, new_grid, delta_rows


def _write_delta_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "cylinder",
                "rpm_idx",
                "tps_idx",
                "rpm_k",
                "tps_pct",
                "n",
                "lc2_avg",
                "target_avg",
                "corr_meas",
                "corr_applied",
                "ve_base",
                "ve_new",
                "delta",
                "delta_pct",
            ]
        )
        for r in rows:
            w.writerow(
                [
                    r["cylinder"],
                    r["rpm_idx"],
                    r["tps_idx"],
                    f"{r['rpm_k']:g}",
                    f"{r['tps_pct']:g}",
                    r["n"],
                    f"{r['lc2_avg']:.2f}",
                    f"{r['target_avg']:.2f}",
                    f"{r['corr_meas']:.4f}",
                    f"{r['corr_applied']:.4f}",
                    f"{r['ve_base']:.2f}",
                    f"{r['ve_new']:.2f}",
                    f"{r['delta']:+.3f}",
                    f"{r['delta_pct']:+.2f}",
                ]
            )


def _write_change_log(
    path: Path,
    base_sha: str,
    new_sha: str,
    delta_rows: list[dict],
    cell_count: int,
    capped_count: int,
) -> None:
    top = sorted(delta_rows, key=lambda r: -abs(r["delta_pct"]))[:25]
    lines = [
        "# iter_11 Patch -- directed cruise VE trim from measured AFR",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "Vehicle: Ryan Titus 2006 Fat Boy CVO (103 ci)",
        "Session: 2026-05-10_4thgear_baseline",
        "",
        "iter_9 cruise pulls (`_46/47/48`, 1099 steady-state samples) showed the",
        "loaded dyno hitting cells at TPS 5-25% RPM 1.75-4.5 still rich after iter_9",
        "(which only trimmed TPS 0/2/5/7/10 by fixed -7%).",
        "",
        f"- base file: `iter_9_patched.pvv`",
        f"- base SHA-256: `{base_sha}`",
        f"- iter_11_patched.pvv SHA-256: `{new_sha}`",
        "",
        "## Strategy",
        "",
        "Per-cell directed VE trim using measured AFR error:",
        f"- Min hits per cell: {MIN_HITS}",
        f"- Apply only if measured correction < {ENRICH_THRESH} (lean-only, never enrich)",
        f"- RPM scope: {RPM_LO} - {RPM_HI} (RPM x 1000)",
        f"- TPS columns in scope: {sorted(TPS_SCOPE)}",
        f"- Trim cap: {MAX_TRIM_PCT * 100:.0f}% per cell",
        "- Mirror Front and Rear with identical trim",
        "",
        "## Result",
        "",
        f"- Cells trimmed (per cylinder): {cell_count // 2}",
        f"- Cells where evidence asked for >{abs(MAX_TRIM_PCT) * 100:.0f}% but capped: "
        f"{capped_count}",
        "",
        "## Top trims by absolute delta_pct",
        "",
        "| cyl | rpm_k | tps | n | LC2 | tgt | corr_meas | applied | base | new | delta_pct |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in top:
        lines.append(
            f"| {r['cylinder']} | {r['rpm_k']:g} | {r['tps_pct']:g} | {r['n']} | "
            f"{r['lc2_avg']:.2f} | {r['target_avg']:.2f} | {r['corr_meas']:.3f} | "
            f"{r['corr_applied']:.3f} | {r['ve_base']:.2f} | {r['ve_new']:.2f} | "
            f"{r['delta_pct']:+.2f}% |"
        )
    lines.extend(
        [
            "",
            "## Tables byte-identical to iter_9",
            "",
            "- Spark Advance Front/Rear (iter_8 +2 deg WOT preserved)",
            "- Engine Displacement (103.0 CID)",
            "- Acceleration Enrichment (iter_6 AE fix preserved)",
            "- AFR / PE AFR",
            "- Max Knock Retard, RPM Limit",
            "- Deceleration Enleanment (iter_9 0.92 preserved)",
            "",
            "## Expected outcome",
            "",
            "- Cruise AFR at TPS 15-25% on loaded dyno: should rise from LC2 11.8-12.3 toward 13.0-13.5",
            "- Real cruise (MAP 60-70 kPa): unchanged from iter_9",
            "- WOT power: identical to iter_9 (94.2 hp avg)",
            "- Tip-in transient: unchanged",
            "",
            "## Pull plan",
            "",
            "- Cruise sweep at TPS 10-25% across 2000-4500 RPM (loaded), log",
            "- Snap-closed throttle from 4000+ RPM to validate iter_9 decel fix is live",
            "- One confirmation WOT pull (verify WOT untouched)",
            "",
            "## Abort criteria",
            "",
            "- Cruise stumble or surging: revert iter_9",
            "- WOT HP drop: revert (should not happen, WOT VE/spark untouched)",
            "",
            f"Revert file: `iter_9_patched.pvv` (SHA-256 `{base_sha}`).",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_iteration_json(path: Path, patch_filename: str, cell_count: int) -> None:
    payload = {
        "id": "iter_11",
        "session_id": "2026-05-10_4thgear_baseline",
        "index": 11,
        "patch_filename": patch_filename,
        "patch_base": "iter_9_patched.pvv",
        "supersedes": None,
        "evidence_dir": "iterations/iter_9/pulls",
        "status": "ready_to_flash",
        "flashed_at": None,
        "notes": (
            f"iter_11 = iter_9 base + directed cruise VE trim. {cell_count // 2} cells per "
            "cylinder trimmed using measured per-cell AFR error from iter_9 cruise pulls "
            "(_46/47/48, 1099 steady-state samples). Lean-only, capped at -10%/cell, "
            "mirrored Front+Rear. WOT, spark, decel enleanment, AE, AFR untouched."
        ),
        "created_at": datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", type=Path, default=DEFAULT_BASE)
    ap.add_argument("--corrections", type=Path, default=DEFAULT_CORRECTIONS)
    ap.add_argument("--iter11-dir", type=Path, default=DEFAULT_ITER11)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    if args.verbose:
        logging.basicConfig(level=logging.INFO, format="%(message)s")

    if not args.base.exists():
        print(f"ERROR: base not found {args.base}", file=sys.stderr)
        return 2
    if not args.corrections.exists():
        print(f"ERROR: corrections csv not found {args.corrections}", file=sys.stderr)
        return 3

    corrections = _load_corrections(args.corrections)
    base_sha = g2.sha256(args.base)
    tree = ET.parse(str(args.base))
    root = tree.getroot()

    vf_item = g2.find_item_by_name(root, g2.VE_FRONT_TABLE)
    vr_item = g2.find_item_by_name(root, g2.VE_REAR_TABLE)
    if vf_item is None or vr_item is None:
        print("ERROR: VE tables missing", file=sys.stderr)
        return 4

    _, _, vf_base, vf_new, vf_rows = _apply_trims(vf_item, "front", corrections)
    _, _, vr_base, vr_new, vr_rows = _apply_trims(vr_item, "rear", corrections)

    capped_count = sum(
        1 for r in (vf_rows + vr_rows) if abs(r["corr_meas"] - r["corr_applied"]) > 1e-6
    )

    args.iter11_dir.mkdir(parents=True, exist_ok=True)
    patch_dir = args.iter11_dir / "patch"
    pulls_dir = args.iter11_dir / "pulls"
    patch_dir.mkdir(parents=True, exist_ok=True)
    pulls_dir.mkdir(parents=True, exist_ok=True)
    patched = patch_dir / "iter_11_patched.pvv"
    tree.write(str(patched), encoding="utf-8", xml_declaration=True)

    sf_item = g2.find_item_by_name(root, g2.SPARK_FRONT_TABLE)
    sr_item = g2.find_item_by_name(root, g2.SPARK_REAR_TABLE)
    _, _, sf_grid = g2.read_table(sf_item)
    _, _, sr_grid = g2.read_table(sr_item)

    try:
        g2.verify_patch_gates(
            patched,
            args.base,
            EXPECTED_CHANGED,
            UNTOUCHABLE,
            (sf_grid, sf_grid),
            (sr_grid, sr_grid),
            ve_stage_front=vf_base,
            ve_patched_front=vf_new,
            ve_stage_rear=vr_base,
            ve_patched_rear=vr_new,
            ve_max_frac_change=abs(MAX_TRIM_PCT) + 1e-6,
        )
    except RuntimeError as exc:
        patched.unlink(missing_ok=True)
        print(f"ABORT: {exc}", file=sys.stderr)
        return 5

    new_sha = g2.sha256(patched)
    _write_delta_csv(patch_dir / "ve_directed_trim_delta.csv", vf_rows + vr_rows)
    _write_change_log(
        patch_dir / "change_log.md",
        base_sha,
        new_sha,
        vf_rows + vr_rows,
        len(vf_rows) + len(vr_rows),
        capped_count,
    )
    _write_iteration_json(
        args.iter11_dir / "iteration.json", patched.name, len(vf_rows) + len(vr_rows)
    )

    manifest = pulls_dir / "manifest.json"
    if not manifest.exists():
        manifest.write_text(
            json.dumps(
                {
                    "iteration_id": "iter_11",
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

    print("OK")
    print(f"  base            SHA-256: {base_sha}")
    print(f"  iter_11_patched SHA-256: {new_sha}")
    print(f"  cells trimmed:  front={len(vf_rows)}  rear={len(vr_rows)}")
    print(f"  hit -10% cap:   {capped_count}")
    print(f"  artifacts: {patch_dir}")
    print(f"  flash this file: {patched}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
