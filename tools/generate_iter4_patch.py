"""
DynoAI iter_4 patch generator -- small lean trim on top of iter_3.

Base: iter_3_patched.pvv (already flashed). Only mutates VE Front + Rear.
Applies ONLY negative ve_delta_pct (rich-cell trim) clamped to -5% per cell.
Positive (lean) cells from the iter_3 findings are skipped this iteration --
they are typically transient noise at part-throttle and will be re-evaluated
post-flash. AFR targets, spark, displacement, decel, knock cap, RPM limit
stay byte-identical to iter_3.

Usage:
    python tools/iter3/analyze_iter2_dwrt.py \
        --base-pvv ...iter_3/patch/iter_3_patched.pvv \
        --pulls-dir ...iter_3/pulls \
        --out ...iter_3/analyses/iter3_dwrt_findings.json
    python tools/generate_iter4_patch.py
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
DEFAULT_BASE = SESSION_DIR / "iterations" / "iter_3" / "patch" / "iter_3_patched.pvv"
DEFAULT_ITER4 = SESSION_DIR / "iterations" / "iter_4"
DEFAULT_FINDINGS = (
    SESSION_DIR / "iterations" / "iter_3" / "analyses" / "iter3_dwrt_findings.json"
)

VE_MAX_FRAC_CHANGE = 0.05
APPLY_LEAN_ADD = False
MIN_TRIM_PCT = 1.0


EXPECTED_CHANGED_ITER4 = sorted([g2.VE_FRONT_TABLE, g2.VE_REAR_TABLE])

UNTOUCHABLE_ITER4 = sorted([
    g2.DISPLACEMENT_TABLE,
    g2.SPARK_FRONT_TABLE,
    g2.SPARK_REAR_TABLE,
    g2.DECEL_ENLEANMENT_TABLE,
    g2.KNOCK_RETARD_TABLE,
    g2.RPM_LIMIT_TABLE,
    g2.AFR_TARGET_TABLE,
    g2.AFR_STOICH_TABLE,
])


def _apply_ve_trim(
    item: ET.Element,
    base_grid: list[list[float]],
    corrections: list[dict],
) -> tuple[list[list[float]], list[list[float]], int]:
    """Apply only negative ve_delta_pct >= MIN_TRIM_PCT magnitude; clamp to +/-5%."""
    new_grid = deepcopy(base_grid)
    applied = 0
    for cell in corrections:
        d_pct = float(cell["ve_delta_pct"])
        if not APPLY_LEAN_ADD and d_pct >= 0:
            continue
        if abs(d_pct) < MIN_TRIM_PCT:
            continue
        r = int(cell["row_idx"])
        c = int(cell["col_idx"])
        b = base_grid[r][c]
        nv = b * (1.0 + d_pct / 100.0)
        lo, hi = b * (1.0 - VE_MAX_FRAC_CHANGE), b * (1.0 + VE_MAX_FRAC_CHANGE)
        clamped = max(lo, min(hi, nv))
        if abs(clamped - b) < 1e-9:
            continue
        new_grid[r][c] = clamped
        applied += 1
    g2.write_cells(item, new_grid)
    return base_grid, new_grid, applied


def _write_ve_delta_csv(
    path: Path,
    cylinder: str,
    row_axis: list[float],
    col_axis: list[float],
    base_grid: list[list[float]],
    new_grid: list[list[float]],
    n_by_rc: dict[tuple[int, int], int],
    err_by_rc: dict[tuple[int, int], float],
) -> None:
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for r, rpm_k in enumerate(row_axis):
            for c, tps in enumerate(col_axis):
                if abs(new_grid[r][c] - base_grid[r][c]) < 1e-9:
                    continue
                rpm_display = int(round(rpm_k * 1000))
                base = base_grid[r][c]
                new = new_grid[r][c]
                delta = (new - base) / base * 100.0 if abs(base) > 1e-9 else 0.0
                w.writerow([
                    cylinder,
                    rpm_display,
                    tps,
                    n_by_rc.get((r, c), ""),
                    f"{err_by_rc.get((r, c), 0.0):+.2f}",
                    f"{base:.3f}",
                    f"{new:.3f}",
                    f"{delta:+.3f}",
                ])


def _write_iter4_change_log(
    path: Path,
    base_sha: str,
    new_sha: str,
    findings_path: Path,
    ve_cells_applied: int,
    skipped_lean: int,
    skipped_small: int,
) -> None:
    findings = json.loads(findings_path.read_text(encoding="utf-8"))
    try:
        findings_rel = findings_path.relative_to(PROJECT_ROOT)
    except ValueError:
        findings_rel = findings_path
    src_lines = [
        f"- `{s['name']}` SHA-256 `{s['sha256']}`  peak_hp={s.get('peak_hp', 'n/a')}"
        for s in findings.get("sources", [])
    ]
    lines = [
        "# iter_4 Patch -- small lean trim on top of iter_3",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "Vehicle: Ryan Titus 2006 Fat Boy CVO (103 ci)",
        "Session: 2026-05-10_4thgear_baseline",
        "",
        "iter_3 was flashed and produced 5 clean 4th-gear pulls in the 91.2-92.0 hp",
        "band with LC2 peak AFR of 11.8-12.4 (rich of Dynojet PE target ~12.8 by",
        "0.4-1.0 AFR). iter_4 walks back the over-fueling at WOT cells with strong",
        "evidence. Only NEGATIVE (rich-cell) VE corrections are applied; positive",
        "(lean) corrections are skipped this iteration because the high-error",
        "light-TPS cells have low sample counts and likely contain transient noise.",
        "",
        f"- base file: `iter_3_patched.pvv`",
        f"- base SHA-256: `{base_sha}`",
        f"- iter_4_patched.pvv SHA-256: `{new_sha}`",
        f"- findings: `{findings_rel}`",
        f"- VE cells trimmed (front+rear same bins): {ve_cells_applied}",
        f"- VE cells skipped (positive/lean, this iter): {skipped_lean}",
        f"- VE cells skipped (|delta| < {MIN_TRIM_PCT}%): {skipped_small}",
        f"- per-cell clamp: +/-{VE_MAX_FRAC_CHANGE * 100:.0f}% vs iter_3",
        "",
        "## Tables changed vs iter_3 (base)",
        "",
        "- VE (TPS based/Front Cyl): rich cells trimmed only",
        "- VE (TPS based/Rear Cyl): same delta pattern (collector probe, no per-cyl split)",
        "",
        "## Tables byte-identical to iter_3",
        "",
        "- Engine Displacement (103.0 CID stays)",
        "- Spark Advance Front/Rear (cam advance + 5500 knock notch preserved)",
        "- AFR / PE AFR (targets unchanged -- ground truth is still Dynojet PE)",
        "- Deceleration Enleanment, Max Knock Retard, RPM Limit",
        "",
        "## Evidence (DWRT logs from iter_3 post-flash)",
        *src_lines,
        "",
        "## Expected outcome",
        "",
        "- Peak LC2 AFR moves from ~12.0 toward ~12.5-12.8 at WOT 3000-5500 RPM",
        "- Peak HP: same or +0.5 to +1.5 (MBT shift from rich to near-target)",
        "- If HP drops or LC2 goes above 13.5 in any 100% TPS cell, hold and review",
        "",
        "## First-pull post-flash protocol",
        "",
        "- 4th gear, same dyno setup as iter_3",
        "- Watch LC2 in 3000-5500 RPM 100% TPS window; expect 12.5-12.8",
        "- Abort if LC2 > 13.8 (too lean of MBT, risk of knock)",
        "- Abort if knock retard > 4 deg (cap from iter_3)",
        "",
        "## Revert",
        "",
        f"Re-flash `iter_3_patched.pvv` (SHA-256 `{base_sha}`).",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_iter4_guardrails(path: Path) -> None:
    lines = [
        "# iter_4 Operational Guardrails",
        "",
        "Small lean trim on rich cells from iter_3 post-flash evidence.",
        "",
        "## Before pulls",
        "",
        "- [ ] LC2 reads plausible band (10-19) before loading drum",
        "- [ ] DynoWare RT RPM source still 'Harley - ECU Engine Speed' / channel stable",
        "- [ ] CHT < 220F before pull",
        "",
        "## During pulls",
        "",
        "- [ ] LC2 between 12.5 and 13.5 at WOT 3000-5500 RPM is the win condition",
        "- [ ] LC2 > 13.8 anywhere at WOT -- abort, do not flash iter_5",
        "- [ ] Knock retard > 4 deg -- abort and report",
        "",
        "## After pulls",
        "",
        "- [ ] Capture 3 clean 4th-gear WOT pulls minimum",
        "- [ ] Compare peak HP and AFR distribution to iter_3 5-pull set",
        "",
        "See `vehicles/ryantitus_fatboy_cvo/profile.json` tuning_guardrails.",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_iter4_iteration_json(path: Path, patch_filename: str, findings_name: str) -> None:
    payload = {
        "id": "iter_4",
        "session_id": "2026-05-10_4thgear_baseline",
        "index": 4,
        "patch_filename": patch_filename,
        "patch_base": "iter_3_patched.pvv",
        "supersedes": "iter_3",
        "evidence_findings": findings_name,
        "status": "ready_to_flash",
        "flashed_at": None,
        "notes": (
            "iter_4 = small lean trim on top of iter_3. Only negative VE corrections "
            f"(rich cells) applied, clamped to +/-{VE_MAX_FRAC_CHANGE * 100:.0f}% per cell. "
            "AFR targets / spark / displacement / decel / knock cap / RPM limit "
            "byte-identical to iter_3. Source: iter_3 post-flash 4th-gear pulls."
        ),
        "created_at": datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", type=Path, default=DEFAULT_BASE)
    ap.add_argument("--iter4-dir", type=Path, default=DEFAULT_ITER4)
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
        print("ERROR: ve_correction_grid empty", file=sys.stderr)
        return 4

    n_by_rc: dict[tuple[int, int], int] = {
        (int(c["row_idx"]), int(c["col_idx"])): int(c["n"]) for c in ve_grid
    }
    err_by_rc: dict[tuple[int, int], float] = {
        (int(c["row_idx"]), int(c["col_idx"])): float(c["median_err_pct"])
        for c in ve_grid
    }

    base_sha = g2.sha256(args.base)
    tree = ET.parse(str(args.base))
    root = tree.getroot()

    vf_item = g2.find_item_by_name(root, g2.VE_FRONT_TABLE)
    vr_item = g2.find_item_by_name(root, g2.VE_REAR_TABLE)
    if vf_item is None or vr_item is None:
        print("ERROR: VE tables missing in base", file=sys.stderr)
        return 5

    vf_row, vf_col, vf_base = g2.read_table(vf_item)
    vr_row, vr_col, vr_base = g2.read_table(vr_item)

    skipped_lean = sum(1 for c in ve_grid if float(c["ve_delta_pct"]) >= 0)
    skipped_small = sum(
        1
        for c in ve_grid
        if float(c["ve_delta_pct"]) < 0
        and abs(float(c["ve_delta_pct"])) < MIN_TRIM_PCT
    )

    logger.info("Applying VE trim (rich-only)")
    _, vf_new, fc = _apply_ve_trim(vf_item, vf_base, ve_grid)
    _, vr_new, rc = _apply_ve_trim(vr_item, vr_base, ve_grid)

    args.iter4_dir.mkdir(parents=True, exist_ok=True)
    patch_dir = args.iter4_dir / "patch"
    pulls_dir = args.iter4_dir / "pulls"
    patch_dir.mkdir(parents=True, exist_ok=True)
    pulls_dir.mkdir(parents=True, exist_ok=True)
    patched = patch_dir / "iter_4_patched.pvv"

    tree.write(str(patched), encoding="utf-8", xml_declaration=True)

    spark_front_item = g2.find_item_by_name(root, g2.SPARK_FRONT_TABLE)
    spark_rear_item = g2.find_item_by_name(root, g2.SPARK_REAR_TABLE)
    _, _, sf_base_grid = g2.read_table(spark_front_item)  # type: ignore[arg-type]
    _, _, sr_base_grid = g2.read_table(spark_rear_item)  # type: ignore[arg-type]

    try:
        g2.verify_patch_gates(
            patched,
            args.base,
            EXPECTED_CHANGED_ITER4,
            UNTOUCHABLE_ITER4,
            (sf_base_grid, sf_base_grid),
            (sr_base_grid, sr_base_grid),
            ve_stage_front=vf_base,
            ve_patched_front=vf_new,
            ve_stage_rear=vr_base,
            ve_patched_rear=vr_new,
            ve_max_frac_change=VE_MAX_FRAC_CHANGE,
        )
    except RuntimeError as exc:
        patched.unlink(missing_ok=True)
        print(f"ABORT: {exc}", file=sys.stderr)
        return 6

    ve_path = patch_dir / "ve_correction_delta.csv"
    ve_path.write_text(
        "cylinder,RPM,tps_pct,n_samples,median_err_pct,ve_base_pct,ve_new_pct,delta_pct\n",
        encoding="utf-8",
    )
    _write_ve_delta_csv(ve_path, "front", vf_row, vf_col, vf_base, vf_new, n_by_rc, err_by_rc)
    _write_ve_delta_csv(ve_path, "rear", vr_row, vr_col, vr_base, vr_new, n_by_rc, err_by_rc)

    new_sha = g2.sha256(patched)
    cells_changed = sum(
        1
        for r in range(len(vf_base))
        for c in range(len(vf_base[0]))
        if abs(vf_new[r][c] - vf_base[r][c]) > 1e-9
    )

    _write_iter4_change_log(
        patch_dir / "change_log.md",
        base_sha,
        new_sha,
        args.findings,
        cells_changed,
        skipped_lean,
        skipped_small,
    )
    _write_iter4_guardrails(patch_dir / "guardrails.md")
    _write_iter4_iteration_json(args.iter4_dir / "iteration.json", patched.name, args.findings.name)

    pulls_manifest = pulls_dir / "manifest.json"
    if not pulls_manifest.exists():
        pulls_manifest.write_text(
            json.dumps(
                {
                    "iteration_id": "iter_4",
                    "tune_state": "iter_4_patched.pvv",
                    "tune_sha256": new_sha,
                    "flashed_at": None,
                    "afr_source": "dyno_tailpipe_wideband_only",
                    "wideband_channel": "LC2 (Innovate venturi in collector)",
                    "lc1_status": "not_hooked_up_ignore",
                    "pulls": [],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    print("OK")
    print(f"  base           SHA-256: {base_sha}")
    print(f"  iter_4_patched SHA-256: {new_sha}")
    print(f"  VE cells trimmed (front grid): {cells_changed}")
    print(f"  skipped (lean/positive): {skipped_lean}")
    print(f"  skipped (|delta| < {MIN_TRIM_PCT}%): {skipped_small}")
    print(f"  artifacts: {patch_dir}")
    print(f"  flash this file: {patched}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
