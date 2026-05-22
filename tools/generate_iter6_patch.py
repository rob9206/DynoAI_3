"""
DynoAI iter_6 patch generator -- AE fix only, WOT VE trim reverted.

Background:
    iter_5 was flashed and produced 5 4th-gear WOT pulls (PV_Logfile_5.csv 20-24).
    Best comparable pull (`_24`, full pull to 6185 RPM, gear ~51) made 81.5 hp at
    LC2 ~12.4 in the 3000-5500 band -- versus iter_3's 91-92 hp at LC2 ~11.5-11.7
    in the same band. The bike makes more power richer than the textbook 12.8 PE
    target. Rear injector duty also pegged at 100-104% above 5500 RPM in pulls
    `_21` and `_24`, a hardware ceiling unrelated to VE trim.

iter_6 strategy:
    Base: iter_3_patched.pvv (the proven-good 91-92 hp tune).
    Apply only the Acceleration Enrichment table revisions from iter_5 to address
    mid-RPM tip-in lean spikes, and remove the 0.91 post-event enleanment tail.
    DO NOT trim VE -- iter_5 demonstrated the WOT cells did not want leaning.

Tables changed (1):
    - Acceleration Enrichment

Tables byte-identical to iter_3:
    - VE (TPS based/Front Cyl), VE (TPS based/Rear Cyl)
    - Engine Displacement (103.0 CID), Spark Advance Front/Rear
    - AFR / PE AFR, Deceleration Enleanment, Max Knock Retard, RPM Limit

Usage:
    python tools/generate_iter6_patch.py
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
DEFAULT_BASE = SESSION_DIR / "iterations" / "iter_3" / "patch" / "iter_3_patched.pvv"
DEFAULT_ITER6 = SESSION_DIR / "iterations" / "iter_6"

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

EXPECTED_CHANGED_ITER6 = sorted([AE_TABLE])

UNTOUCHABLE_ITER6 = sorted([
    g2.DISPLACEMENT_TABLE,
    g2.SPARK_FRONT_TABLE,
    g2.SPARK_REAR_TABLE,
    g2.DECEL_ENLEANMENT_TABLE,
    g2.KNOCK_RETARD_TABLE,
    g2.RPM_LIMIT_TABLE,
    g2.AFR_TARGET_TABLE,
    g2.AFR_STOICH_TABLE,
    g2.VE_FRONT_TABLE,
    g2.VE_REAR_TABLE,
])


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


def _write_iter6_change_log(
    path: Path,
    base_sha: str,
    new_sha: str,
    ae_base: list[float],
    ae_new: list[float],
    ae_axis: list[float],
) -> None:
    ae_lines = ["| time idx | base | new | delta |", "|---|---|---|---|"]
    for label, b, n in zip(ae_axis, ae_base, ae_new):
        ae_lines.append(f"| {label:g} | {b:.2f} | {n:.2f} | {n - b:+.2f} |")

    lines = [
        "# iter_6 Patch -- AE fix only (supersedes iter_5; rolls VE back to iter_3)",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "Vehicle: Ryan Titus 2006 Fat Boy CVO (103 ci)",
        "Session: 2026-05-10_4thgear_baseline",
        "",
        "iter_5 (VE rich-trim + AE fix) was flashed and showed a 10+ hp loss vs iter_3",
        "on the comparable full pull (`PV_Logfile_5.csv_24.txt`: 81.5 hp / LC2 12.4",
        "vs iter_3 91-92 hp / LC2 11.5-11.7). Rear injector duty also pegged at",
        "100-104% above 5500 RPM in pulls `_21` and `_24`. Conclusion: this bike's",
        "WOT cells make more power richer than the Dynojet PE target on this dyno",
        "with the LC2 venturi -- iter_5's lean trim went the wrong direction for HP.",
        "",
        "iter_6 keeps only the evidence-driven AE fix (which addresses tip-in lean",
        "spikes seen in 3rd-gear data) and reverts the WOT VE trim to iter_3.",
        "",
        f"- base file: `iter_3_patched.pvv`",
        f"- base SHA-256: `{base_sha}`",
        f"- iter_6_patched.pvv SHA-256: `{new_sha}`",
        "",
        "## Acceleration Enrichment table (only change vs iter_3)",
        "",
        "Boost mid-decay AE for 3000-4700 RPM tip-in, remove 0.91 post-event",
        "enleanment tail.",
        "",
        *ae_lines,
        "",
        "## Tables byte-identical to iter_3",
        "",
        "- VE (TPS based/Front Cyl), VE (TPS based/Rear Cyl) -- WOT trim REVERTED",
        "- Engine Displacement (103.0 CID)",
        "- Spark Advance Front/Rear (cam advance + 5500 knock notch preserved)",
        "- AFR / PE AFR (targets unchanged)",
        "- Deceleration Enleanment, Max Knock Retard, RPM Limit",
        "",
        "## Expected outcome (4th-gear pulls)",
        "",
        "- Peak HP returns to iter_3 baseline: 91-92",
        "- WOT LC2 in 3000-5500 RPM: 11.5-11.7 (back to richer, what the bike likes)",
        "- 3rd-gear tip-in at 3000-4700 RPM: LC2 max 0-300ms drops from ~14.0",
        "  toward 12.5-13.0; bike feels crisper at roll-on",
        "",
        "## Outstanding constraint",
        "",
        "- Rear injector duty saturating 100-104% above 5500 RPM in iter_3/iter_5",
        "  data. Tune cannot push more fuel above this RPM band without bigger",
        "  injectors. iter_7+ should consider lowering RPM ceiling targets or",
        "  flagging a hardware upgrade for the customer.",
        "",
        "## Abort criteria post-flash",
        "",
        "- Tip-in LC2 < 11.0 sustained -- AE overshoot, revert to iter_3",
        "- Knock retard > 4 deg -- something else changed, revert to iter_3",
        "- WOT HP drops vs iter_3 -- unexpected, revert and review",
        "",
        "## Revert",
        "",
        f"Re-flash `iter_3_patched.pvv` (SHA-256 `{base_sha}`).",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_iter6_guardrails(path: Path) -> None:
    lines = [
        "# iter_6 Operational Guardrails",
        "",
        "AE-only revision on top of iter_3. Single change: tip-in fueling.",
        "",
        "## Pull plan",
        "",
        "- [ ] First: 3 clean 4th-gear WOT pulls to 6000+ RPM (must match iter_3 envelope:",
        "      reach ~5800 RPM at ~115 mph in gear ratio ~51)",
        "- [ ] Second: 5 tip-in events in 3rd gear at 3000-4500 RPM",
        "      (snap throttle 0% -> 100% in <0.2s)",
        "",
        "## Win conditions",
        "",
        "- WOT peak HP: 91-92 (matches iter_3 baseline)",
        "- WOT LC2 3000-5500 RPM avg: ~11.5-11.7 (richer is fine, this bike likes it)",
        "- Tip-in LC2 max in first 300 ms: 12.0 - 13.5 (improvement vs iter_3)",
        "- Knock retard: < 2 deg observed; cap is 4 deg",
        "",
        "## Abort criteria",
        "",
        "- LC2 < 11.0 sustained at tip-in (AE over-enriched, revert iter_3)",
        "- Knock retard > 4 deg",
        "- CHT > 220 F",
        "- WOT HP drops vs iter_3 baseline (something is wrong)",
        "",
        "## Known constraints",
        "",
        "- Rear injector duty was 95-105% above 5500 RPM in prior data; expect",
        "  similar in iter_6. This is a hardware ceiling, not a tune issue.",
        "",
        "See `vehicles/ryantitus_fatboy_cvo/profile.json` tuning_guardrails.",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_iter6_iteration_json(path: Path, patch_filename: str) -> None:
    payload = {
        "id": "iter_6",
        "session_id": "2026-05-10_4thgear_baseline",
        "index": 6,
        "patch_filename": patch_filename,
        "patch_base": "iter_3_patched.pvv",
        "supersedes": "iter_5",
        "evidence_dir": "iterations/iter_5/pulls",
        "status": "ready_to_flash",
        "flashed_at": None,
        "notes": (
            "iter_6 = AE table fix only (mid-decay boost, remove 0.91 tail enleanment). "
            "WOT VE trim from iter_5 has been REVERTED -- iter_5 post-flash data "
            "(PV_Logfile_5.csv_20..24) showed 10+ hp loss vs iter_3. This bike's WOT "
            "cells make more power richer than the Dynojet PE target on this dyno. "
            "All tables byte-identical to iter_3 except Acceleration Enrichment."
        ),
        "created_at": datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", type=Path, default=DEFAULT_BASE)
    ap.add_argument("--iter6-dir", type=Path, default=DEFAULT_ITER6)
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

    ae_item = g2.find_item_by_name(root, AE_TABLE)
    if ae_item is None:
        print(f"ERROR: '{AE_TABLE}' missing in base", file=sys.stderr)
        return 5

    logger.info("Applying AE table revisions only (no VE trim)")
    ae_axis, ae_base, ae_new = _apply_ae(ae_item)

    args.iter6_dir.mkdir(parents=True, exist_ok=True)
    patch_dir = args.iter6_dir / "patch"
    pulls_dir = args.iter6_dir / "pulls"
    patch_dir.mkdir(parents=True, exist_ok=True)
    pulls_dir.mkdir(parents=True, exist_ok=True)
    patched = patch_dir / "iter_6_patched.pvv"

    tree.write(str(patched), encoding="utf-8", xml_declaration=True)

    spark_front_item = g2.find_item_by_name(root, g2.SPARK_FRONT_TABLE)
    spark_rear_item = g2.find_item_by_name(root, g2.SPARK_REAR_TABLE)
    _, _, sf_grid = g2.read_table(spark_front_item)  # type: ignore[arg-type]
    _, _, sr_grid = g2.read_table(spark_rear_item)  # type: ignore[arg-type]
    vf_item = g2.find_item_by_name(root, g2.VE_FRONT_TABLE)
    vr_item = g2.find_item_by_name(root, g2.VE_REAR_TABLE)
    _, _, vf_grid = g2.read_table(vf_item)  # type: ignore[arg-type]
    _, _, vr_grid = g2.read_table(vr_item)  # type: ignore[arg-type]

    try:
        g2.verify_patch_gates(
            patched,
            args.base,
            EXPECTED_CHANGED_ITER6,
            UNTOUCHABLE_ITER6,
            (sf_grid, sf_grid),
            (sr_grid, sr_grid),
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

    _write_ae_delta_csv(patch_dir / "ae_delta.csv", ae_axis, ae_base, ae_new)

    new_sha = g2.sha256(patched)
    ae_cells_changed = sum(1 for b, n in zip(ae_base, ae_new) if abs(n - b) > 1e-9)

    _write_iter6_change_log(
        patch_dir / "change_log.md",
        base_sha,
        new_sha,
        ae_base,
        ae_new,
        ae_axis,
    )
    _write_iter6_guardrails(patch_dir / "guardrails.md")
    _write_iter6_iteration_json(args.iter6_dir / "iteration.json", patched.name)

    pulls_manifest = pulls_dir / "manifest.json"
    if not pulls_manifest.exists():
        pulls_manifest.write_text(
            json.dumps(
                {
                    "iteration_id": "iter_6",
                    "tune_state": "iter_6_patched.pvv",
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
    print(f"  iter_6_patched SHA-256: {new_sha}")
    print(f"  AE cells changed:              {ae_cells_changed}")
    print(f"  artifacts: {patch_dir}")
    print(f"  flash this file: {patched}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
