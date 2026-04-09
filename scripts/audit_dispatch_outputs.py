"""
Audit ingested MasterTune calibration TSV outputs for wrong-table captures.

Reports suspect files with reason codes and writes a JSON audit report that
can be fed directly into requeue_suspect_items.py.

Usage::

    python scripts/audit_dispatch_outputs.py --queue-path data/mastertune_catalog/dispatch_queue_bigtwin_full.json
    python scripts/audit_dispatch_outputs.py --queue-path ... --report-path output/audit_report.json

Exit code 0 = no suspects found, 1 = suspects found, 2 = error.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent


def _tsv_stats(fp: Path) -> Optional[Dict[str, Any]]:
    """Return basic stats for a TSV file: rows, cols, min, max, sample_values."""
    if not fp.exists():
        return None
    try:
        lines = [ln for ln in fp.read_text(encoding="utf-8", errors="ignore").splitlines() if ln.strip()]
    except Exception:
        return None
    if len(lines) < 2:
        return {"rows": 0, "cols": 0, "min": None, "max": None, "sample": []}
    vals: List[float] = []
    rows = 0
    cols = 0
    for ln in lines[1:]:
        parts = ln.split("\t")
        nums = []
        for x in parts[1:]:
            try:
                nums.append(float(x))
            except ValueError:
                pass
        if nums:
            rows += 1
            cols = max(cols, len(nums))
            vals.extend(nums)
    return {
        "rows": rows,
        "cols": cols,
        "min": min(vals) if vals else None,
        "max": max(vals) if vals else None,
        "sample": vals[:6],
    }


def _classify_lambda(s: Dict[str, Any]) -> str:
    """Classify lambda table regime from stats."""
    mn, mx = s.get("min"), s.get("max")
    if mn is None or mx is None:
        return "empty"
    if mx <= 2.0 and mn >= 0.5:
        return "lambda"
    if 8.0 <= mn and mx <= 17.0:
        return "afr"
    if mx > 20.0:
        return "ve_range"
    return "other"


def _classify_ve(s: Dict[str, Any]) -> str:
    """Classify VE table regime from stats."""
    mn, mx = s.get("min"), s.get("max")
    if mn is None or mx is None:
        return "empty"
    if mx <= 2.0 and mn >= 0.5:
        return "lambda_range"
    if 8.0 <= mn and mx <= 17.0:
        return "afr_range"
    if mx >= 30.0:
        return "ve"
    return "other"


def _audit_item(mt_file: Path) -> List[Dict[str, Any]]:
    """
    Audit a single calibration file's TSV outputs.
    Returns a list of issue dicts (empty = clean).
    """
    base = mt_file.parent / "tsv_templates" / mt_file.stem
    lf = base / "lambda_map.tsv"
    vf = base / "ve_front_map.tsv"
    vr = base / "ve_rear_map.tsv"

    ls = _tsv_stats(lf)
    fs = _tsv_stats(vf)
    rs = _tsv_stats(vr)

    issues: List[Dict[str, Any]] = []

    if ls is None:
        issues.append({"table": "lambda", "reason": "missing_tsv"})
    if fs is None:
        issues.append({"table": "ve_front", "reason": "missing_tsv"})
    if rs is None:
        issues.append({"table": "ve_rear", "reason": "missing_tsv"})
    if ls is None or fs is None or rs is None:
        return issues

    # Check dimensions — a cranking-style table is very narrow.
    if ls["cols"] <= 2:
        issues.append({"table": "lambda", "reason": "too_narrow", "cols": ls["cols"], "stats": ls})
    if fs["cols"] <= 2:
        issues.append({"table": "ve_front", "reason": "too_narrow", "cols": fs["cols"], "stats": fs})
    if rs["cols"] <= 2:
        issues.append({"table": "ve_rear", "reason": "too_narrow", "cols": rs["cols"], "stats": rs})

    lc = _classify_lambda(ls)
    fc = _classify_ve(fs)
    rc = _classify_ve(rs)

    # Lambda table should be either 'lambda' or 'afr' regime.
    if lc == "ve_range":
        issues.append({"table": "lambda", "reason": "lambda_contains_ve_values",
                       "min": ls["min"], "max": ls["max"]})
    elif lc == "empty":
        issues.append({"table": "lambda", "reason": "lambda_empty", "stats": ls})

    # VE tables must not be in lambda or AFR range.
    if fc == "lambda_range":
        issues.append({"table": "ve_front", "reason": "ve_front_contains_lambda_values",
                       "min": fs["min"], "max": fs["max"]})
    elif fc == "afr_range":
        issues.append({"table": "ve_front", "reason": "ve_front_contains_afr_values",
                       "min": fs["min"], "max": fs["max"]})

    if rc == "lambda_range":
        issues.append({"table": "ve_rear", "reason": "ve_rear_contains_lambda_values",
                       "min": rs["min"], "max": rs["max"]})
    elif rc == "afr_range":
        issues.append({"table": "ve_rear", "reason": "ve_rear_contains_afr_values",
                       "min": rs["min"], "max": rs["max"]})

    # All three tables identical: same wrong table captured 3×.
    def _rounds(vals: List[float]) -> Tuple:
        return tuple(round(v, 2) for v in vals[:6])

    if (ls.get("sample") and fs.get("sample") and rs.get("sample") and
            _rounds(ls["sample"]) == _rounds(fs["sample"]) == _rounds(rs["sample"])):
        issues.append({
            "table": "all",
            "reason": "all_tables_identical_sample",
            "sample": ls["sample"][:6],
        })

    return issues


def run_audit(
    queue_path: Path,
    report_path: Optional[Path],
    only_ingested: bool = True,
) -> Dict[str, Any]:
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    items = queue.get("items", [])

    suspect: List[Dict[str, Any]] = []
    clean = 0
    skipped = 0

    for item in items:
        status = item.get("status", "")
        if only_ingested and status != "ingested":
            skipped += 1
            continue
        mt_file = Path(item["mt_file"])
        issues = _audit_item(mt_file)
        if issues:
            suspect.append({
                "mt_file": str(mt_file),
                "status": status,
                "retries": item.get("retries", 0),
                "issues": issues,
            })
        else:
            clean += 1

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "queue_path": str(queue_path),
        "total_items": len(items),
        "ingested_checked": clean + len(suspect),
        "clean": clean,
        "suspect_count": len(suspect),
        "skipped_non_ingested": skipped,
        "suspects": suspect,
    }

    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Report written to {report_path}")

    return report


def _print_report(report: Dict[str, Any]) -> None:
    print(f"\nAudit report")
    print(f"  queue   : {report['queue_path']}")
    print(f"  checked : {report['ingested_checked']}")
    print(f"  clean   : {report['clean']}")
    print(f"  suspect : {report['suspect_count']}")
    if report["suspects"]:
        print("\nSuspect files:")
        for s in report["suspects"]:
            reasons = ", ".join(f"{i['table']}:{i['reason']}" for i in s["issues"])
            print(f"  {Path(s['mt_file']).name}  [{reasons}]")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit MasterTune TSV outputs for wrong-table captures")
    parser.add_argument(
        "--queue-path",
        default=str(ROOT_DIR / "data" / "mastertune_catalog" / "dispatch_queue_bigtwin_full.json"),
        help="Path to the dispatch queue JSON",
    )
    parser.add_argument(
        "--report-path",
        default=None,
        help="Path to write JSON audit report (optional)",
    )
    parser.add_argument(
        "--all-statuses",
        action="store_true",
        help="Audit all items regardless of status (default: ingested only)",
    )
    args = parser.parse_args()

    queue_path = Path(args.queue_path)
    if not queue_path.exists():
        print(f"ERROR: queue path not found: {queue_path}", file=sys.stderr)
        return 2

    report_path = Path(args.report_path) if args.report_path else None
    report = run_audit(queue_path, report_path, only_ingested=not args.all_statuses)
    _print_report(report)

    return 1 if report["suspect_count"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
