"""
DynoAI iter_5 patch generator -- combined VE trim + Acceleration Enrichment fix.

Base: iter_3_patched.pvv (currently flashed). Applies:
  1. Same rich-only VE trim that iter_4 would have applied (clamped to +/-5%)
  2. Acceleration Enrichment table revisions to address mid-RPM lean tip-in
     and remove the 0.91 post-event enleanment tail

This supersedes the never-flashed iter_4. Spark, displacement, AFR targets,
decel enleanment, max knock retard, and RPM limit remain byte-identical to iter_3.

Usage:
    python tools/generate_iter5_patch.py
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
DEFAULT_ITER5 = SESSION_DIR / "iterations" / "iter_5"
DEFAULT_VE_FINDINGS = (
    SESSION_DIR / "iterations" / "iter_3" / "analyses" / "iter3_dwrt_findings.json"
)

VE_MAX_FRAC_CHANGE = 0.05
APPLY_LEAN_ADD = False
MIN_TRIM_PCT = 1.0

AE_TABLE = "Acceleration Enrichment"

AE_NEW_VALUES: dict[int, float] = {
    0: 3.98,
    1: 3.30,
    2: 2.55,
    3: 2.00,
    4: 1.55,
    5: 1.25,
    6: 1.06,
    7: 1.00,
    8: 1.00,
    9: 1.00,
    10: 1.00,
    11: 1.00,
}

AE_SANITY_MAX = 5.0
AE_SANITY_MIN = 0.5

EXPECTED_CHANGED_ITER5 = sorted([g2.VE_FRONT_TABLE, g2.VE_REAR_TABLE, AE_TABLE])

UNTOUCHABLE_ITER5 = sorted([
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
    """Negative-only VE corrections, clamped to +/-5%."""
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


def _apply_ae(item: ET.Element) -> tuple[list[float], list[float], list[float]]:
    """Apply AE_NEW_VALUES to the (single-row) Acceleration Enrichment table.

    Returns (col_axis, base_values, new_values).
    """
    rows = item.find("Rows")
    cols = item.find("Columns")
    if rows is None or cols is None:
        raise RuntimeError(f"{AE_TABLE} missing Rows/Columns")
    col_axis = [g2.parse_float(c.get("label", "0") or "0") for c in cols.findall("Col")]
    row_elems = rows.findall("Row")
    if len(row_elems) != 1:
        raise RuntimeError(
            f"{AE_TABLE} expected 1 row, found {len(row_elems)} -- update generator"
        )
    cells = row_elems[0].findall("Cell")
    if len(cells) != len(AE_NEW_VALUES):
        raise RuntimeError(
            f"{AE_TABLE} expected {len(AE_NEW_VALUES)} cells, found {len(cells)}"
        )

    base_values: list[float] = []
    new_values: list[float] = []
    for i, cell in enumerate(cells):
        base = g2.parse_float(cell.get("value", "0") or "0")
        base_values.append(base)
        new = AE_NEW_VALUES.get(i, base)
        if not (AE_SANITY_MIN <= new <= AE_SANITY_MAX):
            raise RuntimeError(
                f"AE sanity FAIL: col[{i}]={new} outside [{AE_SANITY_MIN}, {AE_SANITY_MAX}]"
            )
        cell.set("value", g2.fmt_cell(new))
        new_values.append(new)
    return col_axis, base_values, new_values


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


def _write_ae_delta_csv(
    path: Path,
    col_axis: list[float],
    base_values: list[float],
    new_values: list[float],
) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["col_idx", "time_index", "ae_base", "ae_new", "delta", "delta_pct"])
        for i, (label, b, n) in enumerate(zip(col_axis, base_values, new_values)):
            d = n - b
            pct = (d / b * 100.0) if abs(b) > 1e-9 else 0.0
            w.writerow([i, f"{label:g}", f"{b:.3f}", f"{n:.3f}", f"{d:+.3f}", f"{pct:+.2f}"])


def _write_iter5_change_log(
    path: Path,
    base_sha: str,
    new_sha: str,
    findings_path: Path,
    ve_cells_applied: int,
    skipped_lean: int,
    skipped_small: int,
    ae_base: list[float],
    ae_new: list[float],
    ae_axis: list[float],
) -> None:
    try:
        findings_rel = findings_path.relative_to(PROJECT_ROOT)
    except ValueError:
        findings_rel = findings_path

    ae_lines = ["| time idx | base | new | delta |", "|---|---|---|---|"]
    for label, b, n in zip(ae_axis, ae_base, ae_new):
        ae_lines.append(f"| {label:g} | {b:.2f} | {n:.2f} | {n - b:+.2f} |")

    lines = [
        "# iter_5 Patch -- combined VE trim + AE fix (supersedes iter_4)",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "Vehicle: Ryan Titus 2006 Fat Boy CVO (103 ci)",
        "Session: 2026-05-10_4thgear_baseline",
        "",
        "iter_3 was flashed and produced two evidence streams:",
        "  1. Five clean 4th-gear pulls: peak HP 91.2-92.0, WOT LC2 11.8-12.4 (rich)",
        "  2. Seven 3rd-gear tip-in pulls (17 events): mid-RPM (3.4k-4.4k) tip-in",
        "     LC2 spiking to 13.9-14.4 (lean)",
        "iter_5 fixes both in one flash. iter_4 (VE trim only) is superseded and",
        "will not be flashed.",
        "",
        f"- base file: `iter_3_patched.pvv`",
        f"- base SHA-256: `{base_sha}`",
        f"- iter_5_patched.pvv SHA-256: `{new_sha}`",
        f"- VE findings: `{findings_rel}`",
        f"- VE cells trimmed (front+rear same bins): {ve_cells_applied}",
        f"- VE cells skipped (positive/lean): {skipped_lean}",
        f"- VE cells skipped (|delta| < {MIN_TRIM_PCT}%): {skipped_small}",
        f"- per-cell VE clamp: +/-{VE_MAX_FRAC_CHANGE * 100:.0f}% vs iter_3",
        "",
        "## Acceleration Enrichment table",
        "",
        "Boost mid-decay AE to address 3000-4700 RPM tip-in lean spikes, and",
        "remove the 0.91 post-event enleanment tail.",
        "",
        *ae_lines,
        "",
        "## Tables changed (3)",
        "",
        "- VE (TPS based/Front Cyl): rich WOT cells trimmed only",
        "- VE (TPS based/Rear Cyl): same delta pattern (collector probe)",
        "- Acceleration Enrichment: mid-decay boost + tail enleanment removal",
        "",
        "## Tables byte-identical to iter_3",
        "",
        "- Engine Displacement (103.0 CID stays)",
        "- Spark Advance Front/Rear (cam advance + 5500 knock notch preserved)",
        "- AFR / PE AFR (targets unchanged)",
        "- Deceleration Enleanment, Max Knock Retard, RPM Limit",
        "",
        "## Expected outcome",
        "",
        "- WOT 3000-5500 RPM 100% TPS: LC2 moves from ~12.0 toward 12.5-12.8",
        "- 3rd-gear tip-in at 3000-4700 RPM: LC2 max during 0-300ms drops from",
        "  ~14.0 toward 12.5-13.0; tip-in feel crisper",
        "- WOT peak HP: unchanged or +0.5 to +1.5",
        "",
        "## Abort criteria post-flash",
        "",
        "- WOT LC2 > 13.8 anywhere in 3000-5500 RPM band -- hold, do not flash iter_6",
        "- Tip-in LC2 < 11.0 sustained -- AE overshoot, revert to iter_3",
        "- Knock retard > 4 deg",
        "",
        "## Revert",
        "",
        f"Re-flash `iter_3_patched.pvv` (SHA-256 `{base_sha}`).",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_iter5_guardrails(path: Path) -> None:
    lines = [
        "# iter_5 Operational Guardrails",
        "",
        "Combined WOT VE trim + Acceleration Enrichment revisions.",
        "",
        "## Pull plan (suggested order)",
        "",
        "- [ ] First: 3 clean 4th-gear WOT pulls to ~6000 RPM (validate WOT AFR)",
        "- [ ] Second: 5 tip-in events in 3rd gear at ~3500-4500 RPM",
        "      (snap throttle 0% -> 100% in <0.2s)",
        "- [ ] Capture ECU log + DWRT trace for both",
        "",
        "## Win conditions",
        "",
        "- WOT LC2 in 3000-5500 RPM avg: 12.5 - 13.0 (target 12.8)",
        "- Tip-in LC2 max in first 300 ms: 12.0 - 13.5",
        "- Knock retard: < 2 deg observed; cap is 4 deg",
        "",
        "## Abort criteria",
        "",
        "- LC2 > 13.8 anywhere at WOT",
        "- LC2 < 11.0 sustained at tip-in (over-enrichment, revert iter_3)",
        "- CHT > 220 F",
        "",
        "See `vehicles/ryantitus_fatboy_cvo/profile.json` tuning_guardrails.",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_iter5_iteration_json(path: Path, patch_filename: str, findings_name: str) -> None:
    payload = {
        "id": "iter_5",
        "session_id": "2026-05-10_4thgear_baseline",
        "index": 5,
        "patch_filename": patch_filename,
        "patch_base": "iter_3_patched.pvv",
        "supersedes": "iter_4",
        "evidence_findings": findings_name,
        "evidence_tip_in_dir": "iterations/iter_3/pulls/tip_in_3rd_gear",
        "status": "ready_to_flash",
        "flashed_at": None,
        "notes": (
            "iter_5 = combined VE trim (rich WOT cells, +/-5%) + AE table revision "
            "(mid-decay boost, remove 0.91 tail enleanment). iter_4 (VE only) "
            "superseded -- never flashed. All other tables byte-identical to iter_3."
        ),
        "created_at": datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", type=Path, default=DEFAULT_BASE)
    ap.add_argument("--iter5-dir", type=Path, default=DEFAULT_ITER5)
    ap.add_argument("--findings", type=Path, default=DEFAULT_VE_FINDINGS)
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
    ae_item = g2.find_item_by_name(root, AE_TABLE)
    if vf_item is None or vr_item is None:
        print("ERROR: VE tables missing in base", file=sys.stderr)
        return 5
    if ae_item is None:
        print(f"ERROR: '{AE_TABLE}' missing in base", file=sys.stderr)
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

    logger.info("Applying VE trim (rich-only, +/-%.0f%%)", VE_MAX_FRAC_CHANGE * 100)
    _, vf_new, fc = _apply_ve_trim(vf_item, vf_base, ve_grid)
    _, vr_new, rc_count = _apply_ve_trim(vr_item, vr_base, ve_grid)

    logger.info("Applying AE table revisions")
    ae_axis, ae_base, ae_new = _apply_ae(ae_item)

    args.iter5_dir.mkdir(parents=True, exist_ok=True)
    patch_dir = args.iter5_dir / "patch"
    pulls_dir = args.iter5_dir / "pulls"
    patch_dir.mkdir(parents=True, exist_ok=True)
    pulls_dir.mkdir(parents=True, exist_ok=True)
    patched = patch_dir / "iter_5_patched.pvv"

    tree.write(str(patched), encoding="utf-8", xml_declaration=True)

    spark_front_item = g2.find_item_by_name(root, g2.SPARK_FRONT_TABLE)
    spark_rear_item = g2.find_item_by_name(root, g2.SPARK_REAR_TABLE)
    _, _, sf_grid = g2.read_table(spark_front_item)  # type: ignore[arg-type]
    _, _, sr_grid = g2.read_table(spark_rear_item)  # type: ignore[arg-type]

    try:
        g2.verify_patch_gates(
            patched,
            args.base,
            EXPECTED_CHANGED_ITER5,
            UNTOUCHABLE_ITER5,
            (sf_grid, sf_grid),
            (sr_grid, sr_grid),
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

    _write_ae_delta_csv(patch_dir / "ae_delta.csv", ae_axis, ae_base, ae_new)

    new_sha = g2.sha256(patched)
    ve_cells_changed = sum(
        1
        for r in range(len(vf_base))
        for c in range(len(vf_base[0]))
        if abs(vf_new[r][c] - vf_base[r][c]) > 1e-9
    )
    ae_cells_changed = sum(1 for b, n in zip(ae_base, ae_new) if abs(n - b) > 1e-9)

    _write_iter5_change_log(
        patch_dir / "change_log.md",
        base_sha,
        new_sha,
        args.findings,
        ve_cells_changed,
        skipped_lean,
        skipped_small,
        ae_base,
        ae_new,
        ae_axis,
    )
    _write_iter5_guardrails(patch_dir / "guardrails.md")
    _write_iter5_iteration_json(args.iter5_dir / "iteration.json", patched.name, args.findings.name)

    pulls_manifest = pulls_dir / "manifest.json"
    if not pulls_manifest.exists():
        pulls_manifest.write_text(
            json.dumps(
                {
                    "iteration_id": "iter_5",
                    "tune_state": "iter_5_patched.pvv",
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
    print(f"  iter_5_patched SHA-256: {new_sha}")
    print(f"  VE cells trimmed (front grid): {ve_cells_changed}")
    print(f"  AE cells changed:              {ae_cells_changed}")
    print(f"  artifacts: {patch_dir}")
    print(f"  flash this file: {patched}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
