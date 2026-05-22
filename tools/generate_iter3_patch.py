"""
DynoAI iter_3 patch generator -- iter_2 v3 changes + VE from DynoWare LC2.

Single flash from `dynojet_stage.pvv` applies displacement, spark, decel,
knock cap, RPM limit (same as iter_2 v3) plus VE corrections from
`iter_2/analyses/iter2_dwrt_findings.json`.

Usage:
    python tools/iter3/analyze_iter2_dwrt.py   # produce findings first
    python tools/generate_iter3_patch.py
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import xml.etree.ElementTree as ET
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import generate_iter2_patch as g2

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SESSION_DIR = g2.SESSION_DIR
DEFAULT_BASE = g2.DEFAULT_BASE
DEFAULT_ITER3 = SESSION_DIR / "iterations" / "iter_3"
DEFAULT_FINDINGS = (
    SESSION_DIR / "iterations" / "iter_2" / "analyses" / "iter2_dwrt_findings.json"
)

VE_MAX_FRAC_CHANGE = 0.10

EXPECTED_CHANGED_ITER3 = sorted(
    list(g2.EXPECTED_CHANGED) + [g2.VE_FRONT_TABLE, g2.VE_REAR_TABLE]
)

UNTOUCHABLE_ITER3 = [
    t
    for t in g2.UNTOUCHABLE_TABLES
    if t not in (g2.VE_FRONT_TABLE, g2.VE_REAR_TABLE)
]


def _apply_ve_from_findings(
    item: ET.Element,
    stage_grid: list[list[float]],
    corrections: list[dict],
) -> tuple[list[list[float]], list[list[float]]]:
    """Apply ve_delta_pct to listed cells; clamp each new cell to +/-10% of base."""
    new_grid = deepcopy(stage_grid)
    base_snapshot = deepcopy(stage_grid)
    for cell in corrections:
        r = int(cell["row_idx"])
        c = int(cell["col_idx"])
        d_pct = float(cell["ve_delta_pct"])
        b = base_snapshot[r][c]
        nv = b * (1.0 + d_pct / 100.0)
        lo, hi = b * (1.0 - VE_MAX_FRAC_CHANGE), b * (1.0 + VE_MAX_FRAC_CHANGE)
        new_grid[r][c] = max(lo, min(hi, nv))
    g2.write_cells(item, new_grid)
    return base_snapshot, new_grid


def _write_ve_delta_csv(
    path: Path,
    cylinder: str,
    row_axis: list[float],
    col_axis: list[float],
    base_grid: list[list[float]],
    new_grid: list[list[float]],
    n_by_rc: dict[tuple[int, int], int],
) -> None:
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for r, rpm_k in enumerate(row_axis):
            for c, tps in enumerate(col_axis):
                if abs(new_grid[r][c] - base_grid[r][c]) < 1e-9:
                    continue
                rpm_display = int(round(rpm_k * 1000))
                w.writerow([
                    cylinder,
                    rpm_display,
                    tps,
                    n_by_rc.get((r, c), ""),
                    f"{base_grid[r][c]:.3f}",
                    f"{new_grid[r][c]:.3f}",
                    f"{(new_grid[r][c] - base_grid[r][c]) / base_grid[r][c] * 100.0:+.3f}"
                    if abs(base_grid[r][c]) > 1e-9
                    else "",
                ])


def _write_iter3_change_log(
    path: Path,
    base_sha: str,
    new_sha: str,
    findings_path: Path,
    ve_cells: int,
    disp_base: float,
    spark_summary: dict[str, int],
) -> None:
    findings = json.loads(findings_path.read_text(encoding="utf-8"))
    try:
        findings_rel = findings_path.relative_to(PROJECT_ROOT)
    except ValueError:
        findings_rel = findings_path
    src_lines = [f"- `{s['name']}` SHA-256 `{s['sha256']}`" for s in findings.get("sources", [])]
    lines = [
        "# iter_3 Patch -- supersedes iter_2 v3 (single flash)",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "Vehicle: Ryan Titus 2006 Fat Boy CVO (103 ci)",
        "Session: 2026-05-10_4thgear_baseline",
        "",
        "iter_2 v3 was generated but never flashed. Dyno pulls on the original",
        "Dynojet stage tune were captured with Innovate venturi wideband on",
        "DynoWare RT LC2. iter_3 applies every iter_2 v3 change plus VE corrections",
        "from LC2 vs Dynojet AFR target tables (AFR targets left unchanged).",
        "",
        f"- base file: `dynojet_stage.pvv`",
        f"- base SHA-256: `{base_sha}`",
        f"- iter_3_patched.pvv SHA-256: `{new_sha}`",
        f"- findings: `{findings_rel}`",
        f"- VE cells adjusted (front+rear same bins): {ve_cells}",
        "",
        "## Evidence (DWRT logs)",
        *src_lines,
        "",
        "## iter_2 v3 changes (included)",
        "",
        f"- Engine Displacement: {disp_base:.2f} -> {g2.NEW_DISPLACEMENT_CID:.2f} CID",
        f"- Spark front/rear cells changed: {spark_summary['front_cells']} / {spark_summary['rear_cells']}",
        f"- Deceleration Enleanment: all -> {g2.NEW_DECEL_MULTIPLIER}",
        f"- Max Knock Retard: cap {g2.KNOCK_CAP_DEG:.0f} deg",
        f"- RPM Limit: -> {g2.NEW_RPM_LIMIT} RPMx1000",
        "",
        "## iter_3 additions",
        "",
        "- VE (TPS based/Front Cyl) and VE (TPS based/Rear Cyl): same bulk-AFR",
        "  correction applied to both (collector probe; no per-cylinder split).",
        f"- Per-cell VE change capped at +/-{VE_MAX_FRAC_CHANGE * 100:.0f}% vs Dynojet stage.",
        "",
        "## LC2 probe health (annotate-only)",
        "",
        "Rows where LC2 pegged at the A/D ceiling were excluded from the median",
        "binning but remain in the raw logs. After flash, watch LC2 in the first",
        "10 s of pull 1; a stuck rail voltage means replace the probe before trusting VE.",
        "",
        "## First-pull post-flash protocol",
        "",
        "Same abort criteria as iter_2 v3 (injector duty, knock peg, CHT, smoke).",
        "Additionally: if LC2 flatlines or pegs at ceiling, abort and replace probe.",
        "",
        "## Revert",
        "",
        f"Re-flash `dynojet_stage.pvv` (SHA-256 `{base_sha}`).",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_iter3_guardrails(path: Path) -> None:
    lines = [
        "# iter_3 Operational Guardrails",
        "",
        "Same dyno-operator rules as iter_2; VE was adjusted from tailpipe LC2.",
        "",
        "## LC2 sanity",
        "",
        "- [ ] LC2 reads a plausible AFR band (roughly 10-19) before loading the drum",
        "- [ ] First 10 s of pull 1: LC2 must move with mixture; stuck 22.39 = dead probe",
        "",
        "## After iter_3 flash",
        "",
        "- [ ] Compare LC2 to Desired AFR / PE targets; >1.5 AFR systematic error in a",
        "      RPM/TPS zone flags a bad bin or transient data -- schedule iter_4",
        "",
        "See `vehicles/ryantitus_fatboy_cvo/profile.json` tuning_guardrails.",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_iteration_json(path: Path, patch_filename: str, findings_name: str) -> None:
    payload = {
        "id": "iter_3",
        "session_id": "2026-05-10_4thgear_baseline",
        "index": 3,
        "patch_filename": patch_filename,
        "patch_base": "dynojet_stage.pvv",
        "supersedes": "iter_2",
        "evidence_findings": findings_name,
        "flashed_at": None,
        "notes": (
            "iter_3 = iter_2 v3 (never flashed) plus VE corrections from DynoWare RT "
            "logs analyzed in iter_2/analyses/iter2_dwrt_findings.json. Single flash "
            "from dynojet_stage.pvv. AFR target tables unchanged. LC2 = Innovate venturi."
        ),
        "created_at": datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", type=Path, default=DEFAULT_BASE)
    ap.add_argument("--iter3-dir", type=Path, default=DEFAULT_ITER3)
    ap.add_argument("--findings", type=Path, default=DEFAULT_FINDINGS)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    if args.verbose:
        logging.basicConfig(level=logging.INFO, format="%(message)s")

    if not args.base.exists():
        print(f"ERROR: base not found {args.base}", file=sys.stderr)
        return 2
    if not args.findings.exists():
        print(f"ERROR: findings not found {args.findings}", file=sys.stderr)
        return 3

    findings = json.loads(args.findings.read_text(encoding="utf-8"))
    ve_grid = findings.get("ve_correction_grid") or []
    if not ve_grid:
        print("ERROR: ve_correction_grid empty; run analyze_iter2_dwrt.py", file=sys.stderr)
        return 4

    n_by_rc: dict[tuple[int, int], int] = {
        (int(c["row_idx"]), int(c["col_idx"])): int(c["n"]) for c in ve_grid
    }

    base_sha = g2.sha256(args.base)
    tree = ET.parse(str(args.base))
    root = tree.getroot()

    items: dict[str, ET.Element | None] = {
        name: g2.find_item_by_name(root, name)
        for name in (
            g2.DISPLACEMENT_TABLE,
            g2.SPARK_FRONT_TABLE,
            g2.SPARK_REAR_TABLE,
            g2.DECEL_ENLEANMENT_TABLE,
            g2.KNOCK_RETARD_TABLE,
            g2.RPM_LIMIT_TABLE,
            g2.VE_FRONT_TABLE,
            g2.VE_REAR_TABLE,
        )
    }
    missing = [n for n, it in items.items() if it is None]
    if missing:
        print(f"ERROR: missing tables {missing}", file=sys.stderr)
        return 5

    logger.info("iter_2-style mutations")
    disp_base, _ = g2.apply_displacement(items[g2.DISPLACEMENT_TABLE])  # type: ignore[arg-type]
    f_row, f_col, f_sb, f_sn, f_src = g2.apply_spark_changes(items[g2.SPARK_FRONT_TABLE])  # type: ignore[arg-type]
    r_row, r_col, r_sb, r_sn, r_src = g2.apply_spark_changes(items[g2.SPARK_REAR_TABLE])  # type: ignore[arg-type]
    dec_c, dec_b, dec_n = g2.apply_decel_enleanment(items[g2.DECEL_ENLEANMENT_TABLE])  # type: ignore[arg-type]
    kn_c, kn_b, kn_n = g2.apply_knock_retard_cap(items[g2.KNOCK_RETARD_TABLE])  # type: ignore[arg-type]
    rpm_c, rpm_b, rpm_n = g2.apply_rpm_limit(items[g2.RPM_LIMIT_TABLE])  # type: ignore[arg-type]

    vf_row, vf_col, vf_stage = g2.read_table(items[g2.VE_FRONT_TABLE])  # type: ignore[arg-type]
    vr_row, vr_col, vr_stage = g2.read_table(items[g2.VE_REAR_TABLE])  # type: ignore[arg-type]

    logger.info("VE corrections (%d cells)", len(ve_grid))
    _, vf_new = _apply_ve_from_findings(items[g2.VE_FRONT_TABLE], vf_stage, ve_grid)  # type: ignore[arg-type]
    _, vr_new = _apply_ve_from_findings(items[g2.VE_REAR_TABLE], vr_stage, ve_grid)  # type: ignore[arg-type]

    args.iter3_dir.mkdir(parents=True, exist_ok=True)
    patch_dir = args.iter3_dir / "patch"
    patch_dir.mkdir(parents=True, exist_ok=True)
    patched = patch_dir / "iter_3_patched.pvv"

    tree.write(str(patched), encoding="utf-8", xml_declaration=True)

    try:
        g2.verify_patch_gates(
            patched,
            args.base,
            EXPECTED_CHANGED_ITER3,
            UNTOUCHABLE_ITER3,
            (f_sb, f_sn),
            (r_sb, r_sn),
            ve_stage_front=vf_stage,
            ve_patched_front=vf_new,
            ve_stage_rear=vr_stage,
            ve_patched_rear=vr_new,
            ve_max_frac_change=VE_MAX_FRAC_CHANGE,
        )
    except RuntimeError as exc:
        patched.unlink(missing_ok=True)
        print(f"ABORT: {exc}", file=sys.stderr)
        return 6

    g2.write_displacement_delta_csv(
        patch_dir / "displacement_delta.csv", disp_base, g2.NEW_DISPLACEMENT_CID
    )
    spark_rows = g2.collect_spark_delta_rows(
        "front", f_row, f_col, f_sb, f_sn, f_src
    ) + g2.collect_spark_delta_rows("rear", r_row, r_col, r_sb, r_sn, r_src)
    g2.write_spark_delta_csv(patch_dir / "spark_advance_delta.csv", spark_rows)
    g2.write_simple_delta_csv(
        patch_dir / "decel_enleanment_delta.csv", "CHT_F", dec_c, dec_b, dec_n
    )
    g2.write_simple_delta_csv(
        patch_dir / "knock_retard_delta.csv", "RPM", kn_c, kn_b, kn_n
    )
    g2.write_simple_delta_csv(
        patch_dir / "rpm_limit_delta.csv", "TPS_pct", rpm_c, rpm_b, rpm_n
    )

    ve_path = patch_dir / "ve_correction_delta.csv"
    ve_path.write_text(
        "cylinder,RPM,tps_pct,n_samples,ve_base_pct,ve_new_pct,delta_pct\n",
        encoding="utf-8",
    )
    _write_ve_delta_csv(ve_path, "front", vf_row, vf_col, vf_stage, vf_new, n_by_rc)
    _write_ve_delta_csv(ve_path, "rear", vr_row, vr_col, vr_stage, vr_new, n_by_rc)

    new_sha = g2.sha256(patched)
    fc = sum(
        1
        for r in range(len(f_sb))
        for c in range(len(f_sb[0]))
        if abs(f_sn[r][c] - f_sb[r][c]) > 1e-9
    )
    rc = sum(
        1
        for r in range(len(r_sb))
        for c in range(len(r_sb[0]))
        if abs(r_sn[r][c] - r_sb[r][c]) > 1e-9
    )
    ve_cell_count = sum(
        1
        for r in range(len(vf_stage))
        for c in range(len(vf_stage[0]))
        if abs(vf_new[r][c] - vf_stage[r][c]) > 1e-9
    )

    _write_iter3_change_log(
        patch_dir / "change_log.md",
        base_sha,
        new_sha,
        args.findings,
        ve_cell_count,
        disp_base,
        {"front_cells": fc, "rear_cells": rc},
    )
    _write_iter3_guardrails(patch_dir / "guardrails.md")
    _write_iteration_json(args.iter3_dir / "iteration.json", patched.name, args.findings.name)

    print("OK")
    print(f"  base           SHA-256: {base_sha}")
    print(f"  iter_3_patched SHA-256: {new_sha}")
    print(f"  VE cells changed (front grid): {ve_cell_count}")
    print(f"  artifacts: {patch_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
