"""
DynoAI iter_10 patch generator -- mirror proposed front spark to rear.

Purpose:
    User requested that the proposed timing-table change be mirrored from
    Front cylinder to Rear cylinder. This keeps inter-cylinder spark symmetry.

Strategy:
    - Base file: iter_9_patched.pvv
    - Copy Spark Advance (Front Cyl) grid directly into Spark Advance (Rear Cyl)
    - Leave all other tables byte-identical to iter_9
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import generate_iter2_patch as g2

logger = logging.getLogger(__name__)

SESSION_DIR = g2.SESSION_DIR
DEFAULT_BASE = SESSION_DIR / "iterations" / "iter_9" / "patch" / "iter_9_patched.pvv"
DEFAULT_ITER10 = SESSION_DIR / "iterations" / "iter_10"

EXPECTED_CHANGED = sorted([g2.SPARK_REAR_TABLE])

UNTOUCHABLE = sorted(
    [
        g2.DISPLACEMENT_TABLE,
        g2.VE_FRONT_TABLE,
        g2.VE_REAR_TABLE,
        g2.SPARK_FRONT_TABLE,
        g2.KNOCK_RETARD_TABLE,
        g2.RPM_LIMIT_TABLE,
        g2.AFR_TARGET_TABLE,
        g2.AFR_STOICH_TABLE,
        g2.ACCEL_ENRICH_TABLE,
        g2.DECEL_ENLEANMENT_TABLE,
    ]
)


def _cells_changed(a: ET.Element, b: ET.Element) -> bool:
    ac = a.findall(".//Cell")
    bc = b.findall(".//Cell")
    if len(ac) != len(bc):
        return True
    for ai, bi in zip(ac, bc):
        av = (ai.get("value", "") or "").strip()
        bv = (bi.get("value", "") or "").strip()
        if av != bv:
            return True
    return False


def _verify_scope_and_mirror(base_file: Path, new_file: Path) -> tuple[bool, str]:
    base_root = ET.parse(str(base_file)).getroot()
    new_root = ET.parse(str(new_file)).getroot()
    base_items = {it.get("name"): it for it in base_root.findall("Item") if it.get("name")}
    new_items = {it.get("name"): it for it in new_root.findall("Item") if it.get("name")}
    common = set(base_items) & set(new_items)
    changed = sorted(name for name in common if _cells_changed(base_items[name], new_items[name]))
    if changed != EXPECTED_CHANGED:
        return False, f"unexpected changed tables: {changed} (expected {EXPECTED_CHANGED})"

    sf_item = g2.find_item_by_name(new_root, g2.SPARK_FRONT_TABLE)
    sr_item = g2.find_item_by_name(new_root, g2.SPARK_REAR_TABLE)
    if sf_item is None or sr_item is None:
        return False, "spark tables missing in new file"
    _, _, sf = g2.read_table(sf_item)
    _, _, sr = g2.read_table(sr_item)
    if len(sf) != len(sr) or len(sf[0]) != len(sr[0]):
        return False, "spark table shape mismatch (front vs rear)"
    for r in range(len(sf)):
        for c in range(len(sf[0])):
            if abs(sf[r][c] - sr[r][c]) > 1e-9:
                return False, f"rear!=front at r={r}, c={c}: front={sf[r][c]}, rear={sr[r][c]}"
    return True, "ok"


def _write_change_log(path: Path, base_sha: str, new_sha: str, changed_cells: int) -> None:
    lines = [
        "# iter_10 Patch -- mirror front spark to rear",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "Vehicle: Ryan Titus 2006 Fat Boy CVO (103 ci)",
        "Session: 2026-05-10_4thgear_baseline",
        "",
        f"- base file: `iter_9_patched.pvv`",
        f"- base SHA-256: `{base_sha}`",
        f"- iter_10_patched.pvv SHA-256: `{new_sha}`",
        "",
        "## Change",
        "",
        "- Mirrored `Spark Advance (Front Cyl)` into `Spark Advance (Rear Cyl)`",
        f"- Rear spark cells changed: {changed_cells}",
        "- Spark Front unchanged",
        "",
        "## Untouched",
        "",
        "- VE Front/Rear (including iter_9 decel trims)",
        "- Deceleration Enleanment (iter_9 values preserved)",
        "- Acceleration Enrichment, AFR/PE AFR",
        "- Displacement, Knock Retard, RPM Limit",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_iteration_json(path: Path, patch_filename: str) -> None:
    payload = {
        "id": "iter_10",
        "session_id": "2026-05-10_4thgear_baseline",
        "index": 10,
        "patch_filename": patch_filename,
        "patch_base": "iter_9_patched.pvv",
        "supersedes": None,
        "evidence_dir": "iterations/iter_9/pulls",
        "status": "ready_to_flash",
        "flashed_at": None,
        "notes": (
            "iter_10 = iter_9 base with spark mirror: Rear spark table set equal "
            "to Front spark table cell-for-cell to mirror proposed timing changes."
        ),
        "created_at": datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", type=Path, default=DEFAULT_BASE)
    ap.add_argument("--iter10-dir", type=Path, default=DEFAULT_ITER10)
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
        print("ERROR: spark tables missing in base", file=sys.stderr)
        return 3

    _, _, sf_grid = g2.read_table(sf_item)
    _, _, sr_base_grid = g2.read_table(sr_item)

    # Mirror front spark into rear spark.
    g2.write_cells(sr_item, sf_grid)

    _, _, sr_new_grid = g2.read_table(sr_item)
    changed_cells = 0
    for r in range(len(sr_base_grid)):
        for c in range(len(sr_base_grid[0])):
            if abs(sr_new_grid[r][c] - sr_base_grid[r][c]) > 1e-9:
                changed_cells += 1

    args.iter10_dir.mkdir(parents=True, exist_ok=True)
    patch_dir = args.iter10_dir / "patch"
    pulls_dir = args.iter10_dir / "pulls"
    patch_dir.mkdir(parents=True, exist_ok=True)
    pulls_dir.mkdir(parents=True, exist_ok=True)
    patched = patch_dir / "iter_10_patched.pvv"

    tree.write(str(patched), encoding="utf-8", xml_declaration=True)

    ok, reason = _verify_scope_and_mirror(args.base, patched)
    if not ok:
        patched.unlink(missing_ok=True)
        print(f"ABORT: verify failed: {reason}", file=sys.stderr)
        return 4

    new_sha = g2.sha256(patched)
    _write_change_log(patch_dir / "change_log.md", base_sha, new_sha, changed_cells)
    _write_iteration_json(args.iter10_dir / "iteration.json", patched.name)

    manifest = pulls_dir / "manifest.json"
    if not manifest.exists():
        manifest.write_text(
            json.dumps(
                {
                    "iteration_id": "iter_10",
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
    print(f"  iter_10_patched SHA-256: {new_sha}")
    print(f"  rear spark cells changed: {changed_cells}")
    print(f"  artifacts: {patch_dir}")
    print(f"  flash this file: {patched}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
