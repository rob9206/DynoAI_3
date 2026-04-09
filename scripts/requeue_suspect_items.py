"""
Requeue suspect ingested calibration files for recapture.

Reads a JSON audit report produced by audit_dispatch_outputs.py,
marks suspect items back to 'pending' in the dispatch queue, and
deletes (or backs up) the bad TSV files so they will be re-exported.

Usage::

    # Dry run — no files are modified
    python scripts/requeue_suspect_items.py \\
        --queue-path data/mastertune_catalog/dispatch_queue_bigtwin_full.json \\
        --audit-report output/audit_report_pre_requeue.json \\
        --dry-run

    # Apply — updates queue and removes bad TSVs
    python scripts/requeue_suspect_items.py \\
        --queue-path data/mastertune_catalog/dispatch_queue_bigtwin_full.json \\
        --audit-report output/audit_report_pre_requeue.json \\
        --apply

    # Apply from audit inline (no separate report file needed)
    python scripts/requeue_suspect_items.py \\
        --queue-path data/mastertune_catalog/dispatch_queue_bigtwin_full.json \\
        --apply --run-audit-inline
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT_DIR / "scripts"


def _delete_or_backup_tsvs(mt_file: Path, backup: bool = True) -> List[str]:
    """Remove TSV files for a calibration so dispatch re-exports them."""
    base = mt_file.parent / "tsv_templates" / mt_file.stem
    tsv_names = ["lambda_map.tsv", "ve_front_map.tsv", "ve_rear_map.tsv"]
    removed = []
    for name in tsv_names:
        p = base / name
        if not p.exists():
            continue
        if backup:
            bak = p.with_suffix(".tsv.bak")
            shutil.copy2(p, bak)
        p.unlink()
        removed.append(str(p))
    return removed


def requeue_suspects(
    queue_path: Path,
    audit_report: Dict[str, Any],
    dry_run: bool = True,
    backup_tsvs: bool = True,
) -> Dict[str, Any]:
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    items: List[Dict[str, Any]] = queue.get("items", [])

    suspect_files = {s["mt_file"] for s in audit_report.get("suspects", [])}

    requeued: List[str] = []
    skipped: List[str] = []
    tsv_removals: List[str] = []

    for item in items:
        mt_file_str = item.get("mt_file", "")
        if mt_file_str not in suspect_files:
            continue

        name = Path(mt_file_str).name
        if item.get("status") != "ingested":
            skipped.append(name)
            continue

        if not dry_run:
            removed = _delete_or_backup_tsvs(Path(mt_file_str), backup=backup_tsvs)
            tsv_removals.extend(removed)

            item["status"] = "pending"
            item["retries"] = 0
            item["reason"] = ""
            item["message"] = "requeued_by_audit"
            item["updated_at"] = datetime.now(timezone.utc).isoformat()

        requeued.append(name)

    if not dry_run and requeued:
        queue_path.write_text(json.dumps(queue, indent=2, default=str), encoding="utf-8")

    result = {
        "dry_run": dry_run,
        "requeued_count": len(requeued),
        "requeued_files": requeued,
        "skipped_wrong_status": skipped,
        "tsv_removals": tsv_removals,
        "queue_path": str(queue_path),
    }
    return result


def _print_result(result: Dict[str, Any]) -> None:
    mode = "DRY RUN" if result["dry_run"] else "APPLIED"
    print(f"\n[{mode}] Requeue result")
    print(f"  requeued : {result['requeued_count']}")
    if result["requeued_files"]:
        for f in result["requeued_files"]:
            print(f"    {f}")
    if result["skipped_wrong_status"]:
        print(f"  skipped (not ingested): {len(result['skipped_wrong_status'])}")
        for f in result["skipped_wrong_status"]:
            print(f"    {f}")
    if result["tsv_removals"]:
        print(f"  TSVs removed/backed up: {len(result['tsv_removals'])}")
    if not result["dry_run"] and result["requeued_count"]:
        print(f"\nQueue updated: {result['queue_path']}")
        print("Resume with:")
        print(f'  python scripts/dispatch_mastertune.py --resume --queue-path "{result["queue_path"]}" --window-title-re "MasterTune2-HD.*"')


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Requeue suspect ingested calibration files for recapture"
    )
    parser.add_argument(
        "--queue-path",
        default=str(ROOT_DIR / "data" / "mastertune_catalog" / "dispatch_queue_bigtwin_full.json"),
        help="Path to the dispatch queue JSON",
    )
    parser.add_argument(
        "--audit-report",
        default=None,
        help="Path to JSON audit report from audit_dispatch_outputs.py",
    )
    parser.add_argument(
        "--run-audit-inline",
        action="store_true",
        help="Run audit inline instead of reading a report file",
    )

    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--dry-run", action="store_true", help="Preview changes without modifying any files")
    mode_group.add_argument("--apply", action="store_true", help="Apply changes: update queue and remove bad TSVs")

    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Delete TSVs without creating .bak backups",
    )
    args = parser.parse_args()

    queue_path = Path(args.queue_path)
    if not queue_path.exists():
        print(f"ERROR: queue not found: {queue_path}", file=sys.stderr)
        return 2

    if args.run_audit_inline:
        # Import and run audit inline
        sys.path.insert(0, str(ROOT_DIR))
        from scripts.audit_dispatch_outputs import run_audit  # noqa: E402
        audit_report = run_audit(queue_path, report_path=None)
        print(f"Inline audit found {audit_report['suspect_count']} suspect files.")
    elif args.audit_report:
        rp = Path(args.audit_report)
        if not rp.exists():
            print(f"ERROR: audit report not found: {rp}", file=sys.stderr)
            return 2
        audit_report = json.loads(rp.read_text(encoding="utf-8"))
    else:
        print("ERROR: provide --audit-report or --run-audit-inline", file=sys.stderr)
        return 2

    if audit_report.get("suspect_count", 0) == 0:
        print("No suspects found. Nothing to requeue.")
        return 0

    result = requeue_suspects(
        queue_path=queue_path,
        audit_report=audit_report,
        dry_run=args.dry_run,
        backup_tsvs=not args.no_backup,
    )
    _print_result(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
